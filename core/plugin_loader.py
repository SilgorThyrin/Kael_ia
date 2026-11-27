"""Carregador unificado de plugins estilo Claude Code para o Kael."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


class KaelPluginManager:
    def __init__(self, plugins_dir: Path, state_path: Path):
        self.plugins_dir = Path(plugins_dir)
        self.state_path = Path(state_path)
        self.plugins: dict[str, dict] = {}
        self.hooks: dict[str, list] = {
            "pre_chat": [],
            "pre_cloud": [],
            "post_save": [],
        }
        self._registered_cmds: list[str] = []
        self._state = self._load_state()

    def _load_state(self) -> dict:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"disabled": []}

    def _save_state(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    @staticmethod
    def _import_module(module_name: str, file_path: Path):
        if module_name in sys.modules:
            del sys.modules[module_name]
        spec = importlib.util.spec_from_file_location(module_name, str(file_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    @staticmethod
    def _find_manifest(folder: Path) -> Path | None:
        for rel in ("plugin.json", ".claude-plugin/plugin.json"):
            candidate = folder / rel
            if candidate.is_file():
                return candidate
        return None

    def _register_command(self, registry, cmd_name: str, cmd_spec: dict, pid: str = "plugin"):
        if not cmd_name.startswith("/"):
            cmd_name = f"/{cmd_name}"
        cmd_key = cmd_name.lower()
        if hasattr(registry, "commands") and isinstance(registry.commands, dict):
            spec = dict(cmd_spec)
            spec.setdefault("tool", f"plugin:{pid}")
            spec.setdefault("capability", "confirm")
            registry.commands[cmd_key] = spec
            self._registered_cmds.append(cmd_key)

    def _load_markdown_commands(self, folder: Path, pid: str, ctx, registry):
        cmd_dir = folder / "commands"
        if not cmd_dir.is_dir():
            return
        for md_file in sorted(cmd_dir.glob("*.md")):
            instrucao = md_file.read_text(encoding="utf-8", errors="replace").strip()
            cmd_name = f"/{md_file.stem}"

            def _make_handler(texto_cmd: str, nome_cmd: str):
                def _handler(c, args=None, flags=None):
                    extra = " ".join(args) if isinstance(args, list) else str(args or "")
                    if not hasattr(c, "ceo") or not c.ceo.manager.is_configured:
                        return {
                            "response": f"🔌 Comando `{nome_cmd}` carregado, mas `GEMINI_API_KEY` não está configurada.",
                            "thinking": "Plugin markdown sem API.",
                            "status": "error",
                        }
                    rel = c.ceo.manager.executar_ordem(
                        ordem_ceo=f"{texto_cmd}\n\nEntrada do usuário: {extra}".strip(),
                        contexto_empresa=f"Execução do comando de plugin {nome_cmd} ({pid}).",
                    )
                    return {
                        "response": rel.get("resumo_executivo", json.dumps(rel, ensure_ascii=False)),
                        "thinking": f"Executado via plugin {pid}.",
                        "status": "success",
                    }
                return _handler

            self._register_command(registry, cmd_name, {
                "handler": _make_handler(instrucao, cmd_name),
                "desc": f"[Plugin {pid}] Comando {md_file.stem}",
                "capability": "read",
            })

    def discover_and_load(self, ctx, registry):
        """Lê plugins/* e registra skills, slash commands, tools do Gemini e hooks."""
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.plugins.clear()
        for k in self.hooks:
            self.hooks[k].clear()

        if hasattr(registry, "commands") and isinstance(registry.commands, dict):
            for old_cmd in self._registered_cmds:
                registry.commands.pop(old_cmd, None)
        self._registered_cmds.clear()

        disabled = set(self._state.get("disabled", []))

        for folder in sorted(self.plugins_dir.iterdir()):
            if not folder.is_dir():
                continue
            manifest_file = self._find_manifest(folder)
            if not manifest_file:
                continue

            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            pid = manifest.get("id") or manifest.get("name") or folder.name
            enabled = pid not in disabled and manifest.get("enabled", True)

            entry = {
                "id": pid,
                "name": manifest.get("name", pid),
                "version": manifest.get("version", "1.0.0"),
                "description": manifest.get("description", ""),
                "path": str(folder),
                "enabled": enabled,
                "skill": "",
                "tools_count": 0,
                "hooks_count": 0,
            }
            self.plugins[pid] = entry
            if not enabled:
                continue

            # 1. Carrega SKILL.md
            skill_rel = manifest.get("skill_file", "SKILL.md")
            skill_path = folder / skill_rel
            if skill_path.is_file():
                entry["skill"] = skill_path.read_text(encoding="utf-8").strip()

            # 2. Carrega commands/*.md (padrão Claude Code)
            self._load_markdown_commands(folder, pid, ctx, registry)

            # 3. Carrega tools.py (slash commands + GOOGLE_TOOLS para o Gerente)
            tools_rel = manifest.get("tools_module", "tools.py")
            tools_path = folder / tools_rel
            if tools_path.is_file():
                mod = self._import_module(f"kael_plugin_{pid}_tools", tools_path)
                if hasattr(mod, "COMMANDS") and isinstance(mod.COMMANDS, dict):
                    for cmd_name, cmd_spec in mod.COMMANDS.items():
                        self._register_command(registry, cmd_name, cmd_spec, pid=pid)
                        entry["tools_count"] += 1
                if hasattr(mod, "register"):
                    mod.register(ctx, registry)
                if hasattr(ctx, "ceo") and hasattr(mod, "GOOGLE_TOOLS"):
                    for fn, decl in mod.GOOGLE_TOOLS:
                        ctx.ceo.manager.register_tool(fn, decl)
                        entry["tools_count"] += 1

            # 4. Carrega hooks.py
            hooks_rel = manifest.get("hooks_module", "hooks.py")
            hooks_path = folder / hooks_rel
            if hooks_path.is_file():
                mod = self._import_module(f"kael_plugin_{pid}_hooks", hooks_path)
                for event_name in self.hooks:
                    if hasattr(mod, event_name):
                        self.hooks[event_name].append(getattr(mod, event_name))
                        entry["hooks_count"] += 1

    def set_enabled(self, pid: str, enabled: bool) -> bool:
        if pid not in self.plugins:
            return False
        disabled = set(self._state.get("disabled", []))
        if enabled:
            disabled.discard(pid)
        else:
            disabled.add(pid)
        self._state["disabled"] = sorted(disabled)
        self._save_state()
        return True

    def install_from_git(self, repo_url: str) -> str:
        if not repo_url.startswith(("https://", "git@")):
            raise ValueError("URL inválida. Use https:// ou git@.")
        folder_name = repo_url.rstrip("/").split("/")[-1].removesuffix(".git")
        dest = (self.plugins_dir / folder_name).resolve()
        if dest.exists():
            raise ValueError(f"Plugin '{folder_name}' já existe.")
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(dest)],
            check=True,
            timeout=60,
        )
        if not self._find_manifest(dest):
            raise ValueError("Repositório sem plugin.json ou .claude-plugin/plugin.json.")
        return folder_name

    def run_hooks(self, event_name: str, payload: dict) -> dict:
        for fn in self.hooks.get(event_name, []):
            try:
                res = fn(payload)
                if isinstance(res, dict):
                    payload = res
            except Exception:
                pass
        return payload

    def active_skills_prompt(self) -> str:
        parts = [
            f"[Plugin: {p['name']}]\n{p['skill']}"
            for p in self.plugins.values()
            if p["enabled"] and p["skill"]
        ]
        return "\n\n".join(parts)

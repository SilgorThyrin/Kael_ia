"""
KAEL CONTEXT - Contexto central do Kael
Carrega configuração, inicializa módulos opcionais e gerencia estado.
"""
import json
import os
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))


class KaelContext:
    def __init__(self):
        from core.configuration import load_config
        self.config = load_config(base_dir=BASE_DIR)
        self.config_file = Path(self.config["config_path"])
        
        self.system_prompt = self.config.get("system_prompt", "")
        self.ollama_url = self.config.get("ollama_url", "http://127.0.0.1:8080")
        self.model_name = self.config.get("model_name", "qwen3:8b")
        
        # Caminhos de projeto
        self.projects_root = Path(self.config["projects_root"])
        self.project_path = Path(self.config["project_path"])

        from core.permission_policy import PermissionPolicy
        self.permission_policy = PermissionPolicy(
            self.projects_root,
            BASE_DIR / "config" / "autonomy.local.json",
        )
        
        # Memória
        self.memory_dir = Path(self.config["memory_dir"])
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Histórico
        self.historico_file = BASE_DIR / "ultimas_mensagens.json"
        
        # Modo autônomo
        self.autonomous = {"active": False, "project": None}
        
        # Módulos opcionais
        self.memory = None
        self.compressor = None
        self.game_bridge = None
        self.web_research = None
        self.plugin_bridge = None
        self.autonomous_agent = None
        self.registry = None
        
        # Tenta importar módulos
        try:
            from core.memory import KaelMemory
            self.memory = KaelMemory()
            print("[OK] Memória vetorial carregada")
        except ImportError as e:
            print(f"[AVISO] Memória vetorial indisponível: {e}")
        
        try:
            from core.context_compressor import ContextCompressor
            self.compressor = ContextCompressor(max_chars=12000)
            print("[OK] Compressor de contexto carregado")
        except ImportError as e:
            print(f"[AVISO] Compressor indisponível: {e}")
        
        try:
            from tools.game_bridge import GameBridge
            self.game_bridge = GameBridge
            print("[OK] Game Bridge carregado")
        except ImportError as e:
            print(f"[AVISO] Game Bridge indisponível: {e}")
        
        try:
            from tools.web_research import WebResearch
            self.web_research = WebResearch
            print("[OK] Web Research carregado")
        except ImportError as e:
            print(f"[AVISO] Web Research indisponível: {e}")
    
    def ollama_online(self):
        """Verifica se o Ollama está respondendo."""
        try:
            import requests
            r = requests.get(f"{self.ollama_url}/api/tags", timeout=3)
            return r.status_code == 200
        except:
            return False
    
    def generate(self, prompt, generation_settings=None):
        """Gera resposta via ollama_client."""
        try:
            from ai.ollama_client import generate_response
            settings = generation_settings or getattr(self, "generation_settings", None)
            return generate_response(prompt, settings=settings)
        except ImportError as e:
            print(f"[ERRO] ollama_client não encontrado: {e}")
            message = "Cliente Ollama não disponível."
            return {"response": f"[ERRO] {message}", "thinking": "", "error": message}
    
    def load_historico(self):
        """Carrega histórico de conversas."""
        if not self.historico_file.exists():
            return []
        try:
            with open(self.historico_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    
    def save_historico(self, historico):
        """Salva histórico (mantém apenas as últimas 50 mensagens)."""
        try:
            with open(self.historico_file, 'w', encoding='utf-8') as f:
                json.dump(historico[-50:], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERRO] Ao salvar histórico: {e}")
    
    CODE_EXTENSIONS = {
        ".bat", ".c", ".cc", ".cpp", ".cs", ".css", ".gd", ".gdshader",
        ".go", ".h", ".hpp", ".html", ".java", ".js", ".jsx", ".lua",
        ".luau", ".php", ".ps1", ".py", ".rb", ".rs", ".sh", ".sql",
        ".svg", ".ts", ".tsx", ".tscn", ".tres", ".xml",
    }

    @classmethod
    def contains_code_changes(cls, matches):
        return any(Path(filename).suffix.casefold() in cls.CODE_EXTENSIONS for filename, _ in matches)

    def request_tested_save_commands(
        self, response_text, save_dir=None, require_authorized_folder=False
    ):
        import re
        from core.change_validation import ChangeValidation

        target_dir = (Path(save_dir) if save_dir else self.memory_dir).resolve()
        pattern = r'<kael_save\s+filename=[\'"]([^\'"]+)[\'"]>(.*?)</kael_save>'
        matches = re.findall(pattern, response_text, re.DOTALL)
        code_matches = []
        all_changes = []
        try:
            for filename, content in matches:
                safe_name = self._safe_save_name(filename).as_posix()
                all_changes.append((safe_name, content.strip()))
                if Path(safe_name).suffix.casefold() in self.CODE_EXTENSIONS:
                    code_matches.append(safe_name)
            preview = self.preview_save_commands(response_text, save_dir=target_dir)
        except (OSError, ValueError) as exc:
            return {
                "status": "error",
                "response": f"Nenhum arquivo foi alterado; a proposta não passou pela validação: {exc}",
            }

        if not code_matches:
            return None

        validator = ChangeValidation(
            getattr(self, "config", {}).get("godot_executable")
        )
        test_plan = validator.test_plan(
            target_dir,
            code_matches,
            proposed_files=all_changes,
        )
        if test_plan is None:
            if {Path(name).suffix.casefold() for name in code_matches}.issubset(
                {".lua", ".luau"}
            ):
                reason = (
                    "ALTERAÇÃO BLOQUEADA: não há um runner de testes Roblox/Luau "
                    "configurado. Nenhum código foi gravado."
                )
            else:
                reason = (
                    "ALTERAÇÃO BLOQUEADA: não encontrei uma suíte de testes compatível. "
                    "Nenhum código foi gravado."
                )
            return {
                "status": "error",
                "response": reason,
            }

        registry = getattr(self, "registry", None)
        if registry is None:
            return {
                "status": "error",
                "response": "ALTERAÇÃO BLOQUEADA: o serviço de autorização não está disponível.",
            }

        def run_tests_and_request_apply():
            if (
                require_authorized_folder
                and not self.permission_policy.is_trusted_directory(target_dir)
            ):
                return {
                    "status": "error",
                    "response": "A autorização da pasta foi revogada; nenhum teste ou arquivo foi alterado.",
                }

            report = validator.run(target_dir, all_changes, test_plan)
            report_text = f"{report['summary']}\n\n{report.get('output', '')}".strip()
            if report["status"] != "success":
                return {
                    "status": "error",
                    "response": f"TESTES FALHARAM. Nenhum arquivo foi alterado.\n\n{report_text}",
                }

            try:
                current_preview = self.preview_save_commands(
                    response_text,
                    save_dir=target_dir,
                )
            except (OSError, ValueError) as exc:
                return {
                    "status": "error",
                    "response": f"Nenhum arquivo foi alterado; não foi possível confirmar a prévia: {exc}",
                }
            if current_preview != preview:
                return {
                    "status": "error",
                    "response": "Nenhum arquivo foi alterado; o destino mudou durante os testes.",
                }

            apply_permission = registry.create_approval(
                title="Aprovar implementação testada",
                summary=f"Os testes passaram. Autorizar a gravação de {len(matches)} arquivo(s) em {target_dir}?",
                details=f"{report_text}\n\nPRÉVIA:\n{preview}",
                callback=lambda: self._apply_tested_save_commands(
                    response_text,
                    target_dir,
                    preview,
                    require_authorized_folder,
                ),
                workspace_action="apply_tested_changes",
            )
            return {
                "status": "success",
                "response": f"✅ Testes aprovados. Revise a prévia e autorize a implementação no novo cartão.\n\n{report_text}",
                "next_permission": apply_permission,
            }

        test_permission = registry.create_approval(
            title="Autorizar testes antes da implementação",
            summary=f"Executar {test_plan['description']} em uma cópia temporária do projeto.",
            details=(
                "Os testes podem executar código do projeto com os privilégios do Kael e "
                "podem acessar recursos do sistema/rede. A cópia temporária evita gravar "
                "a proposta no projeto original, mas não é uma sandbox de segurança.\n\n"
                f"Os arquivos originais não serão alterados durante o teste.\n\nPRÉVIA:\n{preview}"
            ),
            callback=run_tests_and_request_apply,
            workspace_action="run_tests",
        )
        return {
            "status": "permission_required",
            "response": "O código está aguardando autorização para ser testado antes de qualquer gravação.",
            "permission": test_permission,
        }

    def _apply_tested_save_commands(
        self, response_text, save_dir, expected_preview, require_authorized_folder
    ):
        try:
            current_preview = self.preview_save_commands(response_text, save_dir=save_dir)
        except (OSError, ValueError) as exc:
            return {
                "status": "error",
                "response": f"Nenhum arquivo foi alterado; a prévia deixou de ser válida: {exc}",
            }
        if current_preview != expected_preview:
            return {
                "status": "error",
                "response": "Nenhum arquivo foi alterado; o destino mudou depois dos testes.",
            }
        if (
            require_authorized_folder
            and not self.permission_policy.is_trusted_directory(save_dir)
        ):
            return {
                "status": "error",
                "response": "A autorização da pasta foi revogada; nenhum arquivo foi alterado.",
            }
        response = self.process_save_commands(
            response_text,
            save_dir=save_dir,
            authorized_folder_required=require_authorized_folder,
            validation_passed=True,
            approval_granted=True,
        )
        failed = any(marker in response for marker in (
            "[ERRO AO SALVAR",
            "[ARQUIVO BLOQUEADO",
            "[ARQUIVO NAO ALTERADO:",
        ))
        return {
            "status": "error" if failed else "success",
            "response": response,
        }

    def process_save_commands(
        self,
        response_text,
        save_dir=None,
        require_trusted_folder=False,
        authorized_folder_required=False,
        validation_passed=False,
        approval_granted=False,
    ):
        """Intercepta <kael_save> e escreve no disco."""
        import re
        target_dir = (Path(save_dir) if save_dir else self.memory_dir).resolve()
        
        pattern = r'<kael_save\s+filename=[\'"]([^\'"]+)[\'"]>(.*?)</kael_save>'
        matches = re.findall(pattern, response_text, re.DOTALL)
        if len(matches) > 20:
            return "\n[ARQUIVO BLOQUEADO: o limite é 20 arquivos por operação.]"
        if self.contains_code_changes(matches) and not validation_passed:
            pending = self.request_tested_save_commands(
                response_text,
                save_dir=target_dir,
                require_authorized_folder=(
                    authorized_folder_required or require_trusted_folder
                ),
            )
            if pending is None:
                return "\n[ARQUIVO BLOQUEADO: não foi possível preparar a validação do código.]"
            if pending["status"] == "permission_required":
                return f"\n[AGUARDANDO TESTE E APROVAÇÃO: {pending['response']}]"
            reason = pending["response"].strip()
            if reason.startswith("ALTERAÇÃO BLOQUEADA:"):
                return f"\n[{reason}]"
            return f"\n[ALTERAÇÃO BLOQUEADA: {pending['response']}]"
        if (
            authorized_folder_required
            and not self.permission_policy.is_trusted_directory(target_dir)
        ):
            return "\n[ARQUIVO BLOQUEADO: a autorização da pasta foi revogada.]"
        if require_trusted_folder and not self.permission_policy.allows_trusted_folder_write(target_dir):
            return "\n[ARQUIVO BLOQUEADO: a pasta autorizada mudou antes da gravação.]"
        target_dir.mkdir(parents=True, exist_ok=True)
        project_autonomous_write = self.permission_policy.allows_project_write(target_dir)
        
        saved_files = []
        clean_text = response_text
        
        for filename, content in matches:
            try:
                safe_name = self._safe_save_name(filename)
            except ValueError as exc:
                clean_text = clean_text.replace(
                    f'<kael_save filename="{filename}">{content}</kael_save>',
                    f"\n[ARQUIVO BLOQUEADO: {exc}]",
                )
                clean_text = clean_text.replace(
                    f"<kael_save filename='{filename}'>{content}</kael_save>",
                    f"\n[ARQUIVO BLOQUEADO: {exc}]",
                )
                continue
            filepath = (target_dir / safe_name).resolve()
            if filepath != target_dir and target_dir not in filepath.parents:
                clean_text = clean_text.replace(
                    f'<kael_save filename="{filename}">{content}</kael_save>',
                    f"\n[ARQUIVO BLOQUEADO: caminho fora do diretorio permitido '{filename}']",
                )
                clean_text = clean_text.replace(
                    f"<kael_save filename='{filename}'>{content}</kael_save>",
                    f"\n[ARQUIVO BLOQUEADO: caminho fora do diretorio permitido '{filename}']",
                )
                continue

            trusted_folder_write = getattr(
                self.permission_policy,
                "allows_trusted_folder_write",
                lambda _path: False,
            )(filepath)
            if require_trusted_folder and not trusted_folder_write:
                clean_text = clean_text.replace(
                    f'<kael_save filename="{filename}">{content}</kael_save>',
                    f"\n[ARQUIVO BLOQUEADO: a pasta autorizada mudou antes da gravação de '{safe_name}']",
                )
                clean_text = clean_text.replace(
                    f"<kael_save filename='{filename}'>{content}</kael_save>",
                    f"\n[ARQUIVO BLOQUEADO: a pasta autorizada mudou antes da gravação de '{safe_name}']",
                )
                continue
            autonomous_write = project_autonomous_write or trusted_folder_write
            
            try:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                if project_autonomous_write and filepath.exists() and not approval_granted:
                    registry = self.registry
                    if registry is None:
                        raise RuntimeError(
                            "Não é possível pedir autorização para sobrescrever sem o serviço de permissões."
                        )
                    approved, outcome = registry.request_approval_and_wait(
                        title="Permissão para sobrescrever arquivo",
                        summary=f"O Kael quer substituir {safe_name}.",
                        details=(
                            f"Destino: {filepath}\n"
                            "Uma cópia de segurança será criada antes da substituição."
                        ),
                        action=lambda: self._write_save_file(
                            filepath,
                            content.strip(),
                            create_backup=True,
                            allow_overwrite=True,
                            allowed_root=target_dir,
                        ),
                    )
                    if not approved:
                        clean_text = clean_text.replace(
                            f'<kael_save filename="{filename}">{content}</kael_save>',
                            f"\n[ARQUIVO NAO ALTERADO: sobrescrita negada ou expirada para '{safe_name}']",
                        )
                        clean_text = clean_text.replace(
                            f"<kael_save filename='{filename}'>{content}</kael_save>",
                            f"\n[ARQUIVO NAO ALTERADO: sobrescrita negada ou expirada para '{safe_name}']",
                        )
                        continue
                    if isinstance(outcome, dict) and outcome.get("error"):
                        raise RuntimeError(outcome["error"])
                elif trusted_folder_write:
                    self._write_save_file(
                        filepath,
                        content.strip(),
                        create_backup=filepath.exists(),
                        allow_overwrite=True,
                        allowed_root=target_dir,
                    )
                else:
                    self._write_save_file(
                        filepath,
                        content.strip(),
                        create_backup=filepath.exists(),
                        allow_overwrite=approval_granted or not autonomous_write,
                        allowed_root=target_dir,
                    )
                saved_files.append(str(safe_name))
                
                # Salva na memória vetorial se disponível
                if self.memory:
                    try:
                        self.memory.add_memory(content.strip(), f"arquivo:{safe_name}")
                    except Exception as exc:
                        print(f"[AVISO] Falha ao indexar {safe_name} na memória: {exc}")
                
                clean_text = clean_text.replace(f'<kael_save filename="{filename}">{content}</kael_save>', '')
                clean_text = clean_text.replace(f"<kael_save filename='{filename}'>{content}</kael_save>", '')
            except Exception as e:
                clean_text += f"\n\n[ERRO AO SALVAR {safe_name}: {e}]"
        
        if saved_files:
            clean_text += f"\n\n✅ **Sistema:** Arquivos salvos: {', '.join(saved_files)}"
        return clean_text

    @staticmethod
    def _safe_save_name(filename):
        import re

        normalized = filename.replace("\\", "/")
        parts = [part for part in normalized.split("/") if part not in ("", ".")]
        is_absolute = normalized.startswith("/") or (
            len(parts[0]) >= 2 and parts[0][1] == ":" if parts else False
        )
        reserved_names = {
            "CON", "PRN", "AUX", "NUL",
            *(f"COM{index}" for index in range(1, 10)),
            *(f"LPT{index}" for index in range(1, 10)),
        }
        if (
            not parts
            or ".." in parts
            or is_absolute
            or any(re.search(r'[\x00-\x1f<>:"|?*]', part) for part in parts)
            or any(part.endswith((" ", ".")) for part in parts)
            or any(part.split(".", 1)[0].upper() in reserved_names for part in parts)
        ):
            raise ValueError(f"nome de arquivo inseguro: {filename}")
        return Path(*parts)

    def preview_save_commands(self, response_text, save_dir=None):
        """Build a bounded unified diff for every file emitted by <kael_save>."""
        import difflib
        import re

        target_dir = (Path(save_dir) if save_dir else self.memory_dir).resolve()
        pattern = r'<kael_save\s+filename=[\'"]([^\'"]+)[\'"]>(.*?)</kael_save>'
        matches = re.findall(pattern, response_text, re.DOTALL)
        if not matches:
            raise ValueError("A resposta não contém arquivos para pré-visualizar.")
        if len(matches) > 20:
            raise ValueError("A operação excede o limite de 20 arquivos.")

        previews = []
        total_chars = 0
        seen_paths = set()
        for filename, content in matches:
            safe_name = self._safe_save_name(filename)
            filepath = (target_dir / safe_name).resolve()
            if filepath == target_dir or target_dir not in filepath.parents:
                raise ValueError(f"O caminho sai da pasta autorizada: {filename}")
            path_key = str(filepath).casefold()
            if path_key in seen_paths:
                raise ValueError(f"O mesmo destino aparece mais de uma vez: {safe_name}")
            seen_paths.add(path_key)
            if filepath.exists() and not filepath.is_file():
                raise ValueError(f"O destino não é um arquivo regular: {safe_name}")

            original = ""
            if filepath.exists():
                if filepath.stat().st_size > 2 * 1024 * 1024:
                    raise ValueError(f"O arquivo existente excede 2 MB: {safe_name}")
                try:
                    original = filepath.read_text(encoding="utf-8")
                except UnicodeDecodeError as exc:
                    raise ValueError(f"O arquivo existente não é texto UTF-8: {safe_name}") from exc

            proposed = content.strip()
            old_label = f"a/{safe_name.as_posix()}" if filepath.exists() else "/dev/null"
            diff = "".join(difflib.unified_diff(
                original.splitlines(keepends=True),
                proposed.splitlines(keepends=True),
                fromfile=old_label,
                tofile=f"b/{safe_name.as_posix()}",
            ))
            action = "Alterar" if filepath.exists() else "Criar"
            preview = f"{action}: {safe_name.as_posix()}\n"
            preview += diff if diff else "(sem diferenças)\n"
            previews.append(preview)
            total_chars += len(preview)
            if total_chars > 100000:
                raise ValueError("A prévia excede 100.000 caracteres; divida a operação.")

        return "\n".join(previews)

    def _write_save_file(
        self,
        filepath,
        content,
        create_backup=False,
        allow_overwrite=True,
        allowed_root=None,
    ):
        """Atomically writes a file and preserves approved overwrites."""
        import secrets
        from datetime import datetime

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        if allowed_root is not None:
            root = Path(allowed_root).resolve()
            parent = filepath.parent.resolve()
            if parent != root and root not in parent.parents:
                raise ValueError(f"O diretório de destino saiu do escopo permitido: {parent}")
            filepath = parent / filepath.name
        if filepath.exists() and not allow_overwrite:
            raise FileExistsError(
                f"O arquivo foi criado durante a operação e não será sobrescrito sem autorização: {filepath}"
            )
        if create_backup and filepath.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup = filepath.with_name(f"{filepath.name}.bak.{timestamp}")
            shutil.copy2(str(filepath), str(backup))

        temp_path = filepath.with_name(f".{filepath.name}.{secrets.token_hex(4)}.tmp")
        try:
            temp_path.write_text(content, encoding="utf-8")
            os.replace(str(temp_path), str(filepath))
        finally:
            if temp_path.exists():
                temp_path.unlink()
        return str(filepath)
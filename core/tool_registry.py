"""
KAEL TOOL REGISTRY v5.3 - HUB unificado com /organizar_jogo
"""
import importlib
import re
import secrets
import threading
import time
from pathlib import Path

TOOLS_DIR = Path(__file__).parent.parent / "tools"
_APPROVAL_RESOURCE_UNBOUND = object()

class ToolRegistry:
    def __init__(self, ctx):
        self.ctx = ctx
        self.commands = {}
        self.tools = {}
        self.pending_approvals = {}
        self._approval_lock = threading.Lock()
        self._register_internal_commands()
    
    def _register_internal_commands(self):
        """Registra todos os comandos internos."""
        handlers = {
            '/status': (self._cmd_status, "Status completo do sistema Kael", "read"),
            '/teste_conexao': (self._cmd_teste_conexao, "Ping no Ollama e Studio", "read"),
            '/help': (self._cmd_help, "Lista todos os comandos", "read"),
            '/ajuda': (self._cmd_help, "Lista todos os comandos", "read"),
            '/gerenciar_jogo': (self._cmd_gerenciar_jogo, "Ativa modo autônomo em um projeto", "control"),
            '/parar_gerenciamento': (self._cmd_parar_gerenciamento, "Desativa modo autônomo", "control"),
            '/ver_jogo': (self._cmd_ver_jogo, "Análise estática real do projeto", "read"),
            '/integrar_jogo': (self._cmd_integrar_jogo, "IA analisa e corrige scripts reais", "project_write"),
            '/refatorar': (self._cmd_refatorar, "IA refatora o maior script", "project_write"),
            '/construir_jogo': (self._cmd_construir_jogo, "Cria estrutura + GDD do projeto", "project_create"),
            '/pesquisar_jogos': (self._cmd_pesquisar_jogos, "Pesquisa web de referência", "network"),
            '/limpar_flutuantes': (self._cmd_limpar_flutuantes, "Varredura + remoção em lote", "studio"),
            '/resultado_limpeza': (self._cmd_resultado_limpeza, "Resultado da última limpeza", "read"),
            '/criar_terreno': (self._cmd_criar_terreno, "Terreno: /criar_terreno colinas --tamanho 384 --seed 10", "project_write"),
            '/criar_assets': (self._cmd_criar_assets, "Assets: /criar_assets arvore --quantidade 5 --seed 10", "project_write"),
            '/desfazer_terreno': (self._cmd_desfazer_terreno, "Restaura terreno: /desfazer_terreno <backup_id>", "studio"),
            '/remover_assets_kael': (self._cmd_remover_assets_kael, "Guarda os assets gerados pelo Kael em backup", "studio"),
            '/desfazer_assets_kael': (self._cmd_desfazer_assets_kael, "Restaura assets: /desfazer_assets_kael <backup_id>", "studio"),
            '/resultado_criacao': (self._cmd_resultado_criacao, "Resultado da criação (opcionalmente informe o task_id)", "read"),
            '/avaliar_criacao': (self._cmd_avaliar_criacao, "Avalia scripts, terreno e assets do jogo", "read"),
            '/corrigir_automaticamente': (self._cmd_corrigir_automaticamente, "Agente autônomo corrige erros", "project_write"),
            '/criar_automaticamente': (self._cmd_criar_automaticamente, "Agente autônomo CRIA o jogo do zero", "project_create"),
            '/organizar_jogo': (self._cmd_organizar_jogo, "Analisa e envia limpeza direto ao Studio", "studio"),
            '/memoria': (self._cmd_memoria, "Inspecao da memoria unificada (regras, episodios, semantica)", "read"),
            '/criar_criativo': (self._cmd_criar_criativo, "Geracao criativa de jogo com temperatura adaptativa", "project_create"),
            '/ideia': (self._cmd_ideia, "Gera ideias criativas via síntese de generos", "read"),
            '/temperatura': (self._cmd_temperatura, "Mostra configuracoes de temperatura adaptativa", "read"),
            '/contexto': (self._cmd_contexto, "Mostra contexto da memória unificada e do projeto", "read"),
            '/estratégia': (self._cmd_estratégia, "Modo CEO: analisa solicitação como plano empresarial", "read"),
            '/modelo': (self._cmd_modelo, "Mudar modelo de IA (local/nuvem)", "read"),
            '/memória_detalhada': (self._cmd_memória_detalhada, "Memória unificada completa (regras + episódios + semântica)", "read"),
            '/criar_arquivo': (self._cmd_criar_arquivo, "Cria novo arquivo com autorização", "project_write"),
            '/modificar_arquivo': (self._cmd_modificar_arquivo, "Modifica arquivo existente com autorização", "project_write"),
            '/ler_arquivo': (self._cmd_ler_arquivo, "Lê conteúdo de um arquivo", "read"),
            '/listar_arquivos': (self._cmd_listar_arquivos, "Lista arquivos e pastas", "read"),
            '/autorizar_acao': (self._cmd_autorizar_acao, "Autoriza ação pendente de arquivo", "project_write"),
            '/cancelar_acao': (self._cmd_cancelar_acao, "Cancela ação pendente de arquivo", "project_write"),
            '/acoes_pendentes': (self._cmd_acoes_pendentes, "Lista ações pendentes de autorização", "read"),
        }

        for cmd, (handler, desc, capability) in handlers.items():
            self.commands[cmd.lower()] = {
                "handler": handler,
                "desc": desc,
                "tool": "core",
                "capability": capability,
            }
    
    def register_module(self, mod):
        """Registra módulo externo."""
        name = getattr(mod, "TOOL_NAME", mod.__name__)
        self.tools[name] = mod
        cmds = getattr(mod, "COMMANDS", {})
        for cmd, info in cmds.items():
            self.commands[cmd.lower()] = {
                "handler": info["handler"],
                "desc": info.get("desc", ""),
                "tool": name,
                "capability": info.get("capability", "confirm"),
                "validate": info.get("validate"),
            }
        print(f"[REG] Tool carregada: {name} ({len(cmds)} comandos)")
    
    def auto_discover(self):
        """Descobre todos os tools/cmd_*.py automaticamente."""
        if not TOOLS_DIR.exists():
            return
        for path in sorted(TOOLS_DIR.glob("cmd_*.py")):
            module_name = f"tools.{path.stem}"
            try:
                mod = importlib.import_module(module_name)
                self.register_module(mod)
            except Exception as e:
                print(f"[REG] ERRO ao carregar {module_name}: {e}")
    
    @staticmethod
    def parse_flags(parts):
        """Parse de flags --engine, --ref, etc."""
        flags = {
            "engine": "auto",
            "ref": [],
            "lote": 50,
            "desc": "",
            "size": 256,
            "quantity": 1,
            "seed": None,
            "parse_error": None,
        }
        numeric_flags = {
            "--size": "size",
            "--tamanho": "size",
            "--quantidade": "quantity",
            "--seed": "seed",
        }
        args = []
        i = 1
        while i < len(parts):
            t = parts[i]
            if t == '--engine' and i + 1 < len(parts):
                flags["engine"] = parts[i + 1].lower()
                i += 2
                continue
            if t in numeric_flags:
                name = numeric_flags[t]
                if i + 1 >= len(parts):
                    flags["parse_error"] = f"A flag {t} requer um número."
                    i += 1
                    continue
                try:
                    flags[name] = int(parts[i + 1])
                except ValueError:
                    flags["parse_error"] = f"Valor inválido para {t}: {parts[i + 1]}"
                i += 2
                continue
            if t == '--lote' and i + 1 < len(parts):
                try:
                    flags["lote"] = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
                continue
            if t in ('--ref', '--exemplos', '--exemplo', '--descricao'):
                is_desc = (t == '--descricao')
                i += 1
                buf = []
                while i < len(parts) and not parts[i].startswith('--'):
                    buf.append(parts[i])
                    i += 1
                raw = ' '.join(buf)
                if is_desc:
                    flags["desc"] = raw
                else:
                    flags["ref"] = [x.strip() for x in re.split(r'[;,]', raw) if x.strip()]
                continue
            args.append(t)
            i += 1
        return args, flags
    
    def create_approval(
        self, title, summary, details, callback, on_reject=None,
        files=None, selection_callback=None, persistent=False,
        workspace_action=None,
    ):
        """Armazena uma ação pendente e retorna apenas os dados exibidos na UI."""
        now = time.time()
        request_id = secrets.token_urlsafe(24)
        with self._approval_lock:
            expired = [
                key for key, item in self.pending_approvals.items()
                if item["expires_at"] <= now
            ]
            for key in expired:
                self.pending_approvals.pop(key, None)

            expires_at = now + 600
            self.pending_approvals[request_id] = {
                "callback": callback,
                "selection_callback": selection_callback,
                "on_reject": on_reject,
                "expires_at": expires_at,
                "public": {
                    "id": request_id,
                    "title": title,
                    "summary": summary,
                    "details": details,
                    "files": list(files or []),
                    "expires_at": expires_at,
                    "persistent": bool(persistent),
                    "workspace_action": workspace_action,
                },
            }
            public_data = self.pending_approvals[request_id]["public"]

        return public_data

    def list_pending_approvals(self):
        now = time.time()
        with self._approval_lock:
            expired = [
                key for key, item in self.pending_approvals.items()
                if item["expires_at"] <= now
            ]
            for key in expired:
                self.pending_approvals.pop(key, None)
            return [item["public"] for item in self.pending_approvals.values()]

    def resolve_approval(self, request_id, approved, selected_files=None):
        """Consome a decisão uma única vez antes de executar a ação."""
        with self._approval_lock:
            pending = self.pending_approvals.get(request_id)

            if pending is None:
                return {"status": "expired", "response": "Esta solicitação expirou ou já foi decidida."}
            if pending["expires_at"] <= time.time():
                self.pending_approvals.pop(request_id, None)
                return {"status": "expired", "response": "Esta solicitação expirou ou já foi decidida."}
            if not isinstance(approved, bool):
                return {"status": "error", "response": "A decisão de aprovação é inválida."}

            selection_callback = pending.get("selection_callback")
            if approved and selection_callback is not None:
                available_files = pending["public"]["files"]
                if (
                    not isinstance(selected_files, list)
                    or not all(isinstance(item, str) for item in selected_files)
                    or not set(selected_files).issubset(available_files)
                ):
                    return {
                        "status": "error",
                        "retryable": True,
                        "response": "Selecione somente arquivos exibidos nesta solicitação.",
                    }
                if not selected_files:
                    return {
                        "status": "error",
                        "retryable": True,
                        "response": "Selecione ao menos um arquivo ou negue a solicitação.",
                    }
                selected_files = list(dict.fromkeys(selected_files))

            self.pending_approvals.pop(request_id, None)

        if not approved:
            on_reject = pending.get("on_reject")
            if on_reject:
                on_reject()
            return {"status": "denied", "response": "Ação cancelada. Nenhuma alteração foi executada."}

        try:
            if pending.get("selection_callback") is not None:
                result = pending["selection_callback"](selected_files)
            else:
                result = pending["callback"]()
        except Exception as e:
            return {"status": "error", "response": f"Falha ao executar a ação aprovada: {e}"}
        return result if isinstance(result, dict) else {
            "status": "success",
            "response": str(result or "Ação concluída."),
        }

    def request_approval_and_wait(self, title, summary, details, action, timeout=600):
        """Waits for a one-time user decision before running a background action."""
        decision = threading.Event()
        outcome = {}

        def execute():
            try:
                outcome["result"] = action()
                outcome["approved"] = True
                return {
                    "status": "success",
                    "response": str(outcome["result"] or "Ação concluída."),
                }
            except Exception as exc:
                outcome["error"] = str(exc)
                raise
            finally:
                decision.set()

        def reject():
            outcome["approved"] = False
            decision.set()

        permission = self.create_approval(
            title=title,
            summary=summary,
            details=details,
            callback=execute,
            on_reject=reject,
        )
        if not decision.wait(timeout):
            self.resolve_approval(permission["id"], False)
            return False, "A solicitação expirou; nenhuma alteração foi executada."
        return bool(outcome.get("approved")), outcome.get("result", outcome.get("error"))

    def dispatch(
        self,
        prompt,
        approved=False,
        expected_resource_path=_APPROVAL_RESOURCE_UNBOUND,
    ):
        """Dispatch de comandos."""
        parts = prompt.split()
        if not parts:
            return None
        entry = self.commands.get(parts[0].lower())
        if not entry:
            return None

        command = parts[0].lower()
        capability = entry.get("capability", "confirm")
        args, flags = self.parse_flags(parts)
        if flags.get("parse_error"):
            return {
                "response": f"⚠️ {flags['parse_error']}",
                "thinking": "Argumento numérico inválido.",
                "status": "error",
            }
        if command == "/criar_terreno":
            preset = args[0].lower() if args else "colinas"
            if preset not in {"planicies", "colinas", "montanhas", "ilha"}:
                return {
                    "response": "Preset inválido. Use planicies, colinas, montanhas ou ilha.",
                    "thinking": "Preset fora da lista permitida.",
                    "status": "error",
                }
            if flags["size"] not in {256, 384, 512}:
                return {
                    "response": "Tamanho inválido. Use 256, 384 ou 512 studs.",
                    "thinking": "Dimensão fora do orçamento permitido.",
                    "status": "error",
                }
        if command == "/criar_assets":
            asset_type = args[0].lower() if args else ""
            if asset_type not in {
                "casa", "torre", "arvore", "rocha",
                "cristal", "acampamento", "bau", "ponte",
            }:
                return {
                    "response": "Tipo inválido. Use casa, torre, arvore, rocha, cristal, acampamento, bau ou ponte.",
                    "thinking": "Tipo de asset fora da lista permitida.",
                    "status": "error",
                }
            if not 1 <= flags["quantity"] <= 20:
                return {
                    "response": "Quantidade inválida. Use um valor entre 1 e 20.",
                    "thinking": "Quantidade fora do limite permitido.",
                    "status": "error",
                }
        if flags.get("seed") is not None and not 0 <= flags["seed"] <= 2_147_483_647:
            return {
                "response": "Seed inválida. Use um inteiro entre 0 e 2147483647.",
                "thinking": "Seed fora do limite permitido.",
                "status": "error",
            }
        resource_path = getattr(self.ctx, "project_path", None)
        if command in {"/criar_terreno", "/criar_assets"} and self.ctx.game_bridge:
            engine = self.ctx.game_bridge(str(resource_path)).detect_engine()
            if engine == "roblox" or (
                engine not in {"godot", "web"} and self.ctx.plugin_bridge
            ):
                capability = "studio"
        if capability == "project_create":
            projects_root = Path(
                getattr(self.ctx, "projects_root", resource_path.parent if resource_path else TOOLS_DIR)
            )
            default_name = "NovoJogo" if command == "/criar_automaticamente" else "Ecos_de_Aethelgard"
            name = re.sub(r'[^\w\-]', '_', args[1]) if len(args) > 1 else default_name
            resource_path = projects_root / name

        if expected_resource_path is not _APPROVAL_RESOURCE_UNBOUND:
            current_resource_path = (
                Path(resource_path).resolve() if resource_path is not None else None
            )
            approved_path = (
                Path(expected_resource_path).resolve()
                if expected_resource_path is not None
                else None
            )
            if current_resource_path != approved_path:
                return {
                    "response": "O projeto ativo mudou desde a solicitação; nenhuma ação foi executada.",
                    "thinking": "O destino não corresponde ao destino aprovado.",
                    "status": "error",
                }

        validator = entry.get("validate")
        if validator is not None:
            try:
                validator(self.ctx, args, flags)
            except (OSError, ValueError) as exc:
                return {
                    "response": f"Comando inválido: {exc}",
                    "thinking": "A validação dos argumentos falhou.",
                    "status": "error",
                }

        policy = getattr(self.ctx, "permission_policy", None)
        approval_capability = (
            "network"
            if command == "/construir_jogo" and flags["ref"]
            else capability
        )
        if policy is not None:
            requires_approval = (
                policy.requires_approval(capability, resource_path)
                or approval_capability == "network"
            )
        else:
            requires_approval = approval_capability not in {"read", "control"}

        if requires_approval and not approved:
            capability_label = {
                "project_write": "Alterar arquivos no projeto",
                "project_create": "Criar projeto",
                "network": "Acessar a rede",
                "studio": "Interagir com o Roblox Studio",
                "execute": "Executar código do projeto",
                "overwrite": "Substituir arquivo existente",
                "system": "Executar ação do sistema",
            }.get(approval_capability, "Executar ferramenta")
            resource_details = f"\nDestino: {resource_path}" if resource_path else ""
            approval = self.create_approval(
                title="Permissão necessária",
                summary=f"{capability_label}: {entry['desc']}",
                details=f"Comando solicitado: {prompt}{resource_details}",
                callback=lambda: self.dispatch(
                    prompt,
                    approved=True,
                    expected_resource_path=resource_path,
                ),
            )
            return {
                "response": "O Kael precisa da sua autorização antes de executar esta ação.",
                "thinking": "",
                "status": "permission_required",
                "permission": approval,
            }

        try:
            return entry["handler"](self.ctx, args, flags)
        except Exception as e:
            return {
                "response": f"[ERRO] Falha no comando `{parts[0]}`: {e}",
                "thinking": f"Exceção no handler: {e}",
                "status": "error"
            }
    
    def help_text(self):
        """Gera texto de ajuda."""
        lines = ["📖 **Comandos disponíveis:**"]
        by_tool = {}
        for cmd, info in self.commands.items():
            by_tool.setdefault(info["tool"], []).append((cmd, info["desc"]))
        for tool, cmds in sorted(by_tool.items()):
            lines.append(f"\n**[{tool}]**")
            for cmd, desc in sorted(cmds):
                lines.append(f"`{cmd}` — {desc}")
        return "\n".join(lines)
    
    # ========== HANDLERS ==========
    
    def _cmd_status(self, ctx, args, flags):
        mem_files = list(ctx.memory_dir.glob('*')) if ctx.memory_dir.exists() else []
        return {
            "response": (
                "✅ **Status do Sistema Kael v5.3**\n"
                f"- **Servidor API:** Online (porta 8000)\n"
                f"- **Ollama:** {'🟢 Online' if ctx.ollama_online() else '🔴 Offline'}\n"
                f"- **Memória Vetorial:** {'🟢 Ativa' if ctx.memory else '🟡 Desativada'}\n"
                f"- **Compressor:** {'🟢 Ativo' if ctx.compressor else '🟡 Desativado'}\n"
                f"- **Game Bridge:** {'🟢 Ativo' if ctx.game_bridge else '🔴 Desativado'}\n"
                f"- **Web Research:** {'🟢 Ativo' if ctx.web_research else '🔴 Desativado'}\n"
                f"- **Plugin Bridge:** {'🟢 Conectado' if ctx.plugin_bridge else '🔴 Desconectado'}\n"
                f"- **Arquivos na Memória:** {len(mem_files)}\n"
                f"- **Projeto Ativo:** `{ctx.project_path.name}`\n"
                f"- **Modo Autônomo:** {'🟢 ATIVO' if ctx.autonomous['active'] else '⚪ Inativo'}"
            ),
            "thinking": "Comando /status executado.",
            "status": "success"
        }
    
    def _cmd_teste_conexao(self, ctx, args, flags):
        ok = ctx.ollama_online()
        studio_ok = ctx.plugin_bridge is not None
        return {
            "response": (
                "📡 **Teste de Conexão**\n"
                f"- Ollama (8080): {'🟢 Respondendo' if ok else '🔴 Offline'}\n"
                "- API Kael (8000): 🟢 Respondendo\n"
                f"- Roblox Studio: {'🟢 Conectado' if studio_ok else '🔴 Desconectado'}"
            ),
            "thinking": "Ping executado.",
            "status": "success" if ok else "error"
        }
    
    def _cmd_help(self, ctx, args, flags):
        return {
            "response": self.help_text(),
            "thinking": "Menu de ajuda.",
            "status": "success"
        }
    
    def _cmd_gerenciar_jogo(self, ctx, args, flags):
        project = args[0] if args else "Ecos_de_Aethelgard"
        ctx.autonomous["active"] = True
        ctx.autonomous["project"] = project
        return {
            "response": f"🤖 **Modo Autônomo ATIVADO** em `{project}`.",
            "thinking": "Estado global alterado.",
            "status": "success"
        }
    
    def _cmd_parar_gerenciamento(self, ctx, args, flags):
        ctx.autonomous["active"] = False
        return {
            "response": "⏹️ **Modo Autônomo DESATIVADO.**",
            "thinking": "Modo autônomo desligado.",
            "status": "success"
        }
    
    def _cmd_ver_jogo(self, ctx, args, flags):
        if not ctx.game_bridge:
            return {"response": "🔴 Game Bridge indisponível.", "thinking": "Módulo ausente.", "status": "error"}
        bridge = ctx.game_bridge(str(ctx.project_path))
        report = bridge.full_report()
        if 'erro' in report:
            return {"response": f"⚠️ {report['erro']}", "thinking": "Projeto não encontrado.", "status": "error"}
        scripts_txt = "\n".join([f"- `{s['arquivo']}` ({s['linhas']} linhas)" for s in report['scripts'][:10]]) or "- (nenhum script)"
        prob_txt = "\n".join([f"- ⚠️ [{p['tipo']}] {p['arquivo']}: {p['detalhe']}" for p in report['problemas'][:10]]) if report['problemas'] else "- ✅ Nenhum problema estático detectado"
        return {
            "response": (
                f"👁️ **Análise Real do Projeto: {ctx.project_path.name}**\n"
                f"- **Motor detectado:** {report['motor']}\n"
                f"- **Scripts:** {report['total_scripts']}\n{scripts_txt}\n"
                f"- **Documentos:** {', '.join(report['documentos']) or 'nenhum'}\n"
                f"- **Cenas:** {len(report['cenas'])}\n\n"
                f"**Problemas detectados:**\n{prob_txt}"
            ),
            "thinking": "Análise estática real executada pelo GameBridge.",
            "status": "success"
        }

    @staticmethod
    def _roblox_studio_error(ctx):
        if not ctx.plugin_bridge:
            return "Plugin do Roblox Studio não conectado."
        if not ctx.plugin_bridge.studio_conectado():
            return "O Studio ainda não enviou um estado recente. Use Mapear Cena e inicie o polling."
        if ctx.game_bridge:
            engine = ctx.game_bridge(str(ctx.project_path)).detect_engine()
            if engine in {"godot", "web"}:
                return f"O projeto ativo foi detectado como {engine}; esta ação tipada é exclusiva do Roblox."
        return None

    def _propor_mudanca_de_jogo(self, ctx, kind, engine, descriptor, flags):
        project_bridge = ctx.game_bridge(str(ctx.project_path))
        report = project_bridge.full_report()
        if "erro" in report:
            return {
                "response": f"⚠️ {report['erro']}",
                "thinking": "Projeto não encontrado.",
                "status": "error",
            }
        documents = project_bridge.read_docs(max_chars=2000)
        if kind == "terrain" and engine == "godot":
            files = "Scenes/KaelTerrain.tscn e Scripts/KaelTerrain.gd"
            requirements = (
                "Crie uma cena 3D de terreno procedural determinístico, com seed e orçamento "
                "de até 1.024 células/segmentos. A cena deve instanciar o script e ser utilizável "
                "ao ser instanciada em outra cena do projeto. Evite loops sem limite."
            )
        elif kind == "terrain":
            files = "index.html, js/kael_terrain.js e tests/kael_terrain.test.js"
            requirements = (
                "Crie um terreno procedural renderizado no canvas, determinístico pela seed, "
                "com dimensão limitada e controles acessíveis. Integre-o à página inicial. "
                "Inclua testes node:test que carreguem o módulo real no sistema já usado pelo projeto "
                "e verifiquem limites, seed e resultado; não use dependências externas nem rede."
            )
        elif engine == "godot":
            files = f"Scenes/KaelAsset_{descriptor}.tscn"
            requirements = (
                "Crie uma cena 3D estática e leve para esse asset, com colisão apropriada, "
                "dimensões coerentes, usando a quantidade solicitada, e sem scripts, rede ou recursos externos. "
                "A cena deve poder ser instanciada no projeto."
            )
        else:
            files = (
                f"assets/kael_{descriptor}.svg, js/kael_assets.js e "
                f"tests/kael_asset_{descriptor}.test.js"
            )
            requirements = (
                "Crie um asset SVG estático seguro e um módulo JavaScript pequeno para carregá-lo "
                "no jogo, integrando-o sem dependências externas e respeitando a quantidade solicitada. "
                "Inclua testes node:test que leiam "
                "o SVG real e verifiquem estrutura e ausência de script/foreignObject; não use rede."
            )

        prompt = (
            f"Proponha uma implementação de {kind} para o projeto {ctx.project_path.name} "
            f"(motor {engine}). Descrição/preset: {descriptor}. Seed: {flags['seed']}. "
            f"Dimensão solicitada: {flags['size']} studs. Quantidade: {flags['quantity']}. Arquivos-alvo: {files}. "
            f"{requirements}\n"
            "Use o GDD e o inventário abaixo para evitar duplicar conteúdo existente. "
            "Não modifique arquivos não relacionados; mantenha o código compatível com a versão "
            "do motor indicada. Não use eval, subprocessos, acesso à rede ou escrita arbitrária "
            "no sistema de arquivos.\n"
            "Retorne somente arquivos completos em tags <kael_save filename='caminho/relativo'>conteúdo"
            "</kael_save>, sem texto adicional. A gravação só ocorrerá depois que o runner compatível "
            "passar e o usuário aprovar o segundo cartão.\n\n"
            f"Inventário: scripts={report.get('scripts', [])[:30]}, "
            f"cenas={report.get('cenas', [])[:30]}, documentos={report.get('documentos', [])[:30]}.\n"
            f"GDD/documentação:\n{documents[:2000]}"
        )
        generated = ctx.generate(prompt)
        generated_text = generated.get("response", "")
        if "<kael_save" not in generated_text:
            return {
                "response": "A proposta não contém arquivos completos para validar. Nenhuma alteração foi feita.",
                "thinking": generated.get("thinking", ""),
                "status": "error",
            }
        validation = ctx.process_save_commands(
            generated_text,
            save_dir=ctx.project_path,
        )
        status = (
            "pending_approval" if "[AGUARDANDO TESTE E APROVAÇÃO:" in validation
            else "blocked" if "[ALTERAÇÃO BLOQUEADA:" in validation or "TESTES FALHARAM" in validation
            else "error"
        )
        return {
            "response": f"🧪 **Proposta de {kind} para {engine}:**\n\n{validation}",
            "thinking": generated.get("thinking", "Proposta submetida ao fluxo central de validação."),
            "status": status,
        }

    def _cmd_criar_terreno(self, ctx, args, flags):
        engine = ctx.game_bridge(str(ctx.project_path)).detect_engine() if ctx.game_bridge else "desconhecido"
        preset = args[0].lower() if args else "colinas"
        if preset not in {"planicies", "colinas", "montanhas", "ilha"}:
            return {
                "response": "Preset inválido. Use planicies, colinas, montanhas ou ilha.",
                "thinking": "Preset de terreno fora da lista permitida.",
                "status": "error",
            }
        if flags["size"] not in {256, 384, 512}:
            return {
                "response": "Tamanho inválido. Use 256, 384 ou 512 studs.",
                "thinking": "Dimensão fora do orçamento permitido.",
                "status": "error",
            }
        if engine in {"godot", "web"}:
            seed = flags["seed"] if flags["seed"] is not None else secrets.randbelow(2_147_483_648)
            flags = {**flags, "seed": seed}
            return self._propor_mudanca_de_jogo(ctx, "terrain", engine, preset, flags)
        error = self._roblox_studio_error(ctx)
        if error:
            return {
                "response": f"⛔ {error} Nenhuma alteração foi enviada.",
                "thinking": "Ação de terreno exige Roblox Studio conectado e projeto compatível.",
                "status": "error",
            }
        seed = flags["seed"] if flags["seed"] is not None else secrets.randbelow(2_147_483_648)
        task = ctx.plugin_bridge.enqueue({
            "tipo": "gerar_terreno",
            "preset": preset,
            "size": flags["size"],
            "seed": seed,
        })
        return {
            "response": (
                f"⛰️ **Geração de terreno solicitada** (tarefa `{task['task_id']}`).\n"
                f"- Preset: `{preset}` | área: {flags['size']}×{flags['size']} studs | seed: `{seed}`\n"
                "- Limite de até 1.024 colunas; a região anterior é guardada em backup antes da escrita.\n"
                "- Esta ação cria Terrain nativo, não executa nem grava scripts Luau.\n"
                "Após concluir, use `/resultado_criacao`; para reverter, use `/desfazer_terreno <backup_id>`."
            ),
            "thinking": "Ação tipada de terreno enviada após autorização.",
            "status": "success",
        }

    def _cmd_criar_assets(self, ctx, args, flags):
        engine = ctx.game_bridge(str(ctx.project_path)).detect_engine() if ctx.game_bridge else "desconhecido"
        if engine in {"godot", "web"}:
            asset_type = args[0].lower() if args else ""
            if asset_type not in {
                "casa", "torre", "arvore", "rocha",
                "cristal", "acampamento", "bau", "ponte",
            }:
                return {
                    "response": "Tipo inválido. Use casa, torre, arvore, rocha, cristal, acampamento, bau ou ponte.",
                    "thinking": "Tipo de asset fora da lista permitida.",
                    "status": "error",
                }
            seed = flags["seed"] if flags["seed"] is not None else secrets.randbelow(2_147_483_648)
            flags = {**flags, "seed": seed}
            return self._propor_mudanca_de_jogo(ctx, "asset", engine, asset_type, flags)
        error = self._roblox_studio_error(ctx)
        if error:
            return {
                "response": f"⛔ {error} Nenhuma alteração foi enviada.",
                "thinking": "Geração de assets exige Roblox Studio conectado e projeto compatível.",
                "status": "error",
            }
        asset_type = args[0].lower() if args else ""
        seed = flags["seed"] if flags["seed"] is not None else secrets.randbelow(2_147_483_648)
        task = ctx.plugin_bridge.enqueue({
            "tipo": "criar_assets",
            "asset_type": asset_type,
            "quantity": flags["quantity"],
            "seed": seed,
        })
        return {
            "response": (
                f"🧱 **Criação de assets solicitada** (tarefa `{task['task_id']}`).\n"
                f"- Tipo: `{asset_type}` | quantidade: {flags['quantity']} | seed: `{seed}`\n"
                "- São modelos estáticos de peças ancoradas, agrupados em `Workspace/Kael_GeneratedAssets`.\n"
                "A ação não cria nem executa scripts. Tipos: `arvore`, `casa`, `torre`, `rocha`, `cristal`, "
                "`acampamento`, `bau` e `ponte`. Após concluir, use `/resultado_criacao`."
            ),
            "thinking": "Ação tipada de criação de assets enviada após autorização.",
            "status": "success",
        }

    def _cmd_desfazer_terreno(self, ctx, args, flags):
        error = self._roblox_studio_error(ctx)
        if error:
            return {
                "response": f"⛔ {error} Nenhuma alteração foi enviada.",
                "thinking": "Restauração de terreno exige Roblox Studio conectado.",
                "status": "error",
            }
        if not args:
            return {
                "response": "Informe o backup exibido em `/resultado_criacao`: `/desfazer_terreno KaelTerrainBackup_1234abcd`.",
                "thinking": "Identificador do backup ausente.",
                "status": "error",
            }
        task = ctx.plugin_bridge.enqueue({
            "tipo": "restaurar_terreno",
            "backup_id": args[0],
        })
        return {
            "response": (
                f"↩️ **Restauração de terreno solicitada** (tarefa `{task['task_id']}`) "
                f"usando o backup `{args[0]}`. Consulte `/resultado_criacao` ao concluir."
            ),
            "thinking": "Ação tipada para restaurar o backup de terreno.",
            "status": "success",
        }

    def _cmd_remover_assets_kael(self, ctx, args, flags):
        error = self._roblox_studio_error(ctx)
        if error:
            return {
                "response": f"⛔ {error} Nenhuma alteração foi enviada.",
                "thinking": "Backup de assets exige Roblox Studio conectado.",
                "status": "error",
            }
        task = ctx.plugin_bridge.enqueue({"tipo": "backup_assets_kael"})
        return {
            "response": (
                f"📦 **Backup dos assets do Kael solicitado** (tarefa `{task['task_id']}`). "
                "Os modelos serão movidos, sem exclusão, para `ServerStorage/Kael_BackupWorld`. "
                "Use `/resultado_criacao` e depois `/desfazer_assets_kael <backup_id>` para restaurar."
            ),
            "thinking": "Ação tipada para guardar os assets em backup.",
            "status": "success",
        }

    def _cmd_desfazer_assets_kael(self, ctx, args, flags):
        error = self._roblox_studio_error(ctx)
        if error:
            return {
                "response": f"⛔ {error} Nenhuma alteração foi enviada.",
                "thinking": "Restauração de assets exige Roblox Studio conectado.",
                "status": "error",
            }
        if not args:
            return {
                "response": "Informe o backup exibido em `/resultado_criacao`: `/desfazer_assets_kael KaelAssetsBackup_1234abcd`.",
                "thinking": "Identificador do backup ausente.",
                "status": "error",
            }
        task = ctx.plugin_bridge.enqueue({
            "tipo": "restaurar_assets_kael",
            "backup_id": args[0],
        })
        return {
            "response": (
                f"↩️ **Restauração de assets solicitada** (tarefa `{task['task_id']}`) "
                f"usando o backup `{args[0]}`. Consulte `/resultado_criacao` ao concluir."
            ),
            "thinking": "Ação tipada para restaurar assets do backup.",
            "status": "success",
        }

    def _cmd_resultado_criacao(self, ctx, args, flags):
        if not ctx.plugin_bridge:
            return {
                "response": "Plugin do Studio não conectado.",
                "thinking": "Plugin bridge ausente.",
                "status": "error",
            }
        if args:
            if not re.fullmatch(r"[a-f0-9]{32}", args[0]):
                return {
                    "response": "task_id inválido. Use o identificador exibido quando a tarefa foi solicitada.",
                    "thinking": "Formato de task_id inválido.",
                    "status": "error",
                }
            task = ctx.plugin_bridge.get_task(args[0])
            if not task:
                return {
                    "response": f"Tarefa `{args[0]}` não encontrada ou expirada.",
                    "thinking": "Histórico da tarefa indisponível.",
                    "status": "error",
                }
            completion = task.get("completion")
            if completion is None:
                return {
                    "response": f"Tarefa `{args[0]}` ainda está `{task['status']}`.",
                    "thinking": "A tarefa ainda não foi concluída pelo plugin.",
                    "status": "pending",
                }
        else:
            completion = getattr(ctx.plugin_bridge, "last_completion", None)
        supported = {
            "gerar_terreno", "criar_assets", "restaurar_terreno",
            "backup_assets_kael", "restaurar_assets_kael",
        }
        if not completion or completion.get("tipo") not in supported:
            return {
                "response": "Nenhuma criação de terreno ou asset foi concluída ainda.",
                "thinking": "Sem resultado de criação no plugin.",
                "status": "success",
            }
        if not completion.get("sucesso"):
            return {
                "response": f"❌ A tarefa `{completion.get('tipo')}` falhou: {completion.get('erro') or 'erro não informado'}.",
                "thinking": "O plugin informou falha na tarefa.",
                "status": "error",
            }
        result = completion.get("resultado", {})
        if completion["tipo"] == "gerar_terreno":
            details = (
                f"Preset `{result.get('preset')}`, área {result.get('size')}×{result.get('size')} studs, "
                f"{result.get('columns')} colunas e seed `{result.get('seed')}`.\n"
                f"Backup para desfazer: `{result.get('backup_id')}`."
            )
        elif completion["tipo"] == "criar_assets":
            names = ", ".join(result.get("names", [])[:10])
            details = (
                f"Tipo `{result.get('asset_type')}`: {result.get('quantity', 0)} modelo(s) criado(s)"
                + (f" — {names}" if names else "")
                + "."
            )
        else:
            if completion["tipo"] == "backup_assets_kael":
                details = (
                    f"{result.get('models', 0)} modelo(s) guardado(s) em backup "
                    f"`{result.get('backup_id') or 'nenhum asset encontrado'}`."
                )
            elif completion["tipo"] == "restaurar_assets_kael":
                details = f"Backup de assets `{result.get('backup_id')}` restaurado."
            else:
                details = f"Backup `{result.get('backup_id')}` restaurado."
        return {
            "response": f"✅ **Resultado do Studio:**\n{details}",
            "thinking": "Resultado confirmado pelo plugin Roblox.",
            "status": "success",
        }

    def _cmd_avaliar_criacao(self, ctx, args, flags):
        if not ctx.game_bridge:
            return {
                "response": "🔴 Game Bridge indisponível.",
                "thinking": "Módulo ausente.",
                "status": "error",
            }
        bridge = ctx.game_bridge(str(ctx.project_path))
        report = bridge.full_report()
        if "erro" in report:
            return {
                "response": f"⚠️ {report['erro']}",
                "thinking": "Projeto não encontrado.",
                "status": "error",
            }
        scripts = [
            {"arquivo": item["arquivo"], "linhas": item["linhas"]}
            for item in report.get("scripts", [])[:30]
        ]
        problems = [
            {
                "tipo": item.get("tipo", "desconhecido"),
                "arquivo": item.get("arquivo", ""),
                "detalhe": item.get("detalhe", "")[:240],
            }
            for item in report.get("problemas", [])[:30]
        ]
        plugin_state = getattr(ctx.plugin_bridge, "last_state", None) if ctx.plugin_bridge else None
        scene = []
        terrain = None
        if (
            isinstance(plugin_state, dict)
            and ctx.plugin_bridge.studio_conectado()
        ):
            scene = [
                {"nome": item.get("nome", ""), "classe": item.get("classe", "")}
                for item in plugin_state.get("instancias", [])[:40]
                if isinstance(item, dict)
            ]
            terrain = plugin_state.get("terreno")
        prompt = (
            "Avalie melhorias para este jogo como produtor técnico. Use apenas as evidências abaixo; "
            "não invente objetos, testes ou funcionalidades existentes. Não gere código nem tags de gravação. "
            "Separe: (1) mudanças que valem a pena, (2) ideias que não valem o custo agora, "
            "(3) scripts, assets e terreno, (4) riscos de desempenho, (5) testes necessários antes de qualquer gravação. "
            "Para cada proposta dê benefício ao jogador, custo, risco, evidência e um teste verificável. "
            "Diga explicitamente quando faltarem evidências. Pontue valor de 0 a 10, mas não trate a pontuação "
            "como aprovação para alterar o projeto. Esta avaliação não executa testes; apresente apenas um plano "
            "de testes e nunca afirme que uma proposta já foi validada.\n\n"
            f"Projeto: {ctx.project_path.name}\n"
            f"Motor: {report.get('motor', 'desconhecido')}\n"
            f"Scripts: {scripts}\n"
            f"Problemas estáticos: {problems}\n"
            f"Documentos: {report.get('documentos', [])[:30]}\n"
            f"Cenas: {report.get('cenas', [])[:30]}\n"
            f"Estado recente do Studio (nomes/classes, sem conteúdo de scripts): {scene or 'indisponível'}\n"
            f"Amostra de terreno em torno do spawn: {terrain or 'indisponível'}\n"
            "Respeite a plataforma: alterações Luau continuam bloqueadas sem runner compatível; "
            "Godot/web devem seguir os testes e a aprovação do fluxo central."
        )
        result = ctx.generate(prompt)
        return {
            "response": f"🔎 **Avaliação de criação — {ctx.project_path.name} ({report.get('motor', 'desconhecido')})**\n\n{result['response']}",
            "thinking": result.get("thinking", "Avaliação baseada no inventário do projeto."),
            "status": "success",
        }
    
    def _cmd_integrar_jogo(self, ctx, args, flags):
        if not ctx.game_bridge:
            return {"response": "🔴 Game Bridge indisponível.", "thinking": "Módulo ausente.", "status": "error"}
        bridge = ctx.game_bridge(str(ctx.project_path))
        scan = bridge.scan_project()
        if 'erro' in scan or not scan['scripts']:
            return {"response": "⚠️ Nenhum script encontrado.", "thinking": "Sem scripts.", "status": "error"}
        trechos = []
        for s in scan['scripts'][:3]:
            texto = (ctx.project_path / s['arquivo']).read_text(encoding='utf-8', errors='ignore')[:2000]
            trechos.append(f"=== {s['arquivo']} ===\n{texto}")
        prompt_ia = (
            f"Analise os scripts do projeto {ctx.project_path.name} (motor: {scan['motor']}). "
            f"Identifique bugs e melhore a integração. Para cada script corrigido, gere o código "
            f"completo dentro da tag: <kael_save filename='Scripts/NOME_fix.ext'>código</kael_save>\n\n"
            + "\n\n".join(trechos)
        )
        resultado = ctx.generate(prompt_ia)
        resposta = ctx.process_save_commands(resultado['response'], save_dir=ctx.project_path)
        save_status = (
            "pending_approval" if "[AGUARDANDO TESTE E APROVAÇÃO:" in resposta
            else "blocked" if "[ALTERAÇÃO BLOQUEADA:" in resposta
            else "success"
        )
        return {
            "response": f"🔧 **Integração analisada.** Resultado da validação:\n\n{resposta}",
            "thinking": resultado.get('thinking', ''),
            "status": save_status
        }
    
    def _cmd_refatorar(self, ctx, args, flags):
        if not ctx.game_bridge:
            return {"response": "🔴 Game Bridge indisponível.", "thinking": "Módulo ausente.", "status": "error"}
        bridge = ctx.game_bridge(str(ctx.project_path))
        scan = bridge.scan_project()
        if 'erro' in scan or not scan['scripts']:
            return {"response": "⚠️ Nenhum script encontrado.", "thinking": "Sem scripts.", "status": "error"}
        maior = max(scan['scripts'], key=lambda s: s['linhas'])
        p = ctx.project_path / maior['arquivo']
        texto = p.read_text(encoding='utf-8', errors='ignore')[:6000]
        novo_nome = f"Scripts/{Path(maior['arquivo']).stem}_refatorado{Path(maior['arquivo']).suffix}"
        prompt_ia = (
            f"Refatore o script abaixo (motor {scan['motor']}) para ficar limpo e modular. "
            f"Salve com: <kael_save filename='{novo_nome}'>código</kael_save>\n\n{texto}"
        )
        resultado = ctx.generate(prompt_ia)
        resposta = ctx.process_save_commands(resultado['response'], save_dir=ctx.project_path)
        save_status = (
            "pending_approval" if "[AGUARDANDO TESTE E APROVAÇÃO:" in resposta
            else "blocked" if "[ALTERAÇÃO BLOQUEADA:" in resposta
            else "success"
        )
        return {
            "response": f"♻️ **Refatoração analisada.** Resultado da validação para `{novo_nome}`:\n\n{resposta}",
            "thinking": resultado.get('thinking', ''),
            "status": save_status
        }
    
    def _cmd_construir_jogo(self, ctx, args, flags):
        if not ctx.game_bridge:
            return {"response": "🔴 Game Bridge indisponível.", "thinking": "Módulo ausente.", "status": "error"}
        genero = args[0] if len(args) > 0 else 'aventura'
        nome = re.sub(r'[^\w\-]', '_', args[1]) if len(args) > 1 else 'Ecos_de_Aethelgard'
        proj_dir = getattr(ctx, "projects_root", ctx.project_path.parent) / nome
        bridge = ctx.game_bridge(str(proj_dir))
        info = bridge.create_project_structure(nome, genero, flags['engine'])
        templates_response = ""
        if info.get("template_files"):
            from tools.game_bridge import template_save_commands
            templates_response = ctx.process_save_commands(
                template_save_commands(info["template_files"]),
                save_dir=proj_dir,
            )
        base_pesquisa = ""
        if flags['ref'] and ctx.web_research:
            base_pesquisa = ctx.web_research().research_genre(genero, flags['ref'])
        gdd_prompt = (
            f"Crie um GDD conciso para um jogo de {genero} chamado {nome} (motor: {info['engine']}). "
            f"Inclua: visão geral, mecânicas principais, progressão, direção de arte e som. "
        )
        if base_pesquisa:
            gdd_prompt += f"\n\nBASE DE PESQUISA REAL:\n{base_pesquisa[:4000]}\n"
        gdd_prompt += f"Salve com: <kael_save filename='Docs/GDD.md'>conteúdo</kael_save>"
        resultado = ctx.generate(gdd_prompt)
        resposta_gdd = ctx.process_save_commands(resultado['response'], save_dir=proj_dir)
        msg = (
            f"🏗️ **Projeto `{nome}` criado!**\n"
            f"- **Motor:** {info['engine']}\n"
            f"- Pastas: {', '.join(info['pastas'])}\n"
            f"- Templates: {', '.join(info['templates']) or 'nenhum'}\n"
        )
        if templates_response:
            msg += f"\n**Validação dos scripts:** {templates_response}\n"
        if flags['ref']:
            msg += f"- **Referências pesquisadas:** {', '.join(flags['ref'])}\n"
        msg += f"\n{resposta_gdd}"
        save_status = (
            "pending_approval" if "[AGUARDANDO TESTE E APROVAÇÃO:" in templates_response
            else "blocked" if "[ALTERAÇÃO BLOQUEADA:" in templates_response
            else "success"
        )
        return {
            "response": msg,
            "thinking": resultado.get('thinking', ''),
            "status": save_status,
        }
    
    def _cmd_pesquisar_jogos(self, ctx, args, flags):
        if not ctx.web_research:
            return {"response": "🔴 Web Research indisponível.", "thinking": "Módulo ausente.", "status": "error"}
        genero = args[0] if args else 'aventura'
        exemplos = flags['ref']
        pesquisa = ctx.web_research().research_genre(genero, exemplos)
        if not pesquisa:
            return {"response": "⚠️ Nenhuma informação encontrada.", "thinking": "Pesquisa web retornou vazio.", "status": "error"}
        docs_dir = ctx.project_path / 'Docs'
        if not docs_dir.exists():
            docs_dir = ctx.memory_dir
        genero_slug = re.sub(r'[^\w\-]', '_', genero)
        fname = f"PESQUISA_{genero_slug}.md"
        try:
            (docs_dir / fname).write_text(pesquisa, encoding='utf-8')
        except Exception as e:
            print(f"[ERRO] Ao salvar pesquisa: {e}")
        return {
            "response": f"🌐 **Pesquisa concluída!** Relatório salvo em `{docs_dir.name}/{fname}`.\n\n**Descobertas principais:**\n{pesquisa[:1500]}",
            "thinking": "Pesquisa web real executada.",
            "status": "success"
        }
    
    def _cmd_limpar_flutuantes(self, ctx, args, flags):
        """Envia limpeza direto ao Roblox Studio + salva cópia local."""
        modo = 'ANALISAR' if '--analisar' in args else 'REMOVER'
        backup = '--sem-backup' not in args
        dist = 50
        for i, p in enumerate(args):
            if p == '--dist' and i + 1 < len(args):
                try:
                    dist = int(args[i + 1])
                except ValueError:
                    pass
        
        if not ctx.game_bridge:
            return {"response": "🔴 Game Bridge indisponível.", "thinking": "Módulo ausente.", "status": "error"}

        # Envia uma ação tipada; o plugin não executa código Lua arbitrário.
        if ctx.plugin_bridge:
            task = ctx.plugin_bridge.enqueue({
                "tipo": "limpar_flutuantes",
                "modo": modo,
                "backup": backup,
                "max_distance": dist,
            })
            return {
                "response": (
                    f"🧹 **Limpeza enfileirada no Roblox Studio** (tarefa `{task['task_id']}`).\n"
                    f"- Modo: {modo} | Backup: {'sim' if backup else 'nao'} | Alcance: {dist} studs\n"
                    f"- A tarefa usa uma ação fixa do plugin; nenhum Lua arbitrário é executado.\n\n"
                    f"Use `/resultado_limpeza` para ver quantos blocos foram removidos."
                ),
                "thinking": "Ação de limpeza tipada enviada ao plugin Roblox.",
                "status": "success"
            }
        
        return {
            "response": (
                "⛔ O Roblox Studio está desconectado. Nenhum script Luau foi salvo: "
                "não há um runner de testes compatível para validar esse código."
            ),
           "thinking": "Execução bloqueada porque não há runner de testes Luau disponível.",
           "status": "error"
        }
    
    def _cmd_resultado_limpeza(self, ctx, args, flags):
        try:
            if ctx.plugin_bridge and ctx.plugin_bridge.last_completion:
                ult = ctx.plugin_bridge.last_completion
                if ult.get('tipo') == 'limpar_flutuantes':
                    resultado = ult.get("resultado", {})
                    if not ult.get("sucesso"):
                        return {
                            "response": f"❌ A limpeza falhou: {ult.get('erro') or 'erro não informado'}",
                            "thinking": "O plugin informou falha na tarefa.",
                            "status": "error",
                        }
                    return {
                        "response": (
                            f"🧹 **Última limpeza no Studio:**\n"
                            f"- Detectados: **{resultado.get('detectados', 0)}** | Removidos: **{resultado.get('removidos', 0)}**\n"
                            f"- Modo: {resultado.get('modo', 'desconhecido')} | Backup: {resultado.get('backup', 'desconhecido')}"
                        ),
                        "thinking": "Resultado real vindo do plugin Roblox.",
                        "status": "success"
                    }
        except:
            pass
        return {"response": "Nenhuma limpeza executada ainda.", "thinking": "Sem resultados.", "status": "success"}
    
    def _cmd_corrigir_automaticamente(self, ctx, args, flags):
        """Ativa o agente autônomo para CORRIGIR erros."""
        if not ctx.autonomous_agent:
            return {"response": "🔴 Agente autônomo não disponível.", "thinking": "Módulo ausente.", "status": "error"}
        
        if not ctx.autonomous_agent.active:
            ctx.autonomous_agent.activate(mode="corrigir")
            try:
                if ctx.plugin_bridge:
                    ctx.plugin_bridge.enqueue({"tipo": "pedir_visao"})
            except:
                pass
            return {
                "response": (
                    "🤖 **Modo Autônomo de CORREÇÃO ATIVADO!**\n\n"
                    "O Kael agora vai:\n"
                    "1. Escanear o jogo automaticamente\n"
                    "2. Detectar blocos flutuantes, erros de script, etc.\n"
                    "3. Corrigir cada problema sozinho\n"
                    "4. Verificar se funcionou e repetir se necessário\n\n"
                    "Aguarde... o Kael está trabalhando no seu jogo."
                ),
                "thinking": "Agente autônomo de correção ativado.",
                "status": "success"
            }
        else:
            status = ctx.autonomous_agent.get_status()
            return {
                "response": (
                    f"🤖 **Agente Autônomo já está ativo!**\n"
                    f"- Modo: {status.get('modo', 'desconhecido')}\n"
                    f"- Iteração: {status['iteracao']}/{status['max_iteracoes']}\n"
                    f"- Tarefas pendentes: {status['tarefas_pendentes']}\n"
                    f"- Tarefas concluídas: {status['tarefas_concluidas']}"
                ),
                "thinking": "Status do agente autônomo.",
                "status": "success"
            }
    
    def _cmd_criar_automaticamente(self, ctx, args, flags):
        """Ativa o agente autônomo para CRIAR um jogo do zero."""
        if not ctx.autonomous_agent:
            return {"response": "🔴 Agente autônomo não disponível.", "thinking": "Módulo ausente.", "status": "error"}
        
        genero = args[0] if args else 'aventura'
        nome = re.sub(r'[^\w\-]', '_', args[1]) if len(args) > 1 else 'NovoJogo'
        engine = flags.get('engine', 'roblox')
        if engine == 'auto':
            engine = 'roblox'
        ref = flags.get('ref', [])
        
        if not ctx.autonomous_agent.active:
            ctx.autonomous_agent.activate(mode="criar")
            try:
                ctx.autonomous_agent.set_project(genero, nome, engine, ref)
            except Exception:
                ctx.autonomous_agent.deactivate()
                raise
            return {
                "response": (
                    f"🤖 **Modo Autônomo de CRIAÇÃO ATIVADO!**\n\n"
                    f"**Projeto:** `{nome}` ({genero} - {engine})\n"
                    f"**Referências:** {', '.join(ref) if ref else 'nenhuma'}\n\n"
                    f"**Fases do Kael:**\n"
                    f"1. 🔍 Pesquisa de mercado e referências\n"
                    f"2. 📄 Geração do GDD (Game Design Document)\n"
                    f"3. 🏗️ Criação da estrutura de pastas\n"
                    f"4. 💻 Geração dos scripts principais\n"
                    f"5. 🧪 Validação e correção automática\n"
                    f"6. 📦 Envio para o Roblox Studio via plugin\n\n"
                    f"Aguarde... o Kael está construindo seu jogo do zero!"
                ),
                "thinking": "Agente autônomo de criação ativado com projeto configurado.",
                "status": "success"
            }
        else:
            return {
                "response": "🤖 Agente já está ativo. Use `/parar_gerenciamento` antes de iniciar novo projeto.",
                "thinking": "Agente já ativo.",
                "status": "success"
            }
    
    def _cmd_organizar_jogo(self, ctx, args, flags):
        print(f"DEBUG 1 - Tipo do ctx.game_bridge: {type(ctx.game_bridge)}")
        print(f"DEBUG 2 - Tipo do ctx.plugin_bridge: {type(ctx.plugin_bridge)}")
        """Analisa o jogo e envia uma tarefa tipada de limpeza ao Studio."""
        if not ctx.plugin_bridge:
            return {
                "response": "🔴 Plugin do Studio não conectado. Abra o Roblox Studio com o plugin ativo.",
                "thinking": "Plugin bridge ausente.",
                "status": "error"
            }
        
        # Verifica se o plugin está conectado recentemente
        if not ctx.plugin_bridge.last_state_time or (time.time() - ctx.plugin_bridge.last_state_time) > 30:
            return {
                "response": "🔴 Studio não enviou estado recente. Clique em 'Mapear Cena' no plugin.",
                "thinking": "Estado do jogo desatualizado.",
                "status": "error"
            }
        
        # Analisa quantos blocos flutuantes existem
        estado = ctx.plugin_bridge.last_state or {}
        instancias = estado.get('instancias', [])
        flutuantes = [obj for obj in instancias if obj.get('y', 0) < -100]
        
        modo = 'ANALISAR' if '--analisar' in args else 'REMOVER'
        backup = '--sem-backup' not in args
        dist = 50
        for i, p in enumerate(args):
            if p == '--dist' and i + 1 < len(args):
                try:
                    dist = int(args[i + 1])
                except ValueError:
                    pass
        
        task = ctx.plugin_bridge.enqueue({
            "tipo": "limpar_flutuantes",
            "modo": modo,
            "backup": backup,
            "max_distance": dist,
        })
        
        return {
            "response": (
                f"🗂️ **Organização enfileirada** (tarefa `{task['task_id']}`).\n\n"
                f"**Análise:** {len(flutuantes)} blocos flutuantes detectados\n"
                f"- Modo: {modo} | Backup: {'sim' if backup else 'nao'} | Alcance: {dist} studs\n\n"
                f"**Ações:**\n"
                f"✅ Ação tipada enviada ao Roblox Studio. Nenhum script Luau foi gravado.\n\n"
                f"Use `/resultado_limpeza` para ver quantos blocos foram removidos."
            ),
            "thinking": f"Análise: {len(flutuantes)} flutuantes. Ação tipada enviada ao plugin.",
            "status": "success"
        }
# ========================================================================
# NOVOS HANDLERS: Memoria, Criatividade, Temperatura
# ========================================================================

    def _cmd_memoria(self, ctx, args, flags):
        """Inspeciona a memória unificada do Kael."""
        mem = getattr(ctx, "unified_memory", None)
        if mem is None:
            return {
                "response": "⚠️ Memória unificada não disponível.",
                "thinking": "Módulo unified_memory não inicializado.",
                "status": "error",
            }

        query = " ".join(args) if args else ""
        partes = []

        try:
            regras = mem.get_learned_rules(limit=10)
            if regras and regras != "Nenhuma regra aprendida ainda.":
                partes.append("### REGRAS APRENDIDAS:\n" + regras)
        except Exception as e:
            partes.append(f"### REGRAS APRENDIDAS: Erro - {e}")

        try:
            episodios = mem.get_similar_episodes(query or "geral", limit=5)
            if episodios:
                ep_lines = []
                for ep in episodios:
                    status = "✅" if ep.get("sucesso") else ("❌" if ep.get("sucesso") is False else "⚪")
                    ep_lines.append(f"{status} {ep['tipo']}: {ep['descricao'][:100]}")
                partes.append("### EPISÓDIOS SIMILARES:\n" + "\n".join(ep_lines))
        except Exception as e:
            partes.append(f"### EPISÓDIOS: Erro - {e}")

        try:
            semantic = mem.search_semantic(query or "geral", limit=5)
            if semantic:
                sem_lines = []
                for item in semantic:
                    c = item.get("content", "")[:150] if isinstance(item, dict) else str(item)[:150]
                    sem_lines.append(f"• {c}")
                partes.append("### MEMÓRIA SEMÂNTICA:\n" + "\n".join(sem_lines))
        except Exception as e:
            partes.append(f"### SEMÂNTICA: Erro - {e}")

        if not partes:
            return {
                "response": "📭 Memória vazia.",
                "thinking": "Memória unificada está vazia.",
                "status": "success",
            }

        return {
            "response": "\n\n".join(partes),
            "thinking": "Memória unificada inspecionada.",
            "status": "success",
        }
    def _cmd_criar_criativo(self, ctx, args, flags):
        """Gera um jogo de forma criativa usando temperatura adaptativa e síntese de ideias."""
        if not args:
            return {
                "response": "⚠️ Uso: `/criar_criativo <gênero> [--ref Jogo1, Jogo2] [--engine roblox|godot|web]`",
                "thinking": "Faltou o gênero do jogo.",
                "status": "error",
            }

        genero = args[0]
        engine = flags.get("engine", "roblox")
        refs = flags.get("ref", [])

        cre = getattr(ctx, "creativity_engine", None)
        ideias_sintese = []
        if cre:
            ideias_sintese = cre.synthesize_ideas(genero, refs, num_ideias=3)
            for ideia in ideias_sintese:
                cre.add_idea(genero, ideia, "sintese_criativa", sucesso=None)

        criatividade_section = ""
        if cre:
            criatividade_section = cre.get_creativity_prompt_section(genero)

        refs_texto = ""
        if refs:
            refs_texto = f"\nJogos de referência: {', '.join(refs)}"

        ideias_texto = ""
        if ideias_sintese:
            ideias_texto = "\nIdeias de síntese:\n" + "\n".join(f"• {i}" for i in ideias_sintese)

        prompt = (
            f"Crie um jogo de {genero} inovador e criativo (motor: {engine}).{refs_texto}{ideias_texto}\n"
            f"{criatividade_section}\n\n"
            "Inclua:\n"
            "1. Visão geral do jogo (o que o torna único)\n"
            "2. Mecânicas principais (mescle gêneros de forma ousada)\n"
            "3. Sistema de progressão (não linear, com surpresas)\n"
            "4. Direção de arte e identidade visual\n"
            "5. Sons e trilha sonora sugeridos\n\n"
            "Salve o GDD com: <kael_save filename='Docs/GDD.md'>conteúdo</kael_save>\n"
            "Salve a estrutura do projeto com: <kael_save filename='Scripts/main.lua'>código do script principal</kael_save>"
        )

        resultado = ctx.generate(prompt)
        resposta = ctx.process_save_commands(resultado['response'], save_dir=ctx.project_path)

        save_status = "success"
        if any(marker in resposta for marker in ("[AGUARDANDO TESTE", "[ALTERAÇÃO BLOQUEADA", "[ARQUIVO BLOQUEADO")):
            save_status = "permission_required"

        return {
            "response": f"🎨 **Jogo Criativo Gerado: {genero}**\n\n{resposta}",
            "thinking": resultado.get('thinking', ''),
            "status": save_status,
        }
    def _cmd_ideia(self, ctx, args, flags):
        """Gera ideias criativas via síntese de gêneros."""
        cre = getattr(ctx, "creativity_engine", None)
        if cre is None:
            return {
                "response": "⚠️ Motor de criatividade não disponível.",
                "thinking": "Módulo creativity_engine não inicializado.",
                "status": "error",
            }

        genero_principal = args[0] if args else "aventura"
        generos_ref = []
        if '--ref' in args:
            idx = args.index('--ref')
            generos_ref = [g.strip() for g in args[idx + 1:]] if idx + 1 < len(args) else []

        ideias = cre.synthesize_ideas(genero_principal, generos_ref, num_ideias=5)

        for ideia in ideias:
            cre.add_idea(genero_principal, ideia, "comando_ideia", sucesso=None)

        if not ideias:
            return {
                "response": f"💡 Nenhuma ideia gerada para '{genero_principal}'. Tente adicionar gêneros de referência com --ref.",
                "thinking": "Síntese retornou vazio.",
                "status": "success",
            }

        linhas = [f"💡 **Ideias Criativas para {genero_principal}:**\n"]
        for i, ideia in enumerate(ideias, 1):
            linhas.append(f"{i}. {ideia}")

        return {
            "response": "\n".join(linhas),
            "thinking": f"Síntese de {len(ideias)} ideias para {genero_principal}.",
            "status": "success",
        }

    def _cmd_temperatura(self, ctx, args, flags):
        """Mostra as configurações de temperatura adaptativa."""
        cre = getattr(ctx, "creativity_engine", None)
        if cre is None:
            return {
                "response": "⚠️ Motor de criatividade não disponível.",
                "thinking": "Módulo creativity_engine não inicializado.",
                "status": "error",
            }

        linhas = ["🌡️ **Temperatura Adaptativa do Kael:**\n"]
        for tipo, temp in cre.TEMPERATURE_MAP.items():
            linhas.append(f"• `{tipo}`: {temp}")

        linhas.append("\n**Faixas de exploração:**")
        for tipo in cre.TEMPERATURE_MAP:
            low, high = cre.get_temperature_range(tipo)
            linhas.append(f"• `{tipo}`: {low} → {high}")

        linhas.append("\n**Detecção automática de tipo de tarefa:**")
        linhas.append("• Palavras como código/script/bug/erro → `tecnico` (0.15)")
        linhas.append("• Palavras como pesquisar/gênero/estilo → `exploratorio` (0.90)")
        linhas.append("• Demais mensagens → `criativo` (0.75)")

        return {
            "response": "\n".join(linhas),
            "thinking": "Configurações de temperatura exibidas.",
            "status": "success",
        }

    def _cmd_contexto(self, ctx, args, flags):
        """Mostra contexto da memória unificada e do projeto"""
        mem_info = ""
        if ctx.memory:
            try:
                rules = ctx.memory.get_learned_rules(5)
                mem_info += f"- Regras aprendidas: {len(rules)}\\n"
            except: pass
    
        project_info = ""
        if hasattr(ctx, 'project_path') and ctx.project_path:
            project_info = f"- Projeto: `{ctx.project_path.name}`\\n"
    
        ctx_config = ""
        if hasattr(ctx, 'config') and ctx.config:
            ctx_config = f"- Temperatura: {ctx.config.get('temperature', 0.45)}\\n"
            ctx_config += f"- Modelo: {ctx.config.get('model_name', 'qwen2.5-coder')}\\n"
    
            return {
                "response": f"📋 **Contexto Atual**\\n{mem_info}{project_info}{ctx_config}"
                f"- **Memória Vetorial:** {'Ativa' if ctx.memory else 'Desativada'}\\n"
                f"- **Compressor:** {'Ativo' if ctx.compressor else 'Desativado'}\\n"
                f"- **Contexto:** ~{ctx.config.get('context_window', 4096)} tokens",
                "thinking": "Contexto exibido.", "status": "success"
            }

    def _cmd_estratégia(self, ctx, args, flags):
        """Modo CEO: analisa solicitação como plano empresarial"""
        prompt = args[0] if args else ""
        if not prompt:
            return {"response": "📝 **Modo Estratégica**\\nInforme uma solicitação após o comando `/estratégia`.\\n\\nExemplo: `/estratégia Criar plano de negócios para aplicativo de delivery`", "thinking": "Modo estratégico ativado.", "status": "ready"}
    
        from core.ceo_ai import create_ceo
        try:
            ceo = create_ceo(model="qwen2.5-coder")  # Usando qwen disponível
            analysis = ceo.analyze_request(prompt)
            return {
                "response": f"🧠 **Modo CEO - Análise Estratégica**\\n\\n"
            f"- **Tipo de Tarefa:** {analysis.get('task_type', 'desconhecido')}\\n"
            f"- **Prioridade:** {analysis.get('priority', 'média')}\\n"
            f"- **Delegação:** {', '.join(analysis.get('delegation', []))}\\n"
            f"- **Raciocínio:** {analysis.get('reasoning', 'Não disponível')[:300]}...",
            "thinking": "CEO analisou a solicitação.", "status": "success"
            }
        except Exception as e:
            return {"response": f"⚠️ Erro ao ativar modo CEO: {str(e)[:200]}", "thinking": "Erro na análise do CEO.", "status": "error"}

    def _cmd_modelo(self, ctx, args, flags):
        """Mudar modelo de IA"""
        arg = args[0].lower() if args else ""
    
        # Modelos disponíveis localmente
        local_models = {
            "qwen2.5-coder": "qwen2.5-coder:7b (local, code)",
            "llama3.1": "llama3.1:8b (local, geral)",
            "qwen3": "qwen3:8b (local, avançado)",
        }
    
        # Modelos de nuvem (requereem API key)
        cloud_models = {
            "gpt-4o": "gpt-4o-mini (OpenAI - requere API key)",
            "claude": "claude-3-haiku (Anthropic - requere API key)",
            "gemini": "gemini-1.5-flash (Google - requere API key)",
        }
    
        if arg in local_models:
            if hasattr(ctx, 'config'):
                ctx.config['model_name'] = arg
                config_path = ctx.base_dir / "config" / "generation.local.json"
                import json
                with open(config_path, 'w') as f:
                    json.dump(ctx.config, f, indent=2)
        
            return {
                "response": f"🤖 **Modelo Local Alterado:** {local_models[arg]}\\n"
                "Reinicie o Kael para efeitos completos.", 
                "thinking": f"Modelo cambiado para {arg}", "status": "success"
            }
        elif arg in cloud_models:
            return {
                "response": f"🤖 **Modelo de Nuvem:** {cloud_models[arg]}\\n"
                "Configure a API key em config/external_apis.json primeiro.", 
                "thinking": "Modelo de nuvem selecionado", "status": "information"
            }
        else:
            # Listar modelos disponíveis
            available = []
            if ctx.ollama_online():
                available.append("qwen2.5-coder:7b (local)")
                available.append("llama3.1:8b (local)")
                available.append("qwen3:8b (local)")
            available.append("gpt-4o-mini (OpenAI nuvem)")
            available.append("claude-3-haiku (Anthropic nuvem)")
            available.append("gemini-1.5-flash (Google nuvem)")
        
            return {
                "response": f"🤖 **Modelos Disponíveis:**\\n" + "\\n".join(f"- {m}" for m in available)
                + "\\n\\nUse `/modelo qwen2.5-coder`, `/modelo llama3.1`, etc.", 
                "thinking": "Listando modelos disponíveis.", "status": "information"
            }

    def _cmd_memória_detalhada(self, ctx, args, flags):
        """Memória unificada completa"""
        parts = []
    
        # Regras aprendidas
        if ctx.memory:
            try:
                rules = ctx.memory.get_learned_rules(10)
                parts.append(f"**📚 Regras Aprendidas ({len(rules)}):**")
                for r in rules[:5]:
                    parts.append(f"- {r[:100]}...")
                if len(rules) > 5:
                    parts.append(f"- ... e mais {len(rules)-5} regras")
            except: parts.append("- Erro ao carregar regras")
    
        # Episódios
        if hasattr(ctx, 'episodic_memory') and ctx.episodic_memory:
            try:
                episodes = ctx.episodic_memory.get_recent(5)
                parts.append(f"**📅 Episódios Recentes ({len(episodes)}):**")
                for e in episodes[:3]:
                    parts.append(f"- {e[:80]}...")
            except: parts.append("- Erro ao carregar episódios")
    
        # Memória semântica
        if hasattr(ctx, 'semantic_memory') and ctx.semantic_memory:
            parts.append(f"**🔍 Memória Semântica:** Ativa")
    
        # Estatísticas do projeto
        if hasattr(ctx, 'project_path') and ctx.project_path:
            parts.append(f"- **Projeto:** `{ctx.project_path.name}`")
    
        return {
            "response": "🧠 **Memória Unificada Detalhada**\\n" + "\\n".join(parts)
            if parts else "Nenhuma memória disponível.",
            "thinking": "Memória detalhada exibida.", "status": "success"
        }

    def _cmd_criar_arquivo(self, ctx, args, flags):
        """Cria novo arquivo com autorização"""
        from core.file_manager import get_file_manager
        fm = get_file_manager()
        if fm is None:
            return {"response": "❌ Gerenciador de arquivos não inicializado.", "thinking": "FileManager não disponível.", "status": "error"}
        if not args:
            return {"response": "📝 **Criar Arquivo**\nUso: `/criar_arquivo <caminho> <conteúdo>`\nExemplo: `/criar_arquivo teste.txt Olá, mundo!`", "thinking": "Sintaxe incorreta.", "status": "ready"}
        file_path = args[0]
        content = " ".join(args[1:]) if len(args) > 1 else ""
        return fm.create_file(file_path, content)

    def _cmd_modificar_arquivo(self, ctx, args, flags):
        """Modifica arquivo existente com autorização"""
        from core.file_manager import get_file_manager
        fm = get_file_manager()
        if fm is None:
            return {"response": "❌ Gerenciador de arquivos não inicializado.", "thinking": "FileManager não disponível.", "status": "error"}
        if not args:
            return {"response": "📝 **Modificar Arquivo**\nUso: `/modificar_arquivo <caminho> <novo conteúdo>`\nExemplo: `/modificar_arquivo teste.txt Novo conteúdo aqui`", "thinking": "Sintaxe incorreta.", "status": "ready"}
        file_path = args[0]
        new_content = " ".join(args[1:]) if len(args) > 1 else ""
        return fm.modify_file(file_path, new_content)

    def _cmd_ler_arquivo(self, ctx, args, flags):
        """Lê conteúdo de um arquivo"""
        from core.file_manager import get_file_manager
        fm = get_file_manager()
        if fm is None:
            return {"response": "❌ Gerenciador de arquivos não inicializado.", "thinking": "FileManager não disponível.", "status": "error"}
        if not args:
            return {"response": "📄 **Ler Arquivo**\nUso: `/ler_arquivo <caminho>`\nExemplo: `/ler_arquivo teste.txt`", "thinking": "Sintaxe incorreta.", "status": "ready"}
        file_path = args[0]
        return fm.read_file(file_path)

    def _cmd_listar_arquivos(self, ctx, args, flags):
        """Lista arquivos e pastas"""
        from core.file_manager import get_file_manager
        fm = get_file_manager()
        if fm is None:
            return {"response": "❌ Gerenciador de arquivos não inicializado.", "thinking": "FileManager não disponível.", "status": "error"}
        directory = args[0] if args else ""
        recursive = "--recursivo" in args or "-r" in args
        return fm.list_files(directory, recursive=recursive)

    def _cmd_autorizar_acao(self, ctx, args, flags):
        """Autoriza ação pendente de arquivo"""
        from core.file_manager import get_file_manager
        fm = get_file_manager()
        if fm is None:
            return {"response": "❌ Gerenciador de arquivos não inicializado.", "thinking": "FileManager não disponível.", "status": "error"}
        if not args:
            return {"response": "🔐 **Autorizar Ação**\nUso: `/autorizar_acao <ID>`\nExemplo: `/autorizar_acao 1`", "thinking": "Sintaxe incorreta.", "status": "ready"}
        try:
            action_id = int(args[0])
            return fm.authorize_action(action_id)
        except ValueError:
            return {"response": "❌ ID inválido. Use um número.", "thinking": "ID não é numérico.", "status": "error"}

    def _cmd_cancelar_acao(self, ctx, args, flags):
        """Cancela ação pendente de arquivo"""
        from core.file_manager import get_file_manager
        fm = get_file_manager()
        if fm is None:
            return {"response": "❌ Gerenciador de arquivos não inicializado.", "thinking": "FileManager não disponível.", "status": "error"}
        if not args:
            return {"response": "❌ **Cancelar Ação**\nUso: `/cancelar_acao <ID>`\nExemplo: `/cancelar_acao 1`", "thinking": "Sintaxe incorreta.", "status": "ready"}
        try:
            action_id = int(args[0])
            return fm.cancel_action(action_id)
        except ValueError:
            return {"response": "❌ ID inválido. Use um número.", "thinking": "ID não é numérico.", "status": "error"}

    def _cmd_acoes_pendentes(self, ctx, args, flags):
        """Lista ações pendentes de autorização"""
        from core.file_manager import get_file_manager
        fm = get_file_manager()
        if fm is None:
            return {"response": "❌ Gerenciador de arquivos não inicializado.", "thinking": "FileManager não disponível.", "status": "error"}
        return fm.list_pending_actions()
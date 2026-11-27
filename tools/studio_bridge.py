"""
============================================================
KAEL API SERVER v5.0 - Completo e Unificado
============================================================
Arquitetura: KaelContext + ToolRegistry (modular)
Fallback: arquitetura monolítica v4.0 (se módulos core/ faltarem)

Comandos integrados:
  /status /teste_conexao /help /ajuda
  /gerenciar_jogo [Nome] /parar_gerenciamento
  /ver_jogo /integrar_jogo /refatorar
  /construir_jogo [genero] [nome] --engine [roblox|godot|web] --ref Jogo1, Jogo2
  /pesquisar_jogos [genero] --exemplos Jogo1, Jogo2
  /limpar_flutuantes [--analisar] [--dist N] [--sem-backup]
  /resultado_limpeza
============================================================
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import sys
import re
import time
from pathlib import Path
from collections import deque

BASE_DIR = Path(__file__).parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

# ============================================================
# 1. ARQUITETURA v5.0: KaelContext + ToolRegistry
#    (com fallback para v4.0 se os módulos não existirem)
# ============================================================

class KaelContext:
    """Contexto central do Kael (fallback v4.0 se core/kael_context.py não existir)."""
    
    def __init__(self):
        self.config_file = BASE_DIR / "config" / "config.json"
        self.config = {}
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            except Exception as e:
                print(f"[AVISO] Falha ao ler config.json: {e}")
        
        self.system_prompt = self.config.get("system_prompt", "")
        self.ollama_url = self.config.get("ollama_url", "http://127.0.0.1:8080")
        self.model_name = self.config.get("model_name", "qwen3:8b")
        
        # Caminhos de projeto
        projects_root = Path(self.config.get("projects_root", str(BASE_DIR.parent / "arquivos-de-inteligencia" / "Projetos")))
        self.project_path = Path(self.config.get("project_path", str(projects_root / "Ecos_de_Aethelgard")))
        
        # Memória
        self.memory_dir = BASE_DIR.parent / "arquivos-de-inteligencia" / "conhecimento"
        if not self.memory_dir.exists():
            self.memory_dir = BASE_DIR / "kael_knowledge"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Histórico
        self.historico_file = BASE_DIR / "ultimas_mensagens.json"
        
        # Modo autônomo
        self.autonomous = {"active": False, "project": None}
        
        # Tenta importar módulos opcionais
        self.memory = None
        self.compressor = None
        self.game_bridge = None
        self.web_research = None
        
        try:
            from core.memory import KaelMemory
            self.memory = KaelMemory()
        except ImportError:
            pass
        
        try:
            from core.context_compressor import ContextCompressor
            self.compressor = ContextCompressor(max_chars=12000)
        except ImportError:
            pass
        
        try:
            from tools.game_bridge import GameBridge
            self.game_bridge = GameBridge
        except ImportError:
            pass
        
        try:
            from tools.web_research import WebResearch
            self.web_research = WebResearch
        except ImportError:
            pass
    
    def ollama_online(self):
        try:
            import requests
            r = requests.get(f"{self.ollama_url}/api/tags", timeout=3)
            return r.status_code == 200
        except:
            return False
    
    def generate(self, prompt):
        """Gera resposta via ollama_client."""
        try:
            from ai.ollama_client import generate_response
            return generate_response(prompt)
        except ImportError:
            return {"response": "[ERRO] Cliente Ollama não disponível.", "thinking": ""}
    
    def load_historico(self):
        if not self.historico_file.exists():
            return []
        try:
            with open(self.historico_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    
    def save_historico(self, historico):
        try:
            with open(self.historico_file, 'w', encoding='utf-8') as f:
                json.dump(historico[-50:], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERRO] Ao salvar histórico: {e}")
    
    def process_save_commands(self, response_text, save_dir=None):
        """Fail closed when the legacy context lacks tested-write approvals."""
        pattern = r'<kael_save\s+filename=[\'"]([^\'"]+)[\'"]>(.*?)</kael_save>'
        matches = re.findall(pattern, response_text, re.DOTALL)
        if not matches:
            return response_text
        return (
            "[ARQUIVO BLOQUEADO: o modo legado não possui o fluxo de teste e aprovação. "
            "Nenhum arquivo foi gravado.]"
        )


class ToolRegistry:
    """Registro de comandos (fallback v4.0 se core/tool_registry.py não existir)."""
    
    def __init__(self, ctx):
        self.ctx = ctx
        self.tools = {}
        self.commands = {}
        self._register_default_commands()
    
    def _register_default_commands(self):
        """Registra todos os comandos padrão."""
        self.commands['/status'] = self._cmd_status
        self.commands['/teste_conexao'] = self._cmd_teste_conexao
        self.commands['/help'] = self._cmd_help
        self.commands['/ajuda'] = self._cmd_help
        self.commands['/gerenciar_jogo'] = self._cmd_gerenciar_jogo
        self.commands['/parar_gerenciamento'] = self._cmd_parar_gerenciamento
        self.commands['/ver_jogo'] = self._cmd_ver_jogo
        self.commands['/integrar_jogo'] = self._cmd_integrar_jogo
        self.commands['/refatorar'] = self._cmd_refatorar
        self.commands['/construir_jogo'] = self._cmd_construir_jogo
        self.commands['/pesquisar_jogos'] = self._cmd_pesquisar_jogos
        self.commands['/limpar_flutuantes'] = self._cmd_limpar_flutuantes
        self.commands['/resultado_limpeza'] = self._cmd_resultado_limpeza
    
    def auto_discover(self):
        """Tenta descobrir tools adicionais (stub)."""
        pass
    
    def dispatch(self, prompt):
        """Dispatch de comandos."""
        parts = prompt.split()
        command = parts[0].lower()
        
        if command in self.commands:
            return self.commands[command](parts)
        return None
    
    # ========== COMANDOS ==========
    
    def _cmd_status(self, parts):
        mem_files = list(self.ctx.memory_dir.glob('*')) if self.ctx.memory_dir.exists() else []
        return {
            "response": (
                "✅ **Status do Sistema Kael v5.0**\n"
                f"- **Servidor API:** Online (porta 8000)\n"
                f"- **Ollama:** {'🟢 Online' if self.ctx.ollama_online() else '🔴 Offline'}\n"
                f"- **Memória Vetorial:** {'🟢 Ativa' if self.ctx.memory else '🟡 Desativada'}\n"
                f"- **Compressor:** {'🟢 Ativo' if self.ctx.compressor else '🟡 Desativado'}\n"
                f"- **Game Bridge:** {'🟢 Ativo' if self.ctx.game_bridge else '🔴 Desativado'}\n"
                f"- **Web Research:** {'🟢 Ativo' if self.ctx.web_research else '🔴 Desativado'}\n"
                f"- **Arquivos na Memória:** {len(mem_files)}\n"
                f"- **Projeto Ativo:** `{self.ctx.project_path.name}`\n"
                f"- **Modo Autônomo:** {'🟢 ATIVO' if self.ctx.autonomous['active'] else '⚪ Inativo'}"
            ),
            "thinking": "Comando /status executado.",
            "status": "success"
        }
    
    def _cmd_teste_conexao(self, parts):
        ok = self.ctx.ollama_online()
        return {
            "response": (
                "📡 **Teste de Conexão**\n"
                f"- Ollama (8080): {'🟢 Respondendo' if ok else '🔴 Offline'}\n"
                "- API Kael (8000): 🟢 Respondendo\n"
                f"- Game Bridge: {'🟢 Pronto' if self.ctx.game_bridge else '🔴 Indisponível'}\n"
                f"- Web Research: {'🟢 Pronto' if self.ctx.web_research else '🔴 Indisponível'}"
            ),
            "thinking": "Ping executado.",
            "status": "success" if ok else "error"
        }
    
    def _cmd_help(self, parts):
        return {
            "response": (
                "📖 **Comandos do Sistema:**\n"
                "`/status` `/teste_conexao` `/help`\n"
                "`/gerenciar_jogo [Nome]` `/parar_gerenciamento`\n\n"
                "🎮 **Comandos de Jogo:**\n"
                "`/ver_jogo` - Análise estática do projeto\n"
                "`/integrar_jogo` - IA corrige scripts reais\n"
                "`/refatorar` - IA refatora o maior script\n"
                "`/construir_jogo [genero] [nome] --engine [roblox|godot|web] --ref Jogo1, Jogo2`\n\n"
                "🌐 **Pesquisa:**\n"
                "`/pesquisar_jogos [genero] --exemplos Jogo1, Jogo2`\n\n"
                "🧹 **Limpeza:**\n"
                "`/limpar_flutuantes [--analisar] [--dist N] [--sem-backup]`\n"
                "`/resultado_limpeza`"
            ),
            "thinking": "Menu de ajuda.",
            "status": "success"
        }
    
    def _cmd_gerenciar_jogo(self, parts):
        project = parts[1] if len(parts) > 1 else "Ecos_de_Aethelgard"
        self.ctx.autonomous["active"] = True
        self.ctx.autonomous["project"] = project
        return {
            "response": f"🤖 **Modo Autônomo ATIVADO** em `{project}`. Use `/parar_gerenciamento` para parar.",
            "thinking": "Estado global alterado.",
            "status": "success"
        }
    
    def _cmd_parar_gerenciamento(self, parts):
        self.ctx.autonomous["active"] = False
        return {
            "response": "⏹️ **Modo Autônomo DESATIVADO.**",
            "thinking": "Modo autônomo desligado.",
            "status": "success"
        }
    
    def _cmd_ver_jogo(self, parts):
        if not self.ctx.game_bridge:
            return {"response": "🔴 Game Bridge indisponível.", "thinking": "Módulo ausente.", "status": "error"}
        
        bridge = self.ctx.game_bridge(str(self.ctx.project_path))
        report = bridge.full_report()
        
        if 'erro' in report:
            return {
                "response": f"⚠️ {report['erro']}\nUse `/construir_jogo [genero] [nome]` para criar o projeto.",
                "thinking": "Projeto não encontrado.",
                "status": "error"
            }
        
        scripts_txt = "\n".join([f"- `{s['arquivo']}` ({s['linhas']} linhas)" for s in report['scripts'][:10]]) or "- (nenhum script)"
        if report['problemas']:
            prob_txt = "\n".join([f"- ⚠️ [{p['tipo']}] {p['arquivo']}: {p['detalhe']}" for p in report['problemas'][:10]])
        else:
            prob_txt = "- ✅ Nenhum problema estático detectado"
        
        return {
            "response": (
                f"👁️ **Análise Real do Projeto: {self.ctx.project_path.name}**\n"
                f"- **Motor detectado:** {report['motor']}\n"
                f"- **Scripts:** {report['total_scripts']}\n{scripts_txt}\n"
                f"- **Documentos:** {', '.join(report['documentos']) or 'nenhum'}\n"
                f"- **Cenas:** {len(report['cenas'])}\n\n"
                f"**Problemas detectados:**\n{prob_txt}"
            ),
            "thinking": "Análise estática real executada pelo GameBridge.",
            "status": "success"
        }
    
    def _cmd_integrar_jogo(self, parts):
        if not self.ctx.game_bridge:
            return {"response": "🔴 Game Bridge indisponível.", "thinking": "Módulo ausente.", "status": "error"}
        
        bridge = self.ctx.game_bridge(str(self.ctx.project_path))
        scan = bridge.scan_project()
        
        if 'erro' in scan or not scan['scripts']:
            return {
                "response": f"⚠️ Nenhum script encontrado. ({scan.get('erro', 'pasta vazia')})",
                "thinking": "Sem scripts.",
                "status": "error"
            }
        
        trechos = []
        for s in scan['scripts'][:3]:
            texto = (self.ctx.project_path / s['arquivo']).read_text(encoding='utf-8', errors='ignore')[:2000]
            trechos.append(f"=== {s['arquivo']} ===\n{texto}")
        
        prompt_ia = (
            f"Analise os scripts do projeto {self.ctx.project_path.name} (motor: {scan['motor']}). "
            f"Identifique bugs e melhore a integração. Para cada script corrigido, gere o código "
            f"completo dentro da tag: <kael_save filename='Scripts/NOME_fix.ext'>código</kael_save>\n\n"
            + "\n\n".join(trechos)
        )
        
        resultado = self.ctx.generate(prompt_ia)
        resposta = self.ctx.process_save_commands(resultado['response'], save_dir=self.ctx.project_path)
        
        return {
            "response": f"🔧 **Integração analisada.** Resultado da proposta:\n\n{resposta}",
            "thinking": resultado.get('thinking', ''),
            "status": "blocked"
        }
    
    def _cmd_refatorar(self, parts):
        if not self.ctx.game_bridge:
            return {"response": "🔴 Game Bridge indisponível.", "thinking": "Módulo ausente.", "status": "error"}
        
        bridge = self.ctx.game_bridge(str(self.ctx.project_path))
        scan = bridge.scan_project()
        
        if 'erro' in scan or not scan['scripts']:
            return {"response": "⚠️ Nenhum script encontrado.", "thinking": "Sem scripts.", "status": "error"}
        
        maior = max(scan['scripts'], key=lambda s: s['linhas'])
        p = self.ctx.project_path / maior['arquivo']
        texto = p.read_text(encoding='utf-8', errors='ignore')[:6000]
        novo_nome = f"Scripts/{Path(maior['arquivo']).stem}_refatorado{Path(maior['arquivo']).suffix}"
        
        prompt_ia = (
            f"Refatore o script abaixo (motor {scan['motor']}) para ficar limpo e modular. "
            f"Salve com: <kael_save filename='{novo_nome}'>código</kael_save>\n\n{texto}"
        )
        
        resultado = self.ctx.generate(prompt_ia)
        resposta = self.ctx.process_save_commands(resultado['response'], save_dir=self.ctx.project_path)
        
        return {
            "response": f"♻️ **Refatoração analisada.** Proposta para `{novo_nome}`:\n\n{resposta}",
            "thinking": resultado.get('thinking', ''),
            "status": "blocked"
        }
    
    def _cmd_construir_jogo(self, parts):
        if not self.ctx.game_bridge:
            return {"response": "🔴 Game Bridge indisponível.", "thinking": "Módulo ausente.", "status": "error"}
        
        # Parse de flags
        args = []
        flags = {"engine": "auto", "ref": []}
        i = 1
        while i < len(parts):
            t = parts[i]
            if t == '--engine' and i + 1 < len(parts):
                flags["engine"] = parts[i + 1].lower()
                i += 2
                continue
            if t in ('--ref', '--exemplos', '--exemplo'):
                i += 1
                buf = []
                while i < len(parts) and not parts[i].startswith('--'):
                    buf.append(parts[i])
                    i += 1
                raw = ' '.join(buf)
                flags["ref"] = [x.strip() for x in re.split(r'[;,]', raw) if x.strip()]
                continue
            args.append(t)
            i += 1
        
        genero = args[0] if len(args) > 0 else 'aventura'
        nome = re.sub(r'[^\w\-]', '_', args[1]) if len(args) > 1 else 'Ecos_de_Aethelgard'
        
        proj_dir = self.ctx.project_path.parent / nome
        bridge = self.ctx.game_bridge(str(proj_dir))
        info = bridge.create_project_structure(nome, genero, flags['engine'])
        templates_response = ""
        if info.get("template_files"):
            from tools.game_bridge import template_save_commands
            templates_response = self.ctx.process_save_commands(
                template_save_commands(info["template_files"]),
                save_dir=proj_dir,
            )
        
        # Pesquisa de referência opcional
        base_pesquisa = ""
        if flags['ref'] and self.ctx.web_research:
            base_pesquisa = self.ctx.web_research().research_genre(genero, flags['ref'])
        
        gdd_prompt = (
            f"Crie um GDD conciso para um jogo de {genero} chamado {nome} (motor: {info['engine']}). "
            f"Inclua: visão geral, mecânicas principais, progressão, direção de arte e som. "
        )
        if base_pesquisa:
            gdd_prompt += f"\n\nBASE DE PESQUISA REAL:\n{base_pesquisa[:4000]}\n"
        gdd_prompt += f"Salve com: <kael_save filename='Docs/GDD.md'>conteúdo</kael_save>"
        
        resultado = self.ctx.generate(gdd_prompt)
        resposta_gdd = self.ctx.process_save_commands(resultado['response'], save_dir=proj_dir)
        
        msg = (
            f"🏗️ **Projeto `{nome}` criado!**\n"
            f"- **Motor:** {info['engine']}\n"
            f"- Pastas: {', '.join(info['pastas'])}\n"
            f"- Templates: {', '.join(info['templates']) or 'nenhum'}\n"
        )
        if flags['ref']:
            msg += f"- **Referências pesquisadas:** {', '.join(flags['ref'])}\n"
        if templates_response:
            msg += f"\n**Validação dos scripts:** {templates_response}\n"
        msg += f"\n{resposta_gdd}"
        return {
            "response": msg,
            "thinking": resultado.get('thinking', ''),
            "status": (
                "blocked"
                if templates_response or "[ARQUIVO BLOQUEADO:" in resposta_gdd
                else "success"
            ),
        }
    
    def _cmd_pesquisar_jogos(self, parts):
        if not self.ctx.web_research:
            return {"response": "🔴 Web Research indisponível.", "thinking": "Módulo ausente.", "status": "error"}
        
        args = []
        flags = {"ref": []}
        i = 1
        while i < len(parts):
            t = parts[i]
            if t in ('--ref', '--exemplos', '--exemplo'):
                i += 1
                buf = []
                while i < len(parts) and not parts[i].startswith('--'):
                    buf.append(parts[i])
                    i += 1
                raw = ' '.join(buf)
                flags["ref"] = [x.strip() for x in re.split(r'[;,]', raw) if x.strip()]
                continue
            args.append(t)
            i += 1
        
        genero = args[0] if args else 'aventura'
        exemplos = flags['ref']
        
        pesquisa = self.ctx.web_research().research_genre(genero, exemplos)
        if not pesquisa:
            return {
                "response": "⚠️ Nenhuma informação encontrada. Verifique sua conexão.",
                "thinking": "Pesquisa web retornou vazio.",
                "status": "error"
            }
        
        # Salva o relatório
        docs_dir = self.ctx.project_path / 'Docs'
        if not docs_dir.exists():
            docs_dir = self.ctx.memory_dir
        genero_slug = re.sub(r'[^\w\-]', '_', genero)
        fname = f"PESQUISA_{genero_slug}.md"
        try:
            (docs_dir / fname).write_text(pesquisa, encoding='utf-8')
        except Exception as e:
            print(f"[ERRO] Ao salvar pesquisa: {e}")
        
        return {
            "response": (
                f"🌐 **Pesquisa concluída!** Relatório salvo em `{docs_dir.name}/{fname}`.\n\n"
                f"**Descobertas principais:**\n{pesquisa[:1500]}\n\n"
                f"*(relatório completo no arquivo — use `/construir_jogo ... --ref` para aplicar no GDD)*"
            ),
            "thinking": "Pesquisa web real executada via DuckDuckGo + Wikipedia.",
            "status": "success"
        }
    
    def _cmd_limpar_flutuantes(self, parts):
        modo = 'ANALISAR' if '--analisar' in parts else 'REMOVER'
        backup = '--sem-backup' not in parts
        dist = 50
        for i, p in enumerate(parts):
            if p == '--dist' and i + 1 < len(parts):
                try:
                    dist = int(parts[i + 1])
                except ValueError:
                    pass
        
        # Tenta usar Studio Bridge (plugin remoto)
        try:
            from core.plugin_bridge import enfileirar_limpeza, studio_conectado
            if studio_conectado():
                enfileirar_limpeza(modo=modo, backup=backup, max_distance=dist)
                return {
                    "response": (
                        f"🧹 **Tarefa enviada ao Roblox Studio!**\n"
                        f"- Modo: {modo} | Backup: {'sim' if backup else 'nao'} | Alcance: {dist} studs\n"
                        f"O plugin varre TUDO de uma vez e remove em lote. "
                        f"Veja o Output do Studio ou digite `/resultado_limpeza`."
                    ),
                    "thinking": "Tarefa enfileirada para o plugin via Studio Bridge.",
                    "status": "success"
                }
        except ImportError:
            pass
        
        return {
            "response": (
                "⛔ O Roblox Studio está desconectado. Nenhum script Luau foi salvo: "
                "não há um runner de testes compatível para validar esse código."
            ),
            "thinking": "Execução bloqueada porque não há runner de testes Luau disponível.",
            "status": "error"
        }
    
    def _cmd_resultado_limpeza(self, parts):
        # Tenta ler do Studio Bridge
        try:
            from core.plugin_bridge import ESTADO as STUDIO_ESTADO
            ult = STUDIO_ESTADO["limpezas"][-1] if STUDIO_ESTADO["limpezas"] else None
            if ult:
                nomes = "\n".join(f"- {n}" for n in ult.get("nomes", [])[:15]) or "- (nenhum)"
                return {
                    "response": (
                        f"🧹 **Última limpeza no Studio:**\n"
                        f"- Detectados: **{ult.get('detectados', 0)}** | Removidos em lote: **{ult.get('removidos', 0)}**\n"
                        f"- Modo: {ult.get('modo')} | Backup: {ult.get('backup')}\n\n**Amostra:**\n{nomes}"
                    ),
                    "thinking": "Resultado real vindo do plugin Roblox.",
                    "status": "success"
                }
        except ImportError:
            pass
        
        return {"response": "Nenhuma limpeza executada ainda. Use `/limpar_flutuantes`.", "thinking": "Sem resultados.", "status": "success"}


# ============================================================
# 2. BOOT: contexto + registry
# ============================================================

ctx = KaelContext()
registry = ToolRegistry(ctx)
ctx.registry = registry
registry.auto_discover()

app = Flask(__name__)
CORS(app)

# ============================================================
# 3. PLUGIN BRIDGE (Roblox Studio)
# ============================================================

try:
    from core.plugin_bridge import register_routes
    register_routes(app, ctx)
    print("[OK] Plugin Bridge registrado.")
except Exception as e:
    print(f"[AVISO] Plugin Bridge desativado: {e}")

print("\n" + "=" * 60)
print("🚨 [KAEL] API SERVER v5.0 RODANDO NA PORTA 8000 🚨")
print(f"🎮 Projeto: {ctx.project_path}")
print(f"🔧 Comandos: {len(registry.commands)} registrados")
print(f"🧠 Ollama: {'🟢 Online' if ctx.ollama_online() else '🔴 Offline'}")
print("=" * 60 + "\n")

# ============================================================
# 4. ROTAS HTTP
# ============================================================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "online" if ctx.ollama_online() else "ollama_offline",
        "commands": sorted(registry.commands.keys()),
        "autonomous_mode": ctx.autonomous["active"]
    })

@app.route('/historico', methods=['GET'])
def get_historico():
    return jsonify(ctx.load_historico())

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    prompt = data.get('prompt', '').strip()
    if not prompt:
        return jsonify({"error": "Prompt vazio"}), 400
    
    print(f"\n[API] Recebido: {prompt[:80]}...")
    
    # 1) Comandos -> Registry
    if prompt.startswith('/'):
        resultado = registry.dispatch(prompt)
        if resultado:
            hist = ctx.load_historico()
            hist.append({"role": "user", "content": prompt})
            hist.append({"role": "assistant", "content": resultado.get("response", ""),
                         "thinking": resultado.get("thinking", "")})
            ctx.save_historico(hist)
            return jsonify(resultado)
        print(f"[API] Comando desconhecido -> enviando para a IA: {prompt.split()[0]}")
    
    # 2) Conversa normal: memória + compressão + IA
    memorias = []
    if ctx.memory is not None:
        try:
            memorias = ctx.memory.search_similar(prompt, limit=3)
        except Exception:
            pass
    
    hist = ctx.load_historico()
    if ctx.compressor is not None:
        try:
            contexto = ctx.compressor.build_context(prompt, hist, memorias, ctx.system_prompt)
        except ValueError:
            return jsonify({
                "error": "A mensagem excede o limite de contexto do modelo. Reduza o tamanho."
            }), 413
    else:
        contexto = prompt
    
    resultado = ctx.generate(contexto)
    resposta_final = ctx.process_save_commands(resultado['response'])
    
    hist.append({"role": "user", "content": prompt})
    hist.append({"role": "assistant", "content": resposta_final, "thinking": resultado['thinking']})
    ctx.save_historico(hist)
    
    return jsonify({
        "response": resposta_final,
        "thinking": resultado['thinking'],
        "status": "blocked" if "[ARQUIVO BLOQUEADO:" in resposta_final else "success",
    })

@app.route('/stream', methods=['GET', 'POST'])
def stream():
    if request.method == 'GET':
        prompt = request.args.get('prompt', '')
    else:
        prompt = (request.json or {}).get('prompt', '')
    if not prompt:
        return jsonify({"error": "Prompt vazio."}), 400
    resultado = ctx.generate(prompt)
    return jsonify({"response": resultado['response'], "thinking": resultado['thinking'], "status": "success"})

# ============================================================
# 5. ROTAS DE COMPATIBILIDADE (para clientes antigos)
# ============================================================

@app.route('/proxima_tarefa', methods=['GET'])
def proxima_tarefa_compat():
    """Stub para clientes antigos que fazem polling."""
    return jsonify({"tarefa": None, "status": "idle"})

@app.route('/estado_jogo', methods=['POST', 'GET'])
def estado_jogo_compat():
    """Stub para clientes antigos."""
    return jsonify({
        "projeto": "Ecos_de_Aethelgard",
        "motor": "roblox",
        "status": "ok"
    })

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000, debug=False)
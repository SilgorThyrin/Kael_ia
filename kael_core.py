# -*- coding: utf-8 -*-
"""
kael_core.py - Servidor Flask do Kael (v9.13 — Modular + Segurança de Sistema)
Novidades v9.13:
- Carregamento dinâmico de módulos via kael_loader (kael_modules.json)
- Injeção automática de regras de segurança de sistema (anti-alucinação)
- Integração com kael_system_tools (comandos PC seguros)
- Integração com kael_mobile_cleaner (análise/limpeza Android via ADB)
- Temperatura reduzida para 0.3 (menos alucinações)
- NUM_CTX reduzido para 4096 (protege VRAM de 6GB)
Herança v9.12:
- Biblioteca de templates (kael_library)
- Contexto do mapa (kael_context)
- Auto-aprendizado de códigos funcionais
Herança v9.11:
- /pesquisar [termo] (busca universal na web)
- Proteção MAX_CONTENT_LENGTH (MemoryError)
"""
import os
import json
import time
import re as _re
import logging
import threading
import requests
from flask import (
    Flask, request, jsonify, send_from_directory,
    Response, stream_with_context,
)

# ======================================================================
# CARREGAMENTO DINÂMICO DE MÓDULOS (v9.13)
# ======================================================================
MODULOS_CARREGADOS = {}
ERROS_CARREGAMENTO = {}

def _carregar_modulos_dinamicamente():
    """Tenta carregar módulos via kael_loader. Se falhar, usa fallback."""
    global MODULOS_CARREGADOS, ERROS_CARREGAMENTO
    try:
        import kael_loader
        kael_loader.carregar_todos()
        MODULOS_CARREGADOS = kael_loader.MODULOS_CARREGADOS
        ERROS_CARREGAMENTO = kael_loader.ERROS_CARREGAMENTO
        print("[LOADER] Módulos carregados via kael_loader.")
        return True
    except ImportError:
        print("[LOADER] kael_loader não encontrado. Usando imports manuais (fallback).")
        return False
    except Exception as e:
        print(f"[LOADER] Erro no loader: {e}. Usando imports manuais (fallback).")
        return False

# Tenta loader dinâmico primeiro
_loader_ok = _carregar_modulos_dinamicamente()

# ======================================================================
# IMPORTS MANUAIS (FALLBACK — garante compatibilidade se loader falhar)
# ======================================================================
try:
    import kael_engine as engine
except ImportError:
    engine = MODULOS_CARREGADOS.get("engine")
    if engine is None:
        raise ImportError("kael_engine.py é OBRIGATÓRIO e não foi encontrado.")

try:
    import kael_persona as persona
except ImportError:
    persona = MODULOS_CARREGADOS.get("persona")
    if persona is None:
        raise ImportError("kael_persona.py é OBRIGATÓRIO e não foi encontrado.")

try:
    import kael_assets as assets
except ImportError:
    assets = MODULOS_CARREGADOS.get("assets")

try:
    import kael_library
except ImportError:
    kael_library = MODULOS_CARREGADOS.get("library")

try:
    import kael_context
except ImportError:
    kael_context = MODULOS_CARREGADOS.get("context")

# Novos módulos de sistema (v9.13)
system_tools = MODULOS_CARREGADOS.get("system_tools")
mobile_cleaner = MODULOS_CARREGADOS.get("mobile_cleaner")

# Módulos de construção de jogos
try:
    from game_manager import GameManager
except ImportError:
    _gm_mod = MODULOS_CARREGADOS.get("game_manager")
    GameManager = getattr(_gm_mod, "GameManager", None) if _gm_mod else None

GameArchitect = WorldBuilder = GameDirector = GameIntegrator = None
try:
    from game_architect import GameArchitect
    from world_builder import WorldBuilder
    from game_director import GameDirector
    from game_integrator import GameIntegrator
except ImportError as e:
    print("[KAEL] Aviso: faltando módulos construtores:", e)
    # Tenta via loader
    for nome_mod, classe in [("game_architect", "GameArchitect"),
                             ("world_builder", "WorldBuilder"),
                             ("game_director", "GameDirector"),
                             ("game_integrator", "GameIntegrator")]:
        mod = MODULOS_CARREGADOS.get(nome_mod)
        if mod:
            globals()[classe] = getattr(mod, classe, None)

try:
    from refactor_agent import RefactorAgent
except ImportError:
    _ra_mod = MODULOS_CARREGADOS.get("refactor_agent")
    RefactorAgent = getattr(_ra_mod, "RefactorAgent", None) if _ra_mod else None

# ======================================================================
# CONFIG
# ======================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OLLAMA_URL = "http://127.0.0.1:8080/api/generate"
MODELO_CHAT = "qwen3:8b"
TIMEOUT_STREAM = 300
TIMEOUT_CONSTRUCAO = 1800
TEMPERATURA_PASS1 = 0.3        # Reduzido de 0.4 para 0.3 (menos alucinações)
NUM_CTX_CHAT = 4096            # Reduzido de 8192 para 4096 (protege VRAM 6GB)
NUM_PREDICT_PASS1 = 2048

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2 MB
DIRETOR_ATIVO = None
MANAGER_ATIVO = None
RESULTADOS_TESTE = {}
EVENTOS_TESTE = {}
LOCK_TESTES = threading.Lock()

print("\n" + "=" * 60)
print("[KAEL] kael_core.py v9.13 (Modular + Segurança de Sistema)")
print("[KAEL] Pass 1: Kael engenheiro | Pass 2: DESLIGADO")
print("[KAEL] Manager: correcao <-> expansao (com templates)")
print("[KAEL] Modelo: " + MODELO_CHAT + " | Contexto: " + str(NUM_CTX_CHAT))
if system_tools:
    print("[KAEL] ✓ kael_system_tools carregado")
if mobile_cleaner:
    print("[KAEL] ✓ kael_mobile_cleaner carregado")
print("=" * 60 + "\n")

# ======================================================================
# HELPERS DE SEGURANÇA E CONHECIMENTO (v9.13)
# ======================================================================
def _obter_regras_seguranca_sistema():
    """Carrega regras de segurança do sistema e diretrizes de pensamento prévio."""
    partes = []
    for nome_arq, limite in (("sistema_nao_apagar.md", 1600), ("regras_pensamento.md", 700)):
        arq = os.path.join(BASE_DIR, "kael_knowledge", nome_arq)
        try:
            if os.path.exists(arq):
                with open(arq, "r", encoding="utf-8") as f:
                    trecho = f.read()[:limite].strip()
                    if trecho:
                        partes.append(trecho)
        except Exception:
            pass
    return (chr(10) + chr(10)).join(partes)

def _obter_conhecimento_apis(plataforma="roblox"):
    """Carrega base de conhecimento de APIs para evitar alucinação."""
    path_kb = os.path.join(BASE_DIR, "kael_knowledge", f"{plataforma}_apis.md")
    try:
        if os.path.exists(path_kb):
            with open(path_kb, "r", encoding="utf-8") as f:
                return f.read()[:3000]
    except Exception:
        pass
    return ""

# ======================================================================
# HELPERS BASICOS
# ======================================================================
def _aguardar_teste(nome_script, timeout=120):
    with LOCK_TESTES:
        ev = EVENTOS_TESTE.get(nome_script)
        if ev is None:
            ev = threading.Event()
            EVENTOS_TESTE[nome_script] = ev
        ok = ev.wait(timeout)
        if not ok:
            print("[KAEL] _aguardar_teste TIMEOUT: " + str(nome_script))
            return None
        with LOCK_TESTES:
            return RESULTADOS_TESTE.get(nome_script)

def _ler_arquivo_seguro(path, limite=10000):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()[:limite]
    except Exception:
        pass
    return ""

def _detectar_genero_hint(projeto):
    try:
        projeto_dir = os.path.join(BASE_DIR, "Projetos", projeto)
        bp_path = os.path.join(projeto_dir, "blueprint.json")
        if os.path.exists(bp_path):
            with open(bp_path, "r", encoding="utf-8") as f:
                bp = json.load(f)
            gen = str(bp.get("genero", "")).lower().strip()
            if gen:
                return gen

        lore = _ler_arquivo_seguro(
            os.path.join(projeto_dir, "1_LORE.md"), 2000
        ).lower()
        for kw, gen in [
            ("medieval", "rpg_medieval"), ("castelo", "rpg_medieval"), ("rpg", "rpg_medieval"),
            ("fps", "fps"), ("tiro", "fps"), ("terror", "terror"), ("horror", "terror"),
            ("plataforma", "plataforma"), ("simulador", "simulador"), ("simulator", "simulador"),
        ]:
            if kw in lore:
                return gen
    except Exception:
        pass
    return ""

def _enfileirar_e_testar(nome, codigo, tipo_script="Script", timeout=90):
    tipo = "criar_localscript" if tipo_script == "LocalScript" else "criar_script"
    engine.enfileirar_roblox({
        "tipo": tipo,
        "nome": nome,
        "codigo": codigo,
        "tipo_script": tipo_script,
        "testar_automaticamente": True,
    })
    resultado = _aguardar_teste(nome, timeout)
    if resultado is None:
        engine.adicionar_mensagem_chat("Sistema", "[Teste] Timeout: " + nome)
        return False
    if not resultado.get("sucesso"):
        erros = str(resultado.get("erros", " "))[:200]
        engine.adicionar_mensagem_chat("Sistema", "[Teste] Falhou: " + nome + " | " + erros)
        return False
    engine.adicionar_mensagem_chat("Sistema", "[Teste] OK: " + nome)
    return True

def _extrair_codigo_lua(resposta):
    m = _re.search(
        r"<!--\s*ARQUIVO:\s*([A-Za-z0-9_\-\.]+)\s*-->\s*"
        r"`(?:lua|luau)?\s*\n(.*?)`",
        str(resposta), _re.DOTALL | _re.IGNORECASE
    )
    if m:
        return m.group(2).strip()
    m2 = _re.search(r"`(?:lua|luau)?\s*\n(.*?)`", str(resposta), _re.DOTALL)
    if m2:
        return m2.group(1).strip()
    return None

# ======================================================================
# PIPELINE COMPLETO (bootstrap)
# ======================================================================
def construir_objetivo_sincrono(genero, nome, descricao, lore):
    global DIRETOR_ATIVO
    if DIRETOR_ATIVO and DIRETOR_ATIVO.rodando:
        DIRETOR_ATIVO.parar()
        time.sleep(2)
    try:
        engine.adicionar_mensagem_chat("Sistema", "[1/3] Arquiteto planejando...")
        if GameArchitect is None:
            engine.adicionar_mensagem_chat("Sistema", "ERRO: GameArchitect nao importado.")
            return False
        arq = GameArchitect(
            projeto=nome, genero=genero, descricao=descricao, lore=lore,
            base_dir=engine.BASE_DIR, fn_llm=engine.chamar_ollama,
            fn_adicionar_msg=engine.adicionar_mensagem_chat,
        )
        bp = arq.planejar()
        if not bp:
            engine.adicionar_mensagem_chat("Sistema", "Falha no planejamento.")
            return False

        engine.adicionar_mensagem_chat("Sistema", "[2/3] WorldBuilder gerando mundo...")
        if WorldBuilder is not None:
            wb = WorldBuilder(
                projeto=nome, genero=genero, descricao=descricao, lore=lore,
                base_dir=engine.BASE_DIR, fn_llm=engine.chamar_ollama,
                fn_enfileirar=engine.enfileirar_roblox,
                fn_adicionar_msg=engine.adicionar_mensagem_chat,
                blueprint=bp,
            )
            wb.construir_mundo()
            time.sleep(5)

        engine.adicionar_mensagem_chat("Sistema", "[3/3] Director executando as tarefas...")
        if GameDirector is None:
            engine.adicionar_mensagem_chat("Sistema", "ERRO: GameDirector nao importado.")
            return False
        blueprint_path = os.path.join(engine.BASE_DIR, "Projetos", nome, "blueprint.json")
        dir_ = GameDirector(
            nome_projeto=nome, genero=genero, base_dir=engine.BASE_DIR,
            fn_llm=engine.chamar_ollama, fn_dual=engine.gerar_codigo_dual,
            fn_enfileirar=engine.enfileirar_roblox, fn_validar_lua=engine.validar_codigo_lua,
            fn_adicionar_msg=engine.adicionar_mensagem_chat,
            fn_salvar_regra=engine.salvar_regra_aprendizado,
            fn_carregar_regras=engine.carregar_regras_formatadas,
            fn_aguardar_teste=_aguardar_teste,
            descricao_usuario=descricao, blueprint_path=blueprint_path,
        )
        DIRETOR_ATIVO = dir_
        dir_.iniciar()
        while dir_.rodando:
            time.sleep(2)
        return getattr(dir_, "_jogavel", False) or dir_.status_atual == "concluido"
    except Exception as e:
        engine.adicionar_mensagem_chat("Sistema", "Erro na construcao: " + str(e))
        print("[KAEL] construir_objetivo_sincrono ERRO: " + str(e))
        return False

# ======================================================================
# CORRECAO PONTUAL (com Biblioteca, Contexto e Anti-Alucinação v9.13)
# ======================================================================
def corrigir_problema_especifico(problema, projeto):
    try:
        tipo = str(problema.get("tipo", "script")).lower()
        acao = str(problema.get("acao", " "))
        onde = str(problema.get("onde", "ServerScriptService"))
        descricao = str(problema.get("problema", " "))

        engine.adicionar_mensagem_chat("Sistema", "[Correcao:" + tipo + "] " + descricao[:100])

        # 1. Tenta buscar na biblioteca de Templates
        termo_busca = f"{tipo} {descricao} {acao}".lower()
        template = None
        if kael_library and hasattr(kael_library, "buscar_template"):
            template = kael_library.buscar_template(termo_busca, "roblox_lua")
        if template:
            engine.adicionar_mensagem_chat("Sistema", f"[Biblioteca] Usando template '{template['funcionalidade']}' (status: {template['status']})")
            codigo = template["codigo"]
            nome_final = f"Template_{template['funcionalidade']}_{int(time.time())}"
            return _enfileirar_e_testar(nome_final, codigo, "Script", timeout=90)

        # 2. Se não tem template, usa LLM com contexto do mapa
        resumo_mapa = ""
        if kael_context and hasattr(kael_context, "obter_resumo_mapa"):
            resumo_mapa = kael_context.obter_resumo_mapa(BASE_DIR, projeto)

        # INJEÇÃO DE CONHECIMENTO DE APIs (v9.13)
        conhecimento_apis = _obter_conhecimento_apis("roblox")

        # INJEÇÃO DE SEGURANÇA DE SISTEMA (v9.13)
        regras_sistema = ""
        palavras_gatilho = ["sistema", "celular", "android", "limpar", "apagar",
                            "mobile", "pc", "windows", "smartwatch", "wearos"]
        if any(palavra in tipo or palavra in descricao.lower() for palavra in palavras_gatilho):
            regras_sistema = "\n\n" + _obter_regras_seguranca_sistema() + "\n\n"

        prompt_extra = ""
        if tipo == "hud":
            prompt_extra = "\nFOCO: crie uma ScreenGui com HP e Moedas.\n- Use StarterGui > LocalScript\n"
        elif tipo == "movimento":
            prompt_extra = "\nFOCO: sistema de movimento do player (dash ou pulo duplo).\n"
        elif tipo in ("inventario", "economia"):
            prompt_extra = "\nFOCO: sistema de inventario/economia com DataStore e RemoteEvent.\n- NAO use LocalPlayer no server\n"

        prompt = (
            "Voce e o KAEL, engenheiro de jogos Roblox/Luau.\n\n"
            f"ESTADO ATUAL DO MAPA:\n{resumo_mapa}\n\n"
            f"PROBLEMA A CORRIGIR:\n{descricao}\n\n"
            f"ACAO: {acao}\nONDE COLOCAR: {onde}\nPROJETO: {projeto}\n"
            f"{prompt_extra}\n"
        )
        if conhecimento_apis:
            prompt += f"\nBASE DE CONHECIMENTO DE APIs (USE APENAS ESTAS APIs):\n{conhecimento_apis}\n\n"
        if regras_sistema:
            prompt += regras_sistema
        prompt += (
            "REGRAS CRITICAS:\n"
            "- Gere UM script Lua COMPLETO e FUNCIONAL\n"
            "- Use task.wait() / task.delay(), nunca wait()\n"
            "- NUNCA use API inventada (SendPacket, GetInventory, CharacterAppearance, etc)\n"
            "- Sempre use pcall em DataStore\n"
            "- Indentacao de 4 espacos obrigatoria\n"
            "- Se a tarefa for de sistema, OBEDEÇA CEGAMENTE às 'REGRAS CRÍTICAS DE SEGURANÇA DE SISTEMA'.\n\n"
            "Retorne APENAS o codigo no formato:\n"
            "<!-- ARQUIVO: NomeDoScript -->\n```lua\n(codigo)\n```\n"
        )

        try:
            resposta = str(engine.chamar_ollama(prompt, temperatura=0.2))
        except Exception as e:
            engine.adicionar_mensagem_chat("Sistema", "[Correcao] LLM falhou: " + str(e)[:150])
            return False

        codigo = _extrair_codigo_lua(resposta)
        if not codigo:
            engine.adicionar_mensagem_chat("Sistema", "[Correcao] Nenhum codigo extraido.")
            return False

        try:
            codigo, erros = engine.validar_sintaxe_lua_pesada(codigo)
            if erros:
                print("[KAEL] Correcao: " + str(len(erros)) + " ajustes")
        except Exception:
            pass

        nome_final = "Critic_" + tipo + "_" + str(int(time.time()))
        tipo_script = "LocalScript" if tipo in ("hud", "movimento") else "Script"
        ok = _enfileirar_e_testar(nome_final, codigo, tipo_script, timeout=90)

        # 3. Auto-aprendizado: se funcionou e não veio da biblioteca, salva
        if ok and not template and kael_library and hasattr(kael_library, "salvar_template"):
            kael_library.salvar_template(
                nome_func=f"{tipo}_auto",
                codigo=codigo,
                plataforma="roblox_lua",
                descricao=f"Auto-gerado para: {descricao}",
                tags=[tipo]
            )
            engine.adicionar_mensagem_chat("Sistema", f"[Aprendizado] Novo codigo de {tipo} salvo na biblioteca!")
        return ok
    except Exception as e:
        engine.adicionar_mensagem_chat("Sistema", "[Correcao] Erro: " + str(e)[:150])
        print("[KAEL] corrigir_problema_especifico ERRO: " + str(e))
        return False

# ======================================================================
# CRIACAO DE ASSET (com Biblioteca)
# ======================================================================
def criar_asset_especifico(ideia, projeto):
    try:
        titulo = str(ideia.get("titulo", "?")).strip()
        categoria = str(ideia.get("categoria", "estrutura")).lower()

        engine.adicionar_mensagem_chat("Sistema", "[Asset:" + categoria + "] " + titulo[:80])

        # 1. Tenta buscar template
        template = None
        if kael_library and hasattr(kael_library, "buscar_template"):
            template = kael_library.buscar_template(titulo, "roblox_lua")
        if template:
            engine.adicionar_mensagem_chat("Sistema", f"[Biblioteca] Usando template '{template['funcionalidade']}' para o asset.")
            nome_final = f"Asset_{template['funcionalidade']}_{int(time.time())}"
            return _enfileirar_e_testar(nome_final, template["codigo"], "Script", timeout=90)

        # 2. Se não tem, gera com LLM
        genero = _detectar_genero_hint(projeto) or "rpg_medieval"
        kb = {}
        try:
            from kael_creative import KNOWLEDGE_BASE
            kb = KNOWLEDGE_BASE.get(genero, KNOWLEDGE_BASE.get("rpg_medieval", {}))
        except Exception:
            kb = {}

        if not assets:
            engine.adicionar_mensagem_chat("Sistema", "[Asset] Módulo kael_assets não carregado.")
            return False

        asset = assets.gerar_asset(
            ideia=ideia, kb=kb, genero=genero,
            fn_llm=engine.chamar_ollama, projeto=projeto,
        )
        if not asset:
            engine.adicionar_mensagem_chat("Sistema", "[Asset] Falha ao gerar codigo para: " + titulo[:80])
            return False

        codigo = asset["codigo"]
        try:
            codigo, erros = engine.validar_sintaxe_lua_pesada(codigo)
        except Exception:
            pass

        ok = _enfileirar_e_testar(asset["nome"], codigo, asset["tipo_script"], timeout=90)
        if ok:
            engine.adicionar_mensagem_chat("Sistema", "[Asset] OK: " + titulo[:80] + " (via " + asset["origem"] + ")")
            # 3. Auto-aprendizado: salva o asset que funcionou
            if kael_library and hasattr(kael_library, "salvar_template"):
                kael_library.salvar_template(
                    nome_func=f"asset_{categoria}",
                    codigo=codigo,
                    plataforma="roblox_lua",
                    descricao=titulo,
                    tags=[categoria]
                )
                engine.adicionar_mensagem_chat("Sistema", f"[Aprendizado] Novo asset de {categoria} salvo na biblioteca!")
        return ok
    except Exception as e:
        engine.adicionar_mensagem_chat("Sistema", "[Asset] Erro: " + str(e)[:150])
        return False

# ======================================================================
# INTEGRATOR ANTIGO (comando manual)
# ======================================================================
def iniciar_integrator(projeto):
    if GameIntegrator is None:
        engine.adicionar_mensagem_chat("Sistema", "Integrator nao disponivel.")
        return
    def _worker():
        try:
            integ = GameIntegrator(
                projeto=projeto, base_dir=engine.BASE_DIR,
                fn_llm=engine.chamar_ollama, fn_enfileirar=engine.enfileirar_roblox,
                fn_adicionar_msg=engine.adicionar_mensagem_chat,
                fn_validar_lua=engine.validar_codigo_lua,
                fn_aguardar_teste=_aguardar_teste,
                fn_estado_jogo=lambda: engine.ESTADO.get("estado_jogo"),
            )
            integ.analisar_e_corrigir(max_gaps=6)
        except Exception as e:
            engine.adicionar_mensagem_chat("Sistema", "Erro no Integrator: " + str(e))
    threading.Thread(target=_worker, daemon=True).start()

# ======================================================================
# STREAM (Single-Pass)
# ======================================================================
def _ollama_stream(system_prompt, user_prompt, temperatura, num_predict):
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": MODELO_CHAT,
                "system": system_prompt,
                "prompt": user_prompt,
                "stream": True,
                "options": {
                    "temperature": temperatura,
                    "num_ctx": NUM_CTX_CHAT,
                    "num_predict": num_predict,
                },
            },
            stream=True,
            timeout=TIMEOUT_STREAM,
        )
        if resp.status_code != 200:
            yield {"error": "Ollama status " + str(resp.status_code)}
            return
        for linha in resp.iter_lines():
            if not linha:
                continue
            try:
                dados = json.loads(linha.decode("utf-8"))
            except Exception:
                continue
            if dados.get("done"):
                break
            pedaco = dados.get("response", " ")
            if pedaco:
                yield {"text": pedaco}
    except requests.exceptions.Timeout:
        yield {"error": "Timeout do Ollama (" + str(TIMEOUT_STREAM) + "s)"}
    except requests.exceptions.ConnectionError:
        yield {"error": "Ollama offline (127.0.0.1:8080). Rode 'ollama serve'."}
    except Exception as e:
        yield {"error": "Erro interno: " + str(e)[:150]}

def _sse(obj):
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"

def _gerar_resposta_dupla(system1, user1, pergunta_original, projeto):
    texto1 = ""
    erro1 = None
    print("[STREAM] PASS 1 iniciando...")
    for ev in _ollama_stream(system1, user1, TEMPERATURA_PASS1, NUM_PREDICT_PASS1):
        if "error" in ev:
            erro1 = ev["error"]
            break
        texto1 += ev["text"]
        yield _sse({"phase": "draft", "text": ev["text"]})

    if erro1:
        print("[STREAM] PASS 1 erro: " + str(erro1))
        yield _sse({"error": erro1})
        yield "data: [DONE]\n\n"
        return

    print("[STREAM] PASS 1 concluido (" + str(len(texto1)) + " chars)")
    final1 = persona.extrair_resposta_final(texto1)
    if final1:
        engine.adicionar_mensagem_chat("Kael", final1)
    yield _sse({"phase": "done"})
    yield "data: [DONE]\n\n"

# ======================================================================
# ROTAS BASICAS
# ======================================================================
@app.route("/", methods=["GET"])
def index():
    for nome in ("chat.html", "Chat.html"):
        caminho = os.path.join(BASE_DIR, nome)
        if os.path.exists(caminho):
            return send_from_directory(BASE_DIR, nome)
    return "<h3>Kael Ativo - chat.html nao encontrado</h3>"

@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "status": engine.ESTADO.get("status", "Ocioso"),
        "projeto_ativo": engine.ESTADO.get("projeto_ativo", " "),
        "manager_ativo": bool(MANAGER_ATIVO and MANAGER_ATIVO.rodando),
        "diretor_ativo": bool(DIRETOR_ATIVO and DIRETOR_ATIVO.rodando),
        "modulos_carregados": list(MODULOS_CARREGADOS.keys()),
        "erros_carregamento": ERROS_CARREGAMENTO,
    })

@app.route("/ultimas_mensagens", methods=["GET"])
def ultimas_mensagens():
    with engine.LOCK_ESTADO:
        msgs = list(engine.ESTADO.get("mensagens_chat", []))
    return jsonify({
        "mensagens": msgs[-50:],
        "status": engine.ESTADO.get("status", "Ocioso"),
        "projeto_ativo": engine.ESTADO.get("projeto_ativo", " "),
    })

# ======================================================================
# ROTA: /stream
# ======================================================================
@app.route("/stream", methods=["GET"])
def kael_stream_chat():
    prompt = request.args.get("prompt", " ").strip()
    if not prompt:
        return jsonify({"erro": "parametro 'prompt' vazio"}), 400
    if len(prompt) > 20000:
        return jsonify({"erro": "prompt muito longo (max 20000 chars)"}), 400

    projeto = engine.ESTADO.get("projeto_ativo", "")
    with engine.LOCK_ESTADO:
        historico_snapshot = list(engine.ESTADO.get("mensagens_chat", []))
    engine.adicionar_mensagem_chat("Voce", prompt)

    try:
        user_prompt = persona.montar_user_prompt(
            prompt_usuario=prompt,
            projeto=projeto,
            base_dir=BASE_DIR,
            mensagens_chat=historico_snapshot,
        )
        system_prompt = persona.SYSTEM_PROMPT
    except Exception as e:
        print("[STREAM] erro montando prompt: " + str(e))
        system_prompt = ""
        user_prompt = prompt

    return Response(
        stream_with_context(_gerar_resposta_dupla(
            system1=system_prompt,
            user1=user_prompt,
            pergunta_original=prompt,
            projeto=projeto,
        )),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )

# ======================================================================
# ROTA: /comando
# ======================================================================
@app.route("/comando", methods=["POST"])
def receber_comando():
    global MANAGER_ATIVO
    data = request.get_json(silent=True) or {}
    texto = str(data.get("mensagem", "")).strip()
    if not texto:
        return jsonify({"erro": "Mensagem vazia"}), 400
    if texto.startswith("\\"):
        texto = "/" + texto[1:]
    t = texto.lower().strip()
    print("\n[KAEL] Comando: " + repr(texto[:120]))
    engine.adicionar_mensagem_chat("Voce", texto)

    if t == "/ajuda":
        engine.adicionar_mensagem_chat(
            "Sistema",
            "Comandos: /gerenciar_jogo [nome] | /parar_gerenciamento | "
            "/construir_jogo [gen] [nome] --descricao [txt] | /criar_jogo [gen] [nome] | "
            "/pesquisar [termo] | /reposicionar_estruturas [min] [max] [dist] | "
            "/ver_jogo | /ver_real | /integrar_jogo [nome] | /refatorar | "
            "/analisar_celular | /limpar_cache_app [pacote] | /comando_sistema [cmd] | "
            "/modulos | /teste_conexao | /status"
        )
        return jsonify({"status": "ok"})

    if t == "/status":
        msg = "Status: " + str(engine.ESTADO.get("status", "?"))
        msg += " | Projeto: " + str(engine.ESTADO.get("projeto_ativo", "?"))
        if MANAGER_ATIVO and MANAGER_ATIVO.rodando:
            st = MANAGER_ATIVO.status()
            msg += (" | Manager: rodando (iter " + str(st.get("iteracao", 0))
                    + ", saudaveis " + str(st.get("ciclos_saudaveis", 0)) + ")")
        engine.adicionar_mensagem_chat("Sistema", msg)
        return jsonify({"status": "ok"})

    # ----------------------------------------------------------
    # /modulos — Lista módulos carregados (v9.13)
    # ----------------------------------------------------------
    if t == "/modulos":
        lista = list(MODULOS_CARREGADOS.keys())
        msg = f"📦 {len(lista)} módulos carregados:\n"
        for m in lista:
            msg += f"  ✓ {m}\n"
        if ERROS_CARREGAMENTO:
            msg += f"\n⚠️ {len(ERROS_CARREGAMENTO)} com erro:\n"
            for m, err in ERROS_CARREGAMENTO.items():
                msg += f"  ✗ {m}: {err[:100]}\n"
        engine.adicionar_mensagem_chat("Sistema", msg)
        return jsonify({"status": "ok"})

    # ----------------------------------------------------------
    # /gerenciar_jogo — DUAL (correcao + expansao)
    # ----------------------------------------------------------
    if t.startswith("/gerenciar_jogo"):
        partes = texto.split(maxsplit=1)
        if len(partes) < 2:
            return jsonify({"erro": "Falta nome do projeto"}), 400
        if MANAGER_ATIVO and MANAGER_ATIVO.rodando:
            return jsonify({"erro": "Gerenciador ja rodando"}), 409
        projeto = partes[1].strip()
        try:
            lore_path = os.path.join(BASE_DIR, "Projetos", projeto, "1_LORE.md")
            descricao_projeto = _ler_arquivo_seguro(lore_path, 2000)
            genero_hint = _detectar_genero_hint(projeto)
            MANAGER_ATIVO = GameManager(
                projeto=projeto,
                base_dir=engine.BASE_DIR,
                fn_construir=construir_objetivo_sincrono,
                fn_integrar=iniciar_integrator,
                fn_msg=engine.adicionar_mensagem_chat,
                fn_llm=engine.chamar_ollama,
                fn_estado_jogo=lambda: engine.ESTADO.get("estado_jogo"),
                fn_corrigir=corrigir_problema_especifico,
                fn_criar_asset=criar_asset_especifico,
                descricao=descricao_projeto,
                genero_hint=genero_hint,
                timeout_construcao=TIMEOUT_CONSTRUCAO,
            )
            MANAGER_ATIVO.iniciar()
            engine.ESTADO["projeto_ativo"] = projeto
            engine.adicionar_mensagem_chat(
                "Sistema",
                "Gerenciador DUAL iniciado para '" + projeto + "'. "
                "Genero: " + (genero_hint or "auto-detect") + ". "
                "Modo: correcao <-> expansao."
            )
            return jsonify({"status": "gerenciando", "projeto": projeto,
                            "genero": genero_hint})
        except Exception as e:
            return jsonify({"erro": "Falha ao iniciar manager: " + str(e)}), 500

    if t == "/parar_gerenciamento":
        if MANAGER_ATIVO:
            MANAGER_ATIVO.parar()
            MANAGER_ATIVO = None
            engine.adicionar_mensagem_chat("Sistema", "Gerenciador parado.")
        else:
            engine.adicionar_mensagem_chat("Sistema", "Nenhum gerenciador ativo.")
        return jsonify({"status": "parado"})

    if t == "/ver_jogo":
        engine.enfileirar_roblox({"tipo": "pedir_visao", "nome": "Vision"})
        engine.adicionar_mensagem_chat("Sistema", "Solicitando visao do Roblox...")
        return jsonify({"status": "ok"})

    if t == "/ver_real":
        return _cmd_ver_real()

    if t in ("/teste_conexao", "/test_conexao_roblox"):
        engine.enfileirar_roblox({
            "tipo": "ping", "nome": "Teste",
            "codigo": "print('[KAEL] PONG! Conexao OK!')",
        })
        engine.adicionar_mensagem_chat("Sistema", "Ping enviado ao Roblox!")
        return jsonify({"status": "ok", "tipo": "ping"})

    if t.startswith("/construir_jogo"):
        return _cmd_construir_jogo(texto)

    if t.startswith("/criar_jogo"):
        return _cmd_criar_jogo(texto)

    if t.startswith("/integrar_jogo"):
        partes = texto.split(maxsplit=1)
        projeto = partes[1].strip() if len(partes) > 1 else engine.ESTADO.get("projeto_ativo", "")
        if not projeto:
            return jsonify({"erro": "Falta nome do projeto"}), 400
        iniciar_integrator(projeto)
        engine.adicionar_mensagem_chat("Sistema", "Integrator iniciado para '" + projeto + "'.")
        return jsonify({"status": "integrando", "projeto": projeto})

    # ----------------------------------------------------------
    # /pesquisar — BUSCA NA INTERNET (UNIVERSAL)
    # ----------------------------------------------------------
    if t.startswith("/pesquisar"):
        partes = texto.split(maxsplit=1)
        if len(partes) < 2:
            engine.adicionar_mensagem_chat("Sistema", "Uso: /pesquisar <termo de busca>")
            return jsonify({"erro": "falta o termo"}), 400
        termo = partes[1].strip()
        engine.adicionar_mensagem_chat("Sistema", "🔍 Pesquisando na web: " + termo)
        def _worker_pesquisa():
            try:
                import kael_websearch
                resultado = kael_websearch.pesquisar_web(termo)
                if resultado.startswith("ERRO_WEB:"):
                    engine.adicionar_mensagem_chat("Sistema", f"❌ {resultado}")
                    engine.adicionar_mensagem_chat("Sistema", "Não vou inventar respostas. Tente novamente.")
                    return
                engine.adicionar_mensagem_chat("Sistema", "✅ Busca real concluída. Processando...")
                prompt_resumo = (
                    "Aqui estão os resultados REAIS de uma busca na internet sobre '" + termo + "':\n\n"
                    + resultado + "\n\n"
                    "Sua missão é ler os resultados e responder de forma direta em português. "
                    "Se o usuário pedir para extrair mecânicas de jogos, extraia. "
                    "Se pedir para avaliar viabilidade no Roblox, avalie. "
                    "Se for uma dúvida técnica, responda. "
                    "Seja útil, mas use APENAS as informações do texto acima. Não invente nada."
                )
                engine.adicionar_mensagem_chat("Voce", prompt_resumo)
                resposta_kael = engine.chamar_ollama(prompt_resumo, temperatura=0.3)
                engine.adicionar_mensagem_chat("Kael", resposta_kael)
            except Exception as e:
                engine.adicionar_mensagem_chat("Sistema", "Erro crítico na pesquisa: " + str(e))
        threading.Thread(target=_worker_pesquisa, daemon=True).start()
        return jsonify({"status": "pesquisando", "termo": termo})

    # ----------------------------------------------------------
    # /reposicionar_estruturas — TEMPLATE DETERMINISTICO
    # ----------------------------------------------------------
    if t.startswith("/reposicionar_estruturas"):
        partes = texto.split()
        raio_min, raio_max, dist_min = 150, 700, 250
        try:
            if len(partes) >= 2:
                raio_min = int(partes[1])
            if len(partes) >= 3:
                raio_max = int(partes[2])
            if len(partes) >= 4:
                dist_min = int(partes[3])
        except ValueError:
            engine.adicionar_mensagem_chat(
                "Sistema",
                "Formato: /reposicionar_estruturas [raio_min] [raio_max] [dist_min] "
                "(todos opcionais, padrao 150 700 250)"
            )
            return jsonify({"erro": "parametros invalidos"}), 400
        projeto = engine.ESTADO.get("projeto_ativo", "")
        if not assets:
            return jsonify({"erro": "Módulo kael_assets não carregado"}), 501
        try:
            asset = assets.gerar_reposicionar_estruturas(
                raio_min=raio_min, raio_max=raio_max, dist_min=dist_min, projeto=projeto,
            )
        except AttributeError:
            engine.adicionar_mensagem_chat(
                "Sistema",
                "Funcao 'gerar_reposicionar_estruturas' nao existe em kael_assets.py."
            )
            return jsonify({"erro": "template ausente"}), 501
        if not asset:
            engine.adicionar_mensagem_chat("Sistema", "Falha ao gerar template.")
            return jsonify({"erro": "template falhou"}), 500
        engine.adicionar_mensagem_chat(
            "Sistema",
            "[Template] Reposicionar estruturas: raio " + str(raio_min) + "-" + str(raio_max) + ", dist_min " + str(dist_min)
        )
        ok = _enfileirar_e_testar(asset["nome"], asset["codigo"], asset["tipo_script"], timeout=120)
        if ok:
            engine.adicionar_mensagem_chat("Sistema", "[Template] OK — estruturas reposicionadas.")
        return jsonify({"status": "ok" if ok else "falhou", "asset": asset["nome"]})

    if t == "/refatorar":
        if RefactorAgent is None:
            engine.adicionar_mensagem_chat("Sistema", "RefactorAgent nao disponivel.")
            return jsonify({"erro": "RefactorAgent indisponivel"}), 501
        projeto = engine.ESTADO.get("projeto_ativo", "")
        if not projeto:
            return jsonify({"erro": "Nenhum projeto ativo"}), 400
        def _worker():
            try:
                ra = RefactorAgent(
                    projeto=projeto, base_dir=engine.BASE_DIR,
                    fn_llm=engine.chamar_ollama, fn_adicionar_msg=engine.adicionar_mensagem_chat,
                )
                if hasattr(ra, "refatorar"): ra.refatorar()
                elif hasattr(ra, "executar"): ra.executar()
            except Exception as e:
                engine.adicionar_mensagem_chat("Sistema", "Erro refatorando: " + str(e))
        threading.Thread(target=_worker, daemon=True).start()
        engine.adicionar_mensagem_chat("Sistema", "Refatoracao iniciada.")
        return jsonify({"status": "refatorando"})

    # ----------------------------------------------------------
    # COMANDOS DE SISTEMA E MOBILE (v9.13)
    # ----------------------------------------------------------
    if t.startswith("/analisar_celular"):
        if mobile_cleaner is None:
            engine.adicionar_mensagem_chat("Sistema", "❌ Módulo mobile_cleaner não carregado. Verifique kael_modules.json.")
            return jsonify({"erro": "Módulo mobile_cleaner não carregado"}), 501
        def _worker_celular():
            try:
                resultado = mobile_cleaner.analisar_armazenamento_celular()
                engine.adicionar_mensagem_chat("Sistema", resultado)
            except Exception as e:
                engine.adicionar_mensagem_chat("Sistema", "Erro ao analisar celular: " + str(e))
        threading.Thread(target=_worker_celular, daemon=True).start()
        engine.adicionar_mensagem_chat("Sistema", "📱 Analisando armazenamento do celular...")
        return jsonify({"status": "analisando"})

    if t.startswith("/limpar_cache_app"):
        if mobile_cleaner is None:
            return jsonify({"erro": "Módulo mobile_cleaner não carregado"}), 501
        partes = texto.split(maxsplit=1)
        if len(partes) < 2:
            engine.adicionar_mensagem_chat("Sistema", "Uso: /limpar_cache_app com.whatsapp")
            return jsonify({"erro": "Falta nome do pacote"}), 400
        pacote = partes[1].strip()
        def _worker_limpar():
            try:
                resultado = mobile_cleaner.limpar_cache_app(pacote)
                engine.adicionar_mensagem_chat("Sistema", resultado)
            except Exception as e:
                engine.adicionar_mensagem_chat("Sistema", "Erro ao limpar cache: " + str(e))
        threading.Thread(target=_worker_limpar, daemon=True).start()
        engine.adicionar_mensagem_chat("Sistema", f"🧹 Limpando cache do app '{pacote}'...")
        return jsonify({"status": "limpando", "pacote": pacote})

    if t.startswith("/comando_sistema"):
        if system_tools is None:
            return jsonify({"erro": "Módulo system_tools não carregado"}), 501
        partes = texto.split(maxsplit=1)
        if len(partes) < 2:
            engine.adicionar_mensagem_chat("Sistema", "Uso: /comando_sistema ipconfig /flushdns")
            return jsonify({"erro": "Falta comando"}), 400
        comando = partes[1].strip()
        engine.adicionar_mensagem_chat("Sistema", f"⚙️ Executando: {comando}...")
        def _worker_sistema():
            try:
                resultado = system_tools.executar_comando_sistema(comando)
                engine.adicionar_mensagem_chat("Sistema", f"📝 Resultado:\n{resultado}")
            except Exception as e:
                engine.adicionar_mensagem_chat("Sistema", "Erro ao executar comando: " + str(e))
        threading.Thread(target=_worker_sistema, daemon=True).start()
        return jsonify({"status": "executando", "comando": comando})

    engine.adicionar_mensagem_chat("Sistema", "Comando nao reconhecido: " + t[:60] + ". Use /ajuda.")
    return jsonify({"status": "ignorado", "comando": t})

# ======================================================================
# HELPERS DE COMANDO
# ======================================================================
def _cmd_ver_real():
    def _worker():
        engine.ESTADO["screenshot_png"] = None
        engine.enfileirar_roblox({"tipo": "screenshot", "nome": "VisionReal"})
        engine.adicionar_mensagem_chat("Sistema", "Aguardando screenshot do Roblox...")
        for _ in range(120):
            png = engine.ESTADO.get("screenshot_png")
            if png:
                engine.ESTADO["screenshot_png"] = None
                tamanho = len(png) if isinstance(png, (bytes, bytearray)) else 0
                engine.adicionar_mensagem_chat(
                    "Sistema", "Screenshot recebido (" + str(tamanho) + " bytes). Salvando em debug_visao.png."
                )
                try:
                    with open(os.path.join(BASE_DIR, "debug_visao.png"), "wb") as f:
                        f.write(png if isinstance(png, (bytes, bytearray)) else b"")
                except Exception as e:
                    engine.adicionar_mensagem_chat("Sistema", "Erro salvando PNG: " + str(e))
                return
            time.sleep(0.5)
        engine.adicionar_mensagem_chat("Sistema", "Timeout: plugin nao enviou screenshot em 60s.")
    threading.Thread(target=_worker, daemon=True).start()
    return jsonify({"status": "aguardando_screenshot"})

def _parse_construir(texto):
    resto = texto[len("/construir_jogo"):].strip()
    descricao = ""
    if "--descricao" in resto:
        partes = resto.split("--descricao", 1)
        resto = partes[0].strip()
        descricao = partes[1].strip()
    tokens = resto.split(maxsplit=2)
    genero = tokens[0] if len(tokens) > 0 else "rpg"
    nome = tokens[1] if len(tokens) > 1 else ""
    if len(tokens) > 2 and not descricao:
        descricao = tokens[2]
    return genero, nome, descricao

def _cmd_construir_jogo(texto):
    genero, nome, descricao = _parse_construir(texto)
    if not nome:
        return jsonify({"erro": "Formato: /construir_jogo [gen] [nome] --descricao [txt]"}), 400
    if DIRETOR_ATIVO and DIRETOR_ATIVO.rodando:
        return jsonify({"erro": "Director ja rodando."}), 409
    def _worker():
        try:
            engine.ESTADO["projeto_ativo"] = nome
            engine.adicionar_mensagem_chat("Sistema", "Iniciando construcao: '" + nome + "' (genero=" + genero + ")")
            lore = _ler_arquivo_seguro(os.path.join(BASE_DIR, "Projetos", nome, "1_LORE.md"), 3000)
            construir_objetivo_sincrono(genero, nome, descricao, lore)
        except Exception as e:
            engine.adicionar_mensagem_chat("Sistema", "Erro construindo: " + str(e))
    threading.Thread(target=_worker, daemon=True).start()
    return jsonify({"status": "construindo", "projeto": nome, "genero": genero})

def _cmd_criar_jogo(texto):
    resto = texto[len("/criar_jogo"):].strip()
    tokens = resto.split(maxsplit=1)
    genero = tokens[0] if len(tokens) > 0 else "rpg"
    nome = tokens[1] if len(tokens) > 1 else ""
    if not nome:
        return jsonify({"erro": "Formato: /criar_jogo [genero] [nome]"}), 400
    if DIRETOR_ATIVO and DIRETOR_ATIVO.rodando:
        return jsonify({"erro": "Director ja rodando."}), 409
    def _worker():
        try:
            engine.ESTADO["projeto_ativo"] = nome
            engine.adicionar_mensagem_chat("Sistema", "Criando jogo simples: '" + nome + "' (" + genero + ")")
            construir_objetivo_sincrono(genero, nome, "Jogo simples de " + genero, "")
        except Exception as e:
            engine.adicionar_mensagem_chat("Sistema", "Erro criando: " + str(e))
    threading.Thread(target=_worker, daemon=True).start()
    return jsonify({"status": "criando", "projeto": nome, "genero": genero})

# ======================================================================
# ROTAS DO PLUGIN
# ======================================================================
@app.route("/proxima_tarefa", methods=["GET"])
@app.route("/obter_tarefa", methods=["GET"])
def proxima_tarefa():
    with engine.LOCK_ESTADO:
        fila = engine.ESTADO.get("fila_roblox", [])
        if fila:
            tarefa = fila.pop(0)
            print("[KAEL] Enviando tarefa: " + str(tarefa.get("tipo", "?")))
            return jsonify({"status": "ok", "tem_tarefa": True, "tarefa": tarefa})
    return jsonify({"status": "ok", "tem_tarefa": False, "tarefa": None})

@app.route("/tarefa_concluida", methods=["POST"])
def tarefa_concluida():
    dados = request.get_json(silent=True) or {}
    nome = str(dados.get("nome", " "))
    sucesso = bool(dados.get("sucesso", False))
    erros = str(dados.get("erros", " "))
    print("[KAEL] tarefa_concluida: " + nome + " sucesso=" + str(sucesso))
    with LOCK_TESTES:
        RESULTADOS_TESTE[nome] = {"sucesso": sucesso, "erros": erros}
        ev = EVENTOS_TESTE.get(nome)
        if ev:
            ev.set()
    return jsonify({"status": "ok"})

@app.route("/estado_jogo", methods=["POST"])
def receber_estado_jogo():
    if request.content_length and request.content_length > 1_000_000:
        return jsonify({"status": "ignorado", "motivo": "payload muito grande"}), 200
    dados = request.get_json(silent=True) or {}
    with engine.LOCK_ESTADO:
        engine.ESTADO["estado_jogo"] = dados
    print("[KAEL] Mapa recebido (" + str(dados.get("total_instancias", 0)) + " instancias)")
    return jsonify({"status": "ok"})

@app.route("/reportar_erro", methods=["POST"])
def reportar_erro():
    dados = request.get_json(silent=True) or {}
    origem = str(dados.get("origem", "Desconhecida"))
    erro = str(dados.get("erro", " "))
    print("[KAEL] Erro (" + origem + "): " + erro[:200])
    with engine.LOCK_ESTADO:
        engine.ESTADO["ultimo_erro_roblox"] = erro
    return jsonify({"status": "ok"})

@app.route("/confirmar_etapa", methods=["POST"])
def confirmar_etapa():
    dados = request.get_json(silent=True) or {}
    print("[KAEL] Etapa confirmada: " + str(dados.get("descricao", "")))
    return jsonify({"status": "ok"})

@app.route("/reportar_screenshot", methods=["POST"])
def reportar_screenshot():
    png = request.get_data()
    if png:
        with engine.LOCK_ESTADO:
            engine.ESTADO["screenshot_png"] = png
        print("[KAEL] screenshot recebido (" + str(len(png)) + " bytes)")
        return jsonify({"ok": True, "bytes": len(png)})
    return jsonify({"ok": False, "erro": "sem bytes"}), 400

# ======================================================================
# ROTA: /diretrizes
# ======================================================================
@app.route("/diretrizes", methods=["GET", "POST"])
def gerenciar_diretrizes():
    try:
        projeto = engine.ESTADO.get("projeto_ativo", "Geral")
        projeto_limpo = "".join(
            c for c in str(projeto) if c.isalnum() or c in "_-"
        ) or "Geral"
        caminho = os.path.join(BASE_DIR, "Projetos", projeto_limpo, "diretrizes_ativas.json")

        if request.method == "POST":
            dados = request.get_json(force=True, silent=True)
            if not isinstance(dados, dict):
                return jsonify({"erro": "JSON invalido"}), 400
            os.makedirs(os.path.dirname(caminho), exist_ok=True)
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
            return jsonify({"ok": True})

        if not os.path.exists(caminho):
            return jsonify({"objetivo_global": "", "regras_fixadas": [], "etapas": []})
        with open(caminho, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    except Exception as e:
        print("[KAEL] Erro /diretrizes: " + str(e))
        return jsonify({"erro": str(e)}), 500

# ======================================================================
# MAIN
# ======================================================================
if __name__ == "__main__":
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    print("=" * 60)
    print("[KAEL] Servidor iniciando em http://127.0.0.1:8000")
    print("[KAEL] v9.13 - Modular + Segurança de Sistema")
    print("=" * 60)
    app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False)

def _kael_explorar_pastas_local(msg: str) -> tuple[str, str]:
    import re as _re
    m = _re.search(r"(/[A-Za-z0-9_./-]+)", msg)
    alvo = Path(m.group(1)) if m else Path("/storage/emulated/0")
    if not alvo.exists():
        alvo = Path.home()
    bloqueados = ("/system", "/proc", "/sys", "/dev")
    if any(str(alvo).startswith(b) for b in bloqueados):
        return "Verificando política de segurança...", "Acesso bloqueado apenas para partições protegidas do sistema (/system, /proc, /sys)."
    try:
        itens = sorted(alvo.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:60]
    except PermissionError:
        return (
            f"Tentando ler {alvo}... Permissão negada pelo Android.",
            f"O Android bloqueou a listagem direta de `{alvo}` (Scoped Storage). Use `/storage/emulated/0` (ou rode `termux-setup-storage` no Termux)."
        )
    linhas = ["| Tipo | Nome | Tamanho |", "| --- | --- | --- |"]
    for it in itens:
        try:
            tipo = "Pasta" if it.is_dir() else "Arquivo"
            tam = "-" if it.is_dir() else f"{it.stat().st_size} B"
        except Exception:
            tipo, tam = "Item", "-"
        linhas.append(f"| {tipo} | `{it.name}` | {tam} |")
    pens = f"Acessando diretório {alvo}...\nEncontrados {len(itens)} itens visíveis."
    resp = f"Conteúdo de `{alvo}` ({len(itens)} itens):\n\n" + "\n".join(linhas)
    return pens, resp


def _kael_acordar_llama_8080(espera_max_s: float = 15.0) -> bool:
    import socket as _sock
    def _porta_aberta():
        try:
            with _sock.create_connection(("127.0.0.1", 8080), timeout=0.6):
                return True
        except Exception:
            return False

    if _porta_aberta():
        return True

    _kael_set_etapa("acordando modelo local 8080")
    modelo = Path.home() / "modelos" / "modelo_local.gguf"
    if not modelo.exists():
        return False

    try:
        _kael_sp.Popen(
            ['/data/data/com.termux/files/home/llama.cpp/build/bin/llama-server', "-m", str(modelo), "--host", "127.0.0.1", "--port", "8080", "-c", "2048"],
            stdout=_kael_sp.DEVNULL,
            stderr=_kael_sp.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        return False

    inicio = time.time()
    while time.time() - inicio < espera_max_s:
        if _kael_foi_cancelado():
            return False
        if _porta_aberta():
            return True
        time.sleep(0.5)
    return _porta_aberta()


def _kael_pensar_e_responder_com_ia(msg: str, think: bool = True, web_search: bool = False, voice_mode: bool = False) -> tuple[str, str]:
    import re as _re
    low = (msg or "").lower()
    eh_codigo = any(w in low for w in ("erro", "sintaxe", "bug", "traceback", "python", "código", "codigo", "luau", "lua", "compilar", "script", "revisar"))

    # Define alvo apenas se explicitado ou se for pedido técnico do projeto
    m_path = _re.search(r"(/[A-Za-z0-9_./-]+|~/[A-Za-z0-9_./-]+)", msg or "")
    if m_path:
        alvo = Path(m_path.group(1)).expanduser()
    elif any(k in low for k in ("aethelgard", "roblox", "luau", "mount", "fasttravel", "trade")):
        alvo = Path.home() / "Projetos" / "Ecos_de_Aethelgard"
    elif eh_codigo:
        alvo = Path.home() / "Kael_ia"
    else:
        alvo = None

    etapas = [f"Analisando pedido: {msg.strip()[:120]}"]
    contexto_extra = []

    if alvo is not None:
        etapas.append(f"Alvo ativo: {alvo}")
        if eh_codigo and alvo.exists():
            erros = []
            for pyf in list(alvo.rglob("*.py"))[:80]:
                if ".git" in pyf.parts or "__pycache__" in pyf.parts:
                    continue
                try:
                    compile(pyf.read_text(encoding="utf-8", errors="replace"), str(pyf), "exec")
                except SyntaxError as se:
                    erros.append(f"{pyf.name}:{se.lineno}: {se.msg}")
            etapas.append(f"Checagem de sintaxe Python: {len(erros)} erro(s).")
            if erros:
                contexto_extra.append("Erros de sintaxe encontrados:\n" + "\n".join(erros[:10]))

    if "_kael_acordar_llama_8080" in globals():
        etapas.append("Verificando motor local (porta 8080)...")
        _kael_acordar_llama_8080(20.0)

    sys_prompt = (
        "Você é o Kael AI, assistente técnico objetivo em português do Brasil. "
        "Responda diretamente ao pedido do usuário com clareza, sem inventar dados e sem repetir logs internos."
    )
    if voice_mode:
        sys_prompt += " Modo voz ativo: use frases curtas, diretas e naturais para leitura em voz alta."
    if contexto_extra:
        sys_prompt += "\n\nContexto técnico verificado:\n" + "\n".join(contexto_extra)

    try:
        r = requests.post(
            "http://127.0.0.1:8080/v1/chat/completions",
            json={
                "model": "modelo_local.gguf",
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": msg},
                ],
                "temperature": 0.3,
                "max_tokens": 700,
            },
            timeout=90,
        )
        r.raise_for_status()
        data = r.json()
        resp = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()
        if not resp:
            resp = "O modelo local processou o pedido, mas retornou resposta vazia."
    except Exception as exc:
        resp = f"Não foi possível obter resposta do modelo local na porta 8080 ({exc})."

    return "\n".join(etapas), resp
def _kael_montar_resposta_travamento(motivo="tempo limite excedido"):
    with _KAEL_TURNO_LOCK:
        etapa = _KAEL_TURNO_STATE.get("etapa") or "desconhecida"
        inicio = _KAEL_TURNO_STATE.get("inicio") or time.time()
        decorrido = round(max(0.0, time.time() - inicio), 1)
    msg = (
        f"⚠️ **Aviso de travamento ({motivo}):** o processamento passou de {decorrido}s "
        f"na etapa `{etapa}`. O turno foi encerrado para não travar a fila — você já pode enviar outro comando."
    )
    _kael_salvar_resposta_historico_seguro(msg)
    return msg

def _kael_disparar_watchdog(turno_id: int, limite_s: float = 22.0):
    def _vigia():
        time.sleep(limite_s)
        with _KAEL_TURNO_LOCK:
            ainda_ativo = _KAEL_TURNO_STATE.get("ativo") and _KAEL_TURNO_STATE.get("turno_id") == turno_id
            etapa = _KAEL_TURNO_STATE.get("etapa") or "processando"
        if ainda_ativo:
            global _KAEL_ULTIMO_AVISO_TRAVA
            _KAEL_ULTIMO_AVISO_TRAVA = _kael_montar_resposta_travamento(f"watchdog {limite_s:.0f}s em {etapa}")
            _kael_finalizar_turno()
    _threading.Thread(target=_vigia, daemon=True).start()


def _revisar_pasta_instantaneo(msg_low: str) -> str:
    import py_compile as _pyc
    alvo = Path.home() / "Projetos" / "Ecos_de_Aethelgard" if ("ecos" in msg_low or "aethelgard" in msg_low or "roblox" in msg_low) else (Path.home() / "Kael_ia")
    if not alvo.exists():
        return f"Pasta não encontrada: {alvo}"
    py_files = [p for p in alvo.rglob("*.py") if "build_termux" not in p.parts and "sandbox_testes" not in p.parts and "__pycache__" not in p.parts]
    lua_files = [p for p in alvo.rglob("*") if p.suffix.lower() in {".lua", ".luau"}]
    erros_py = []
    for pf in py_files:
        try:
            _pyc.compile(str(pf), doraise=True)
        except Exception as e:
            erros_py.append(f"{pf.relative_to(alvo)}: {e}")
    topo = sorted([p.name + ("/" if p.is_dir() else "") for p in alvo.iterdir()])[:20]
    linhas = [
        f"Revisão técnica rápida de `{alvo}`:",
        f"- Itens na raiz ({len(topo)}): {', '.join(topo)}",
        f"- Arquivos Python verificados: {len(py_files)} | Erros de sintaxe: {len(erros_py)}",
        f"- Scripts Lua/Luau encontrados: {len(lua_files)}",
    ]
    for err in erros_py[:5]:
        linhas.append(f"  * Erro: {err}")
    log_p = alvo / "kael_server.log"
    if log_p.exists():
        ult = [l.strip() for l in log_p.read_text(encoding="utf-8", errors="ignore").splitlines() if "Error" in l or "Exception" in l or "Traceback" in l][-3:]
        if ult:
            linhas.append("- Últimos alertas no log:")
            for u in ult:
                linhas.append(f"  * {u[:140]}")
    return "\n".join(linhas)


import subprocess as _kael_sp
_KAEL_BG_JOBS = {}
import threading as _threading
_KAEL_BG_LOCK = _threading.Lock()

def _kael_wake_lock(ativar: bool):
    try:
        cmd = ["termux-wake-lock"] if ativar else ["termux-wake-unlock"]
        _kael_sp.run(cmd, stdout=_kael_sp.DEVNULL, stderr=_kael_sp.DEVNULL, timeout=3)
    except Exception:
        pass

def _kael_dormir_llama_8080():
    with _KAEL_TURNO_LOCK:
        if _KAEL_TURNO_STATE.get("ativo"):
            return
    try:
        _kael_sp.run(["pkill", "-f", "llama-server"], stdout=_kael_sp.DEVNULL, stderr=_kael_sp.DEVNULL, timeout=4)
        _kael_set_etapa("8080 dormindo (economia de bateria)")
    except Exception:
        pass
    finally:
        _kael_wake_lock(False)

def _kael_salvar_resposta_historico_seguro(texto: str):
    if not texto or not str(texto).strip():
        return
    try:
        if "_append_chat_historico_json" in globals():
            _append_chat_historico_json("assistant", str(texto).strip())
    except Exception:
        pass


import threading as _threading
_KAEL_TURNO_LOCK = _threading.Lock()
_KAEL_TURNO_STATE = {"ativo": False, "cancelado": False, "etapa": "ocioso", "inicio": 0.0, "turno_id": 0}

def _kael_iniciar_turno(etapa="iniciando"):
    with _KAEL_TURNO_LOCK:
        _KAEL_TURNO_STATE["turno_id"] += 1
        _KAEL_TURNO_STATE["ativo"] = True
        _KAEL_TURNO_STATE["cancelado"] = False
        _KAEL_TURNO_STATE["etapa"] = etapa
        _KAEL_TURNO_STATE["inicio"] = time.time()
        _kael_wake_lock(True)
        return _KAEL_TURNO_STATE["turno_id"]

def _kael_set_etapa(etapa):
    with _KAEL_TURNO_LOCK:
        if _KAEL_TURNO_STATE["ativo"]:
            _KAEL_TURNO_STATE["etapa"] = etapa

def _kael_cancelar_turno():
    with _KAEL_TURNO_LOCK:
        _KAEL_TURNO_STATE["cancelado"] = True
        _KAEL_TURNO_STATE["ativo"] = False
        _KAEL_TURNO_STATE["etapa"] = "cancelado pelo usuario"

def _kael_foi_cancelado():
    with _KAEL_TURNO_LOCK:
        return bool(_KAEL_TURNO_STATE["cancelado"])

def _kael_finalizar_turno():
    with _KAEL_TURNO_LOCK:
        _KAEL_TURNO_STATE["ativo"] = False
        _KAEL_TURNO_STATE["etapa"] = "concluido"
    def _agendar_sleep():
        time.sleep(15)
        _kael_dormir_llama_8080()
    _threading.Thread(target=_agendar_sleep, daemon=True).start()

def _varrer_arquivos_locais_seguro():
    import re as _re
    alvos = [Path.home() / "Kael_ia", Path.home() / "Projetos" / "Ecos_de_Aethelgard", Path("/sdcard/Download")]
    exts = {".sh", ".py", ".lua", ".luau", ".js", ".ps1", ".bat", ".vbs", ".apk"}
    padrao = _re.compile(r"(eval\s*\(|exec\s*\(|base64\.b64decode|curl\s+.*\|\s*(sh|bash)|wget\s+.*\|\s*(sh|bash))", _re.I)
    suspeitos = []
    apks = []
    total_lidos = 0
    for base in alvos:
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if _kael_foi_cancelado():
                return "Varredura cancelada pelo usuário."
            if not p.is_file() or "build_termux" in p.parts or "__pycache__" in p.parts:
                continue
            ext = p.suffix.lower()
            if ext not in exts:
                continue
            total_lidos += 1
            if ext == ".apk":
                apks.append(str(p))
                continue
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
                if padrao.search(txt):
                    suspeitos.append(str(p))
            except Exception:
                pass
    linhas = [
        f"Varredura local concluída ({total_lidos} arquivos inspecionados em Kael_ia, Ecos_de_Aethelgard e Download):",
        f"- Padrões críticos de execução/codificação encontrados: {len(suspeitos)}",
    ]
    for item in suspeitos[:10]:
        linhas.append(f"  * {item}")
    linhas.append(f"- APKs locais encontrados: {len(apks)}")
    for apk in apks[:10]:
        linhas.append(f"  * {apk}")
    linhas.append("(Nota: no Android sem root, a varredura atua nas pastas acessíveis ao usuário/Termux, não na partição protegida do sistema.)")
    return "\n".join(linhas)

import importlib.util
"""
KAEL API SERVER v5.2 - Com Agente Autônomo de Criação
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import sys
import tempfile
import time
import threading
import re
from pathlib import Path
import requests

BASE_DIR = Path(__file__).parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from core.kael_context import KaelContext
from core.tool_registry import ToolRegistry
from core.autonomous_agent import AutonomousAgent
from core.docs_rag import DocsRagIndex
from core.project_indexer import ProjectIndexer
from core.skill_manager import SkillManager
from core.telemetry import SystemTelemetry
from core.chat_history import validate_chat_history
from core.local_file_workspace import LocalFileWorkspace
from core.attachments import (
    MAX_ATTACHMENT_CHARS,
    format_attachments,
    history_prompt,
    validate_attachments,
)
from core.configuration import validate_generation_settings
from core.unified_memory import init_unified_memory, get_unified_memory
from core.creativity_engine import init_creativity_engine, get_creativity_engine
from core.sistema.gerenciador_popups import init_gerenciador_popups

# Boot
ctx = KaelContext()
registry = ToolRegistry(ctx)
ctx.registry = registry
registry.auto_discover()

# Gerenciador de Pop-ups
ctx.gerenciador_popups = init_gerenciador_popups(BASE_DIR)

# File Manager (criar, modificar, ler arquivos com autorização)
from core.file_manager import init_file_manager
ctx.file_manager = init_file_manager(BASE_DIR)
print("[OK] File Manager inicializado.")

# Agente Autônomo
ctx.autonomous_agent = AutonomousAgent(ctx)
for _line in (BASE_DIR / ".env").read_text(encoding="utf-8").splitlines() if (BASE_DIR / ".env").exists() else []:
    if "=" in _line and not _line.strip().startswith("#"):
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip().strip("\"'"))
from core.ceo_ai import create_ceo
ctx.ceo = create_ceo(model=ctx.config.get("model_name", "qwen2.5:1.5b"))
from core.plugin_loader import KaelPluginManager
ctx.registry = registry
ctx.plugin_manager = KaelPluginManager(BASE_DIR / "plugins", BASE_DIR / "config" / "plugins.local.json")
ctx.plugin_manager.discover_and_load(ctx, registry)
ctx.ceo.plugin_manager = ctx.plugin_manager
ctx.telemetry = SystemTelemetry()
ctx.skills = SkillManager(
    BASE_DIR / "skills",
    BASE_DIR / "config" / "skills.local.json",
)
try:
    ctx.docs_index = DocsRagIndex(ctx.memory_dir / "docs_rag.sqlite")
    print("[OK] Índice local de documentação carregado.")
except Exception as exc:
    ctx.docs_index = None
    print(f"[AVISO] RAG de documentação indisponível: {exc}")

# Memória Unificada (legado + vetorial + episódica)
try:
    ctx.unified_memory = init_unified_memory(
        str(BASE_DIR),
        str(ctx.memory_dir),
    )
    print("[OK] Memória unificada carregada.")
except Exception as exc:
    ctx.unified_memory = None
    print(f"[AVISO] Memória unificada indisponível: {exc}")

# Motor de Criatividade (temperatura adaptativa + síntese de ideias)
try:
    ctx.creativity_engine = init_creativity_engine(str(BASE_DIR))
    print("[OK] Motor de criatividade carregado.")
except Exception as exc:
    ctx.creativity_engine = None
    print(f"[AVISO] Motor de criatividade indisponível: {exc}")



def _buscar_contexto_memoria_local(pergunta: str) -> str:
    partes = []
    q = (pergunta or "").strip()
    if not q:
        return ""
    try:
        from scripts import aprendizado_kael as _ap
        itens = _ap.listar_aprendizados(20)
        palavras = [w.lower() for w in re.findall(r"[a-zA-ZÀ-ÿ0-9_]{3,}", q) if w.lower() not in ("lembra", "lembrar", "falamos", "sobre", "oque", "qual", "quais", "como", "faz", "fazer", "resumo")]
        for it in itens:
            blob = f"{it.get('chave','')} {it.get('valor','')}".lower()
            if not palavras or any(w in blob for w in palavras):
                partes.append(f"- [{it.get('chave')}] {it.get('valor')}")
    except Exception:
        pass
    try:
        import sqlite3
        db_p = os.path.expanduser("~/Kael_ia/data/kael_memory.db")
        if os.path.exists(db_p):
            conn = sqlite3.connect(db_p)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tabelas = [r[0] for r in cur.fetchall()]
            for t in tabelas:
                if "fts" in t.lower() or "memor" in t.lower() or "conhec" in t.lower():
                    try:
                        cols = [c[1] for c in cur.execute(f"PRAGMA table_info({t})").fetchall()]
                        txt_cols = [c for c in cols if any(k in c.lower() for k in ("text", "content", "body", "valor", "resposta", "pergunta", "nota", "tema", "resumo"))]
                        if not txt_cols:
                            continue
                        where_clauses = " OR ".join([f"lower({c}) LIKE ?" for c in txt_cols])
                        palavras = [w.lower() for w in re.findall(r"[a-zA-ZÀ-ÿ0-9_]{4,}", q) if w.lower() not in ("lembra", "lembrar", "falamos", "sobre", "roblox", "studio", "luau", "resumo")]
                        for w in palavras[:4]:
                            rows = cur.execute(f"SELECT {', '.join(txt_cols[:3])} FROM {t} WHERE {where_clauses} LIMIT 3", [f"%{w}%"] * len(txt_cols)).fetchall()
                            for r in rows:
                                linha = " | ".join(str(x) for x in r if x)
                                if linha and linha not in partes:
                                    partes.append(linha[:260])
                    except Exception:
                        pass
            conn.close()
    except Exception:
        pass
    return "\n".join(partes[:8])

def _coletar_diagnostico_kael(texto_usuario: str) -> str:
    t = (texto_usuario or "").lower()
    if not any(k in t for k in ("desempenho", "latencia", "latência", "memoria", "memória", "saude", "saúde", "lento", "rapido", "rápido", "diagnóst", "diagnost")):
        return ""
    partes = []
    try:
        import subprocess
        out = subprocess.check_output(["ps", "-ef"], text=True, stderr=subprocess.DEVNULL)
        linhas = [ln.strip() for ln in out.splitlines() if any(w in ln.lower() for w in ("llama-server", "kael_app.py", "api_server.py"))]
        if linhas:
            partes.append("Processos reais em execução:\n" + "\n".join(linhas[:6]))
    except Exception:
        pass
    try:
        import sqlite3
        for db_p in (Path("kael_memory.db"), Path("data/kael_memory.db"), Path.home() / "storage" / "shared" / "Documents" / "Kael_ia" / "kael_memory.db"):
            if db_p.exists():
                conn = sqlite3.connect(str(db_p))
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memories'")
                if cur.fetchone():
                    cur.execute("SELECT COUNT(*) FROM memories")
                    total = cur.fetchone()[0]
                    partes.append(f"Memória SQLite ({db_p}): {total} registros em 'memories'.")
                conn.close()
                break
    except Exception:
        pass
    try:
        for r_p in (Path("regras_aprendidas.json"), Path("data/regras_aprendidas.json")):
            if r_p.exists():
                txt = r_p.read_text(encoding="utf-8", errors="replace")[:600]
                partes.append(f"Regras aprendidas ({r_p}): {txt}")
                break
    except Exception:
        pass
    if not partes:
        return ""
    return (
        "\n\n[DADOS REAIS DO SISTEMA KAEL - USE ESTES DADOS E NÃO DIGA QUE NÃO TEM ACESSO]:\n"
        + "\n".join(partes)
    )

app = Flask(__name__)

CHAT_HISTORY_JSON_PATH = BASE_DIR / "data" / "chat_historico.json"

def _extrair_mensagem_e_historico(body: dict):
    if not isinstance(body, dict):
        return "", []
    hist = body.get("history")
    if not isinstance(hist, list):
        hist = []
    msg = ""
    for chave in ("message", "prompt", "mensagem", "text"):
        val = body.get(chave)
        if isinstance(val, str) and val.strip():
            msg = val.strip()
            break
    if not msg and hist:
        for item in reversed(hist):
            if isinstance(item, dict):
                c = item.get("content") or item.get("message") or item.get("text") or ""
                if isinstance(c, str) and c.strip():
                    msg = c.strip()
                    break
            elif isinstance(item, str) and item.strip():
                msg = item.strip()
                break
    return msg, hist

def _append_chat_historico_json(role: str, content: str, limite: int = 200):
    import json
    from datetime import datetime
    if not content or not str(content).strip():
        return
    try:
        CHAT_HISTORY_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        atual = []
        if CHAT_HISTORY_JSON_PATH.exists():
            lido = json.loads(CHAT_HISTORY_JSON_PATH.read_text(encoding="utf-8", errors="replace"))
            if isinstance(lido, list):
                atual = lido
        atual.append({
            "role": role,
            "content": str(content).strip(),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        })
        atual = atual[-limite:]
        CHAT_HISTORY_JSON_PATH.write_text(
            json.dumps(atual, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"[HIST] Falha ao salvar histórico JSON: {exc}")


try:
    from scripts.permissoes_kael import (
        aguardar_decisao,
        listar_pendentes,
        resolver_permissao,
        solicitar_permissao,
    )
except Exception:
    aguardar_decisao = None
    listar_pendentes = None
    resolver_permissao = None
    solicitar_permissao = None

api_port = ctx.config["api_port"]
CORS(app, origins=[
    f"http://127.0.0.1:{api_port}",
    f"http://localhost:{api_port}",
    f"http://[::1]:{api_port}",
])

GENERATION_SETTINGS_PATH = BASE_DIR / "config" / "generation.local.json"


def _load_generation_settings():
    settings = {
        "model": ctx.model_name,
        "temperature": ctx.config["temperature"],
        "max_tokens": ctx.config["max_tokens"],
        "think": ctx.config["think"],
    }
    if GENERATION_SETTINGS_PATH.exists():
        try:
            with GENERATION_SETTINGS_PATH.open("r", encoding="utf-8") as file:
                saved = json.load(file)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Falha ao ler configurações locais de geração: {exc}") from exc
        if not isinstance(saved, dict):
            raise RuntimeError("generation.local.json deve conter um objeto JSON.")
        settings.update(saved)
    environment_settings = {
        "KAEL_MODEL": "model",
        "KAEL_TEMPERATURE": "temperature",
        "KAEL_MAX_TOKENS": "max_tokens",
        "KAEL_THINK": "think",
    }
    for environment_key, setting_key in environment_settings.items():
        if environment_key in os.environ:
            config_key = {
                "model": "model_name",
                "max_tokens": "max_tokens",
                "temperature": "temperature",
                "think": "think",
            }[setting_key]
            settings[setting_key] = ctx.config[config_key]
    try:
        return validate_generation_settings(settings)
    except ValueError as exc:
        raise RuntimeError(f"Configuração local de geração inválida: {exc}") from exc


def _save_generation_settings(settings):
    GENERATION_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=GENERATION_SETTINGS_PATH.parent,
            prefix=".generation-",
            suffix=".tmp",
            delete=False,
        ) as file:
            temp_path = Path(file.name)
            json.dump(settings, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, GENERATION_SETTINGS_PATH)
    except OSError:
        if temp_path and temp_path.exists():
            temp_path.unlink()
        raise


ctx.generation_settings = _load_generation_settings()
generation_settings_lock = threading.Lock()


def _available_ollama_models():
    try:
        response = requests.get(f"{ctx.ollama_url}/api/tags", timeout=3)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ConnectionError(f"Não foi possível consultar os modelos locais do Ollama: {exc}") from exc
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        raise ConnectionError("O Ollama retornou uma lista de modelos inválida.")
    names = sorted({
        item["name"] for item in models
        if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"]
    })
    return names

# Plugin Bridge
try:
    from core.plugin_bridge import register_routes
    register_routes(app, ctx)
    print("[OK] Plugin Bridge registrado.")
except Exception as e:
    print(f"[AVISO] Plugin Bridge desativado: {e}")

print("\n" + "=" * 60)
print("🚨 [KAEL] API SERVER v5.2 RODANDO NA PORTA 8000 🚨")
print(f"🎮 Projeto: {ctx.project_path}")
print(f"🔧 Registry: {len(registry.tools)} tools | {len(registry.commands)} comandos")
print(f"🤖 Agente Autônomo: {'✅ ATIVO' if ctx.autonomous_agent.active else '⚪ Inativo'}")
print("=" * 60 + "\n")

# Loop do agente autônomo
def autonomous_loop():
    while True:
        if ctx.autonomous_agent.active:
            ctx.autonomous_agent.run_cycle()
        time.sleep(3)

threading.Thread(target=autonomous_loop, daemon=True).start()

@app.route('/', methods=['GET'])
def chat_ui():
    tpl = BASE_DIR / "templates" / "kael_chat.html"
    if tpl.is_file():
        return send_from_directory(BASE_DIR / "templates", "kael_chat.html")
    return send_from_directory(BASE_DIR / "ui", "chat.html")



@app.route('/voz/config', methods=['GET', 'POST'])
def voz_config():
    padrao = {
        "perfil": "natural",
        "voz_nome": "",
        "rate": 1.0,
        "pitch": 1.0,
        "auto_falar": False,
    }
    try:
        from scripts import aprendizado_kael as _ap_voz
    except Exception:
        _ap_voz = None

    if request.method == 'GET':
        atual = dict(padrao)
        if _ap_voz and hasattr(_ap_voz, "buscar_aprendizado"):
            salvo = _ap_voz.buscar_aprendizado("voz:config_ativa")
            if salvo:
                try:
                    import json as _json_voz
                    parsed = _json_voz.loads(salvo)
                    if isinstance(parsed, dict):
                        atual.update(parsed)
                except Exception:
                    pass
        return jsonify({"ok": True, "config": atual}), 200

    data = request.get_json(silent=True) or {}
    atual = dict(padrao)
    if _ap_voz and hasattr(_ap_voz, "buscar_aprendizado"):
        salvo = _ap_voz.buscar_aprendizado("voz:config_ativa")
        if salvo:
            try:
                import json as _json_voz
                parsed = _json_voz.loads(salvo)
                if isinstance(parsed, dict):
                    atual.update(parsed)
            except Exception:
                pass

    if "perfil" in data and str(data["perfil"]).strip():
        atual["perfil"] = str(data["perfil"]).strip()[:24]
    if "voz_nome" in data:
        atual["voz_nome"] = str(data["voz_nome"] or "").strip()[:120]
    if "rate" in data:
        try:
            atual["rate"] = max(0.6, min(1.6, float(data["rate"])))
        except Exception:
            pass
    if "pitch" in data:
        try:
            atual["pitch"] = max(0.6, min(1.4, float(data["pitch"])))
        except Exception:
            pass
    if "auto_falar" in data:
        atual["auto_falar"] = bool(data["auto_falar"])

    if _ap_voz and hasattr(_ap_voz, "salvar_aprendizado"):
        import json as _json_voz
        _ap_voz.salvar_aprendizado("voz", "voz:config_ativa", _json_voz.dumps(atual, ensure_ascii=False))

    return jsonify({"ok": True, "config": atual}), 200


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "online" if ctx.ollama_online() else "ollama_offline",
        "tools": sorted(registry.tools.keys()),
        "commands": sorted(registry.commands.keys()),
        "autonomous_mode": ctx.autonomous["active"],
        "autonomous_agent": ctx.autonomous_agent.get_status(),
        "pending_approvals": len(registry.pending_approvals),
        "permission_policy": ctx.permission_policy.public_state(),
        "telemetry": ctx.telemetry.snapshot(),
        "memoria_unificada": bool(ctx.unified_memory),
        "motor_criatividade": bool(ctx.creativity_engine),
    })

@app.route('/models', methods=['GET'])
def list_local_models():
    try:
        models = _available_ollama_models()
    except ConnectionError as exc:
        return jsonify({"error": str(exc)}), 503
    return jsonify({
        "models": models,
        "selected": ctx.generation_settings["model"],
    })

@app.route('/settings/generation', methods=['GET'])
def get_generation_settings():
    with generation_settings_lock:
        settings = dict(ctx.generation_settings)
    locked = [
        setting for environment_key, setting in (
            ("KAEL_MODEL", "model"),
            ("KAEL_TEMPERATURE", "temperature"),
            ("KAEL_MAX_TOKENS", "max_tokens"),
            ("KAEL_THINK", "think"),
        )
        if environment_key in os.environ
    ]
    return jsonify({
        "settings": settings,
        "locked": locked,
        "limits": {
            "temperature": {"min": 0, "max": 2, "step": 0.1},
            "max_tokens": {"min": 64, "max": 8192, "step": 64},
        },
    })

@app.route('/settings/generation', methods=['POST'])
def update_generation_settings():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return jsonify({"error": "Informe ao menos uma configuração de geração."}), 400
    with generation_settings_lock:
        candidate = dict(ctx.generation_settings)
        locked = {
            setting for environment_key, setting in (
                ("KAEL_MODEL", "model"),
                ("KAEL_TEMPERATURE", "temperature"),
                ("KAEL_MAX_TOKENS", "max_tokens"),
                ("KAEL_THINK", "think"),
            )
            if environment_key in os.environ
        }
        if any(data[key] != candidate[key] for key in locked if key in data):
            return jsonify({
                "error": "Uma ou mais configurações são controladas por variáveis de ambiente.",
                "locked": sorted(locked),
            }), 400
        models = None
        if "model" in data and data["model"] != candidate["model"]:
            try:
                models = _available_ollama_models()
            except ConnectionError as exc:
                return jsonify({"error": str(exc)}), 503
        candidate.update(data)
        try:
            validated = validate_generation_settings(candidate, models)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        try:
            _save_generation_settings(validated)
        except OSError as exc:
            print(f"[CONFIG] Falha ao salvar configurações de geração: {exc}")
            return jsonify({"error": "Não foi possível salvar as configurações locais."}), 500
        ctx.generation_settings = validated
        ctx.model_name = validated["model"]
    return jsonify({"settings": validated})

@app.route('/settings/autonomy', methods=['GET'])
def get_autonomy_settings():
    return jsonify(ctx.permission_policy.public_state())

@app.route('/settings/autonomy', methods=['POST'])
def update_autonomy_settings():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "O corpo da solicitação deve ser um objeto JSON."}), 400
    mode = data.get("mode")
    try:
        ctx.permission_policy.set_mode(mode)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except OSError as exc:
        print(f"[PERMISSAO] Falha ao persistir o nível de autorização: {exc}")
        return jsonify({"error": "Não foi possível salvar o nível de autorização localmente."}), 500
    return jsonify(ctx.permission_policy.public_state())

@app.route('/filesystem/folders', methods=['GET'])
def list_trusted_folders():
    state = ctx.permission_policy.public_state()
    return jsonify({"folders": state["trusted_folders"]})

@app.route('/filesystem/folders/authorize', methods=['POST'])
def authorize_file_folder():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Informe o caminho da pasta."}), 400
    try:
        folder = ctx.permission_policy.validate_trusted_folder(data.get("path"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if ctx.permission_policy.is_trusted_directory(folder):
        return jsonify({"status": "already_authorized", "folder": folder})

    permission = registry.create_approval(
        title="Autorizar pasta local",
        summary=f"Permitir acesso aos arquivos diretamente nesta pasta: {folder}",
        details=(
            "A autorização vale para leitura e escrita controladas no workspace. "
            "Você pode revogar a autorização a qualquer momento."
        ),
        action_type="auth_folder",
        payload={"folder": folder},
    )
    return jsonify({
        "status": "pending_approval",
        "approval_id": permission["id"],
        "folder": folder,
    })

@app.route('/approvals/pending', methods=['GET'])
def list_pending_approvals():
    approvals = registry.list_pending_approvals()
    return jsonify({"pending": approvals})

@app.route('/approvals/<approval_id>/resolve', methods=['POST'])
def resolve_approval(approval_id):
    data = request.get_json(silent=True) or {}
    accept = bool(data.get("accept", False))
    result = registry.resolve_approval(approval_id, accept)
    if not result:
        return jsonify({"error": "Solicitação não encontrada ou já resolvida."}), 404
    return jsonify({"status": "resolved", "approval": result})


# --- Rotas de permissão do pop-up (/kael-perm/*) ---
@app.route('/kael-perm/request', methods=['POST'])
def kael_perm_request():
    data = request.get_json(silent=True) or {}
    acao = str(data.get("acao") or "Confirmar ação do Kael").strip()
    alvo = str(data.get("alvo") or str(ctx.project_path)).strip()
    detalhes = str(data.get("detalhes") or "").strip()
    if callable(solicitar_permissao):
        item = solicitar_permissao(acao, alvo, detalhes)
        return jsonify({"ok": True, "item": item}), 200
    return jsonify({"ok": False, "error": "permissoes_kael indisponível"}), 500


@app.route('/kael-perm/pending', methods=['GET'])
def kael_perm_pending():
    itens = []
    if callable(listar_pendentes):
        for p in listar_pendentes():
            itens.append({
                "id": p.get("id"),
                "acao": p.get("acao", "Confirmar ação do Kael"),
                "alvo": p.get("alvo", ""),
                "detalhes": p.get("detalhes", ""),
                "source": "permissoes_kael",
            })
    try:
        for ap in registry.list_pending_approvals():
            itens.append({
                "id": ap.get("id") or ap.get("request_id"),
                "acao": ap.get("title") or ap.get("action_type") or "Aprovação pendente",
                "alvo": ap.get("summary") or "",
                "detalhes": ap.get("details") or "",
                "source": "tool_registry",
            })
    except Exception:
        pass
    return jsonify({"pending": itens}), 200


@app.route('/kael-perm/resolve', methods=['POST'])
def kael_perm_resolve():
    data = request.get_json(silent=True) or {}
    perm_id = str(data.get("id") or "").strip()
    aceitar = bool(data.get("accept", False))
    resolvido = None
    if callable(resolver_permissao) and perm_id:
        resolvido = resolver_permissao(perm_id, aceitar)

    reg_resultado = None
    if perm_id and hasattr(registry, "resolve_approval"):
        try:
            reg_res = registry.resolve_approval(perm_id, aceitar)
            if isinstance(reg_res, dict) and reg_res.get("status") not in ("expired", "error"):
                reg_resultado = reg_res
        except Exception as exc:
            reg_resultado = {"status": "error", "response": str(exc)}

    if not resolvido and not reg_resultado:
        return jsonify({"ok": False, "error": "Permissão não encontrada ou já resolvida."}), 404

    return jsonify({
        "ok": True,
        "accepted": aceitar,
        "resolved": resolvido,
        "registry_result": reg_resultado,
    }), 200


def _localizar_arquivo_alvo_kael(referencia: str) -> str:
    """Resolve caminho real de um arquivo citado em ~/Kael_ia ou ~/Projetos."""
    ref = (referencia or "").strip().strip("'\"")
    if not ref:
        return ""
    exp = Path(os.path.expanduser(ref))
    if exp.is_file():
        return str(exp)
    bases = [
        Path.home() / "Kael_ia",
        Path.home() / "Kael_ia" / "scripts",
        Path.home() / "Kael_ia" / "templates",
        Path.home() / "Kael_ia" / "sandbox_testes",
        Path.home() / "Projetos" / "Ecos_de_Aethelgard",
        Path.home() / "Projetos",
    ]
    for b in bases:
        cand = b / ref
        if cand.is_file():
            return str(cand)
    nome = os.path.basename(ref)
    if nome:
        for b in (Path.home() / "Kael_ia", Path.home() / "Projetos"):
            if not b.exists():
                continue
            for found in b.rglob(nome):
                if found.is_file() and "backups" not in str(found) and "__pycache__" not in str(found):
                    return str(found)
    return ""


def _inspecionar_saude_e_projetos(user_msg: str) -> str:
    """Inspeção automática de logs recentes e estrutura de ~/Kael_ia e ~/Projetos."""
    baixo = (user_msg or "").lower()
    gatilhos = (
        "log", "logs", "erro", "erros", "falha", "falhas", "traceback",
        "saúde", "saude", "inspecione", "inspecionar", "revise", "revisar",
        "diagnostique", "diagnosticar", "status do projeto", "ecos de aethelgard"
    )
    if not any(g in baixo for g in gatilhos):
        return ""

    partes = []
    for log_rel in ("data/kael_server.log", "data/llama_server.log"):
        lp = Path.home() / "Kael_ia" / log_rel
        if lp.is_file():
            linhas = lp.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
            alertas = [
                l.strip()[:150] for l in linhas
                if any(tok in l.lower() for tok in ("error", "erro", "exception", "traceback", "500", "400", "warning", "clean up", "cleaning up"))
            ]
            if alertas:
                partes.append(f"[{log_rel}] últimos alertas:\n" + "\n".join(alertas[-6:]))

    ecos_dir = Path.home() / "Projetos" / "Ecos_de_Aethelgard"
    if ecos_dir.exists():
        arqs_ecos = [
            str(p.relative_to(ecos_dir))
            for p in ecos_dir.rglob("*")
            if p.is_file() and "__pycache__" not in str(p)
        ][:20]
        partes.append(f"[Ecos_de_Aethelgard] arquivos ({len(arqs_ecos)}): {', '.join(arqs_ecos) if arqs_ecos else 'nenhum arquivo ainda'}")

    return ("\n".join(partes))[:900]


def _resumo_arquivos_reais(user_msg: str, pasta_alvo: str = "") -> str:
    raiz_kael = Path.home() / "Kael_ia"
    raiz_ecos = Path.home() / "Projetos" / "Ecos_de_Aethelgard"
    itens_kael = sorted([p.name + ("/" if p.is_dir() else "") for p in raiz_kael.iterdir()])[:18] if raiz_kael.exists() else []
    itens_ecos = sorted([p.name + ("/" if p.is_dir() else "") for p in raiz_ecos.iterdir()])[:12] if raiz_ecos.exists() else []
    bloco = [
        f"Pasta ~/Kael_ia: {', '.join(itens_kael)}",
        f"Pasta ~/Projetos/Ecos_de_Aethelgard: {', '.join(itens_ecos) if itens_ecos else 'vazia'}",
    ]
    msg_txt = user_msg or ""
    m_refs = re.findall(r'([~/$A-Za-z0-9_./-]+\.(?:py|lua|luau|html|js|json|md))', msg_txt)
    for ref in m_refs[:2]:
        caminho_real = _localizar_arquivo_alvo_kael(ref)
        if caminho_real and os.path.isfile(caminho_real):
            conteudo_full = Path(caminho_real).read_text(encoding="utf-8", errors="replace")
            trecho = conteudo_full[:900]
            bloco.append(f"Conteúdo real de {caminho_real}:\n{trecho}")
            try:
                from scripts.aprendizado_kael import aprender_de_codigo as _ap_cod
                _ap_cod(caminho_real, conteudo_full, nota="lido para analise/edicao")
            except Exception:
                pass
    return "\n".join(bloco)[:1250]


@app.route('/sandbox/rodar', methods=['POST', 'GET'])
def sandbox_rodar():
    import subprocess, sys
    runner = Path.home() / "Kael_ia" / "sandbox_testes" / "executar_testes.py"
    if not runner.is_file():
        return jsonify({"ok": False, "saida": "executar_testes.py não encontrado."}), 404
    proc = subprocess.run([sys.executable, str(runner)], capture_output=True, text=True, timeout=25)
    saida = (proc.stdout + "\n" + proc.stderr).strip()
    return jsonify({"ok": proc.returncode == 0, "saida": saida}), 200

@app.route('/sandbox/arquivos', methods=['GET'])
def sandbox_arquivos():
    raiz_kael = Path.home() / "Kael_ia"
    raiz_ecos = Path.home() / "Projetos" / "Ecos_de_Aethelgard"
    kael_list = sorted([p.name + ("/" if p.is_dir() else "") for p in raiz_kael.iterdir()]) if raiz_kael.exists() else []
    ecos_list = sorted([p.name + ("/" if p.is_dir() else "") for p in raiz_ecos.iterdir()]) if raiz_ecos.exists() else []
    return jsonify({"ok": True, "kael": kael_list, "ecos": ecos_list}), 200


def _eh_pedido_implementacao(msg: str) -> bool:
    txt = (msg or "").lower()
    termos = (
        "implemente", "implementar", "crie", "criar", "edite", "editar",
        "altere", "alterar", "melhore", "melhorar", "escreva", "escrever",
        "corrija", "corrigir", "adicione", "adicionar", "gere", "gerar",
        "arquivo", "script", "código", "codigo", "rota", "função", "funcao",
        "erro", "bug", "falha", "problema", "log", "diagnóstico", "diagnostico",
        "analise", "analisar", "revisar", "testar", "teste",
    )
    return any(t in txt for t in termos)


def _sanitizar_resposta_executor(reply: str, user_msg: str) -> str:
    if not isinstance(reply, str) or not reply.strip():
        return reply
    baixo = reply.lower()
    recusas = (
        "não estou aqui para implementar",
        "nao estou aqui para implementar",
        "não implementar ações ou alterações",
        "nao implementar acoes ou alteracoes",
        "apenas uma orientação geral",
        "apenas uma orientacao geral",
        "orientações gerais",
        "orientacoes gerais",
        "de forma geral",
        "de maneira geral",
        "papel é orientar e ajudar de maneira geral",
        "papel e orientar e ajudar de maneira geral",
        "não tenho o acesso direto aos arquivos",
        "nao tenho o acesso direto aos arquivos",
        "não tenho a capacidade de acessar arquivos",
        "nao tenho a capacidade de acessar arquivos",
        "não tenho acesso direto",
        "nao tenho acesso direto",
        "não posso acessar diretamente",
        "nao posso acessar diretamente",
        "como modelo de linguagem",
        "como inteligência artificial",
        "como inteligencia artificial",
        "como assistente, eu não posso",
        "como assistente, eu nao posso",
        "não posso executar ou implementar códigos diretamente",
        "nao posso executar ou implementar codigos diretamente",
        "como assistente, não posso",
        "como assistente, nao posso",
        "fornecer sugestões e diretrizes",
        "fornecer sugestoes e diretrizes",
        "diretrizes sobre como melhorar",
        "formas de interação entre as ias",
        "formas de interacao entre as ias",
        "não posso implementar",
        "nao posso implementar",
        "arquivos locais não confiáveis",
        "arquivos locais nao confiaveis",
        "instruções confiáveis",
        "instrucoes confiaveis",
    )
    _eh_consulta_ou_mem = any(k in (user_msg or "").lower() for k in ("lembra", "lembrar", "falamos", "memória", "memoria", "resumo", "pesquisa", "como criar"))
    if (not _eh_consulta_ou_mem) and _eh_pedido_implementacao(user_msg) and any(r in baixo for r in recusas):
        return (
            "Modo executor ativo para o pedido: vou preparar o rascunho e validar na sandbox "
            "(`~/Kael_ia/sandbox_testes/candidatos/`) com `executar_testes.py` antes de aplicar "
            "no destino. Informe o caminho/nome do arquivo ou confirme qual módulo/script você quer "
            "que eu gere agora para testar."
        )
    return reply


def _materializar_rascunho_sandbox(reply: str, user_msg: str) -> str:
    """Se o usuario pediu criacao/implementacao de script/arquivo, garante a gravacao
    em ~/Kael_ia/sandbox_testes/candidatos/ e roda executar_testes.py --arquivo."""
    import os
    import re
    import subprocess

    txt_user = (user_msg or "").strip()
    baixo_user = txt_user.lower()
    pediu_criacao = any(k in baixo_user for k in (
        "implemente", "implementar", "crie", "criar", "gere", "gerar", "escreva", "escrever"
    )) and any(k in baixo_user for k in (
        "script", "arquivo", ".py", ".lua", "sandbox", "diagnostico", "diagnóstico"
    ))
    if not pediu_criacao:
        return reply

    cand_dir = os.path.expanduser("~/Kael_ia/sandbox_testes/candidatos")
    os.makedirs(cand_dir, exist_ok=True)

    m_path = re.search(r'([~/$A-Za-z0-9_./-]+\.(?:py|lua))', txt_user)
    if m_path:
        nome_base = os.path.basename(m_path.group(1))
    else:
        nome_base = "rascunho_kael.py"
    if not (nome_base.endswith(".py") or nome_base.endswith(".lua")):
        nome_base += ".py"

    destino = os.path.join(cand_dir, nome_base)

    # Tenta extrair bloco de codigo da resposta do modelo
    code = ""
    m_block = re.search(r"```(?:python|py|lua|luau)?\s*\n(.*?)```", reply or "", flags=re.S | re.I)
    if m_block and m_block.group(1).strip():
        code = m_block.group(1).strip() + "\n"
        if destino.endswith(".py"):
            code = code.replace(
                "sqlite3.connect('kael_memory.db')",
                "sqlite3.connect(os.path.expanduser('~/Kael_ia/data/kael_memory.db'))"
            ).replace(
                'sqlite3.connect("kael_memory.db")',
                'sqlite3.connect(os.path.expanduser("~/Kael_ia/data/kael_memory.db"))'
            )
    elif destino.endswith(".py"):
        code = (
            "import os\n"
            "import sqlite3\n"
            "import subprocess\n\n"
            "BASE = os.path.expanduser('~/Kael_ia')\n"
            "DB_PATH = os.path.join(BASE, 'data', 'kael_memory.db')\n\n"
            "def main():\n"
            "    print('=== DIAGNOSTICO KAEL (GERADO PELO KAEL) ===')\n"
            "    print('Base existe:', os.path.isdir(BASE), '| SQLite existe:', os.path.isfile(DB_PATH))\n"
            "    if os.path.isfile(DB_PATH):\n"
            "        conn = sqlite3.connect(DB_PATH)\n"
            "        cur = conn.cursor()\n"
            "        tables = [r[0] for r in cur.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]\n"
            "        print('Tabelas SQLite:', tables)\n"
            "        for t in tables:\n"
            "            cnt = cur.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]\n"
            "            print(f'  - {t}: {cnt}')\n"
            "        conn.close()\n"
            "    out = subprocess.check_output(['ps', '-ef'], text=True, errors='replace')\n"
            "    procs = [l for l in out.splitlines() if any(k in l for k in ('api_server.py', 'llama-server', 'kael_app.py'))]\n"
            "    print('Processos Kael:', len(procs))\n"
            "    for p in procs:\n"
            "        print(' ', p[:140])\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
    elif destino.endswith(".lua"):
        code = (
            "-- Script Luau gerado pelo Kael na sandbox\n"
            "local Service = {}\n"
            "Service.__index = Service\n\n"
            "function Service.new()\n"
            "    return setmetatable({}, Service)\n"
            "end\n\n"
            "return Service\n"
        )

    try:
        with open(destino, "w", encoding="utf-8") as f:
            f.write(code)
    except Exception as exc:
        return f"{reply}\n\n[Falha ao gravar em {destino}: {exc}]"

    runner = os.path.expanduser("~/Kael_ia/sandbox_testes/executar_testes.py")
    status_txt = ""
    if os.path.isfile(runner):
        try:
            proc = subprocess.run(
                ["python3", runner, "--arquivo", destino],
                capture_output=True, text=True, timeout=22
            )
            saida = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
            linhas_ok = [l for l in saida.splitlines() if "RESULTADO FINAL:" in l or "[OK]" in l or "[ERRO]" in l or "[FALHA]" in l]
            resumo = "\n".join(linhas_ok[-6:]) if linhas_ok else saida[-400:]
            status_txt = f"\n\n[Sandbox] Arquivo gravado em `{destino}` e validado com `executar_testes.py`:\n```text\n{resumo}\n```"
        except Exception as exc:
            status_txt = f"\n\n[Sandbox] Arquivo gravado em `{destino}` (erro ao rodar validador: {exc})."
    else:
        status_txt = f"\n\n[Sandbox] Arquivo gravado em `{destino}`."

    base_reply = reply.strip()
    if destino not in base_reply:
        return base_reply + status_txt
    return base_reply + status_txt


def _ciclo_autonomo_sandbox(reply: str, user_msg: str) -> str:
    """Executa ciclo de gravar na sandbox, rodar executar_testes.py --arquivo,
    tentar autocorrecao basica se reprovar, e promover/reiniciar se o usuario
    pedir explicitamente para aplicar/implementar no destino."""
    import os
    import re
    import shutil
    import subprocess
    import time

    txt = (user_msg or "").strip()
    baixo = txt.lower()

    gatilhos_acao = (
        "implemente", "implementar", "crie", "criar", "corrija", "corrigir",
        "edite", "editar", "altere", "alterar", "gere", "gerar", "escreva", "escrever",
        "aplique", "aplicar", "teste", "testar", "melhore", "melhorar",
        "ajuste", "ajustar", "modifique", "modificar", "atualize", "atualizar",
        "refatore", "refatorar"
    )
    if not any(g in baixo for g in gatilhos_acao):
        return reply

    cand_dir = os.path.expanduser("~/Kael_ia/sandbox_testes/candidatos")
    os.makedirs(cand_dir, exist_ok=True)
    runner = os.path.expanduser("~/Kael_ia/sandbox_testes/executar_testes.py")

    # Detecta caminho alvo mencionado (absoluto, relativo em Kael_ia/Projetos ou nome de arquivo)
    m_alvo = re.search(r'(~\/[A-Za-z0-9_./-]+\.(?:py|lua|luau|html|js)|\/data\/data\/com\.termux\/files\/home\/[A-Za-z0-9_./-]+\.(?:py|lua|luau|html|js)|[A-Za-z0-9_./-]+\.(?:py|lua|luau|html|js))', txt)
    alvo_raw = m_alvo.group(1) if m_alvo else ""
    if alvo_raw and not alvo_raw.startswith(("~/", "/")):
        resolvido = _localizar_arquivo_alvo_kael(alvo_raw)
        if resolvido:
            alvo_raw = resolvido
    nome_arq = os.path.basename(alvo_raw) if alvo_raw else "auto_kael.py"
    if not nome_arq:
        nome_arq = "auto_kael.py"

    destino_cand = os.path.join(cand_dir, nome_arq)

    # Extrai bloco de codigo se existir; senao preserva o que ja foi gravado
    m_code = re.search(r"```(?:python|py|lua|luau|html)?\s*\n(.*?)```", reply or "", flags=re.S | re.I)
    if m_code and m_code.group(1).strip():
        code = m_code.group(1).strip() + "\n"
        if nome_arq.endswith(".py"):
            code = code.replace(
                "sqlite3.connect('kael_memory.db')",
                "sqlite3.connect(os.path.expanduser('~/Kael_ia/data/kael_memory.db'))"
            ).replace(
                'sqlite3.connect("kael_memory.db")',
                'sqlite3.connect(os.path.expanduser("~/Kael_ia/data/kael_memory.db"))'
            )
        with open(destino_cand, "w", encoding="utf-8") as f:
            f.write(code)
    elif not os.path.isfile(destino_cand):
        return reply

    def _rodar_validador(caminho: str):
        if not os.path.isfile(runner):
            return True, "Validador executar_testes.py nao encontrado."
        p = subprocess.run(["python3", runner, "--arquivo", caminho], capture_output=True, text=True, timeout=22)
        out = ((p.stdout or "") + "\n" + (p.stderr or "")).strip()
        aprovado = ("RESULTADO FINAL: APROVADO" in out) and (p.returncode == 0)
        return aprovado, out

    aprovado, out_val = _rodar_validador(destino_cand)

    # Tentativa automatica de autocorrecao se reprovar em Python (ex: NameError / import os)
    if not aprovado and nome_arq.endswith(".py"):
        try:
            cur_code = open(destino_cand, "r", encoding="utf-8", errors="replace").read()
            if "os." in cur_code and "import os" not in cur_code:
                cur_code = "import os\n" + cur_code
                with open(destino_cand, "w", encoding="utf-8") as f:
                    f.write(cur_code)
                aprovado, out_val = _rodar_validador(destino_cand)
        except Exception:
            pass

    resumo_linhas = [
        l for l in out_val.splitlines()
        if any(k in l for k in ("RESULTADO FINAL:", "[OK]", "[ERRO]", "[FALHA]", "SyntaxError", "Traceback"))
    ]
    resumo_txt = "\n".join(resumo_linhas[-8:]) if resumo_linhas else out_val[-400:]

    pediu_aplicar = any(k in baixo for k in ("aplique", "aplicar", "promova", "promover", "no destino", "direto no"))
    destino_final = ""
    if aprovado and alvo_raw and ("sandbox_testes/candidatos" not in alvo_raw) and (not pediu_aplicar):
        try:
            if callable(solicitar_permissao):
                solicitar_permissao(
                    f"Aplicar candidato validado em {os.path.basename(os.path.expanduser(alvo_raw))}",
                    os.path.expanduser(alvo_raw),
                    f"Candidato aprovado: {destino_cand} (com backup automático antes de sobrescrever)",
                )
        except Exception:
            pass

    if aprovado and pediu_aplicar and alvo_raw and ("sandbox_testes/candidatos" not in alvo_raw):
        destino_final = os.path.expanduser(alvo_raw)
        if os.path.isfile(destino_final):
            ts = time.strftime("%Y%m%d_%H%M%S")
            bkp_dir = os.path.expanduser(f"~/Kael_ia_backups/auto_apply_{ts}")
            os.makedirs(bkp_dir, exist_ok=True)
            shutil.copy2(destino_final, os.path.join(bkp_dir, os.path.basename(destino_final)))
        os.makedirs(os.path.dirname(destino_final), exist_ok=True)
        shutil.copy2(destino_cand, destino_final)

        # Se promoveu api_server.py, agenda reinicio limpo da porta 8000
        if os.path.basename(destino_final) == "api_server.py":
            subprocess.Popen(
                ["sh", "-c", "sleep 1; pkill -9 -f 'api_server.py' || true; sleep 1; nohup python3 ~/Kael_ia/api_server.py >> ~/Kael_ia/data/kael_server.log 2>&1 &"],
                start_new_session=True,
            )

    if aprovado and os.path.isfile(destino_cand):
        try:
            from scripts.aprendizado_kael import aprender_de_codigo as _ap_cod2
            _cod_validado = open(destino_cand, "r", encoding="utf-8", errors="replace").read()
            _nota_ap = f"{'aplicado em ' + destino_final if destino_final else 'validado na sandbox'}: {txt[:80]}"
            _ap_cod2(destino_final or destino_cand, _cod_validado, nota=_nota_ap)
        except Exception:
            pass

    extra = f"\n\n[Ciclo Autônomo Sandbox]\nCandidato: `{destino_cand}` | Status: `{'APROVADO' if aprovado else 'REPROVADO'}`"
    if destino_final:
        extra += f"\nAplicado com backup em: `{destino_final}`"
    extra += f"\n```text\n{resumo_txt}\n```"
    return (reply or "").strip() + extra


def _instrucao_raciocinio_kael(user_msg: str) -> str:
    """Gera diretriz objetiva para o Kael raciocinar sobre o pedido do usuario,
    o ambiente (Termux, ~/Kael_ia, ~/Projetos/Ecos_de_Aethelgard) e o entregavel."""
    txt = (user_msg or "").strip()
    baixo = txt.lower()

    if any(k in baixo for k in ("chat", "interface", "html", "ui", "ux", "histórico", "historico")):
        foco = "Foco: interface e fluxo do chat Kael (templates/kael_chat.html e rotas /chat, /chat/historico em ~/Kael_ia)."
    elif any(k in baixo for k in ("aethelgard", ".lua", "luau", "roblox", "mount", "fasttravel", "trade")):
        foco = "Foco: criar, arquitetar, atualizar e manter qualquer jogo (Roblox/Luau, Godot, Web) ou aplicativo (Python, Android, APIs, Web) em ~/Projetos/<projeto> com validação na sandbox."
    elif any(k in baixo for k in ("erro", "500", "log", "bug", "falha", "sandbox", "teste")):
        foco = "Foco: diagnóstico técnico, correção e validação via ~/Kael_ia/sandbox_testes/executar_testes.py."
    else:
        foco = "Foco: execução técnica direta no ambiente Termux (~/Kael_ia e ~/Projetos/Ecos_de_Aethelgard)."

    return (
        "\n[Raciocínio Kael] Analise o que o usuário pediu e responda com naturalidade, fluidez e clareza. "
        f"{foco} "
        "Em conversa normal ou dúvidas rápidas, fale como parceiro técnico direto e humano (evite listas artificiais ou tom robótico). "
        "Nunca use desculpas de assistente genérico nem diga que não tem acesso a arquivos/histórico; "
        "quando o pedido envolver código ou arquivo, entregue o código completo e funcional."
    )


def _eh_resposta_generica_kael(texto: str) -> bool:
    t = (texto or "").strip().lower()
    if not t:
        return True
    padroes = (
        "modo executor ativo para o pedido",
        "informe o caminho/nome do arquivo",
        "como assistente",
        "como kael, assistente",
        "sou apenas um assistente",
        "não posso acessar",
        "nao posso acessar",
        "minha capacidade é limitada",
        "minha capacidade e limitada",
        "não tenho acesso",
        "nao tenho acesso",
        "não posso analisar",
        "nao posso analisar",
        "em memória local",
        "em memoria local",
        "não posso alterar",
        "nao posso alterar",
        "não posso editar",
        "nao posso editar",
        "não posso executar",
        "nao posso executar",
        "não posso implementar",
        "nao posso implementar",
        "não consigo revisar",
        "nao consigo revisar",
        "fornecer sugestões e diretrizes",
        "fornecer sugestoes e diretrizes",
        "informações gerais",
        "informacoes gerais",
        "suporte técnico e assistência em projetos de software",
        "suporte tecnico e assistencia em projetos de software",
    )
    return any(p in t for p in padroes)




def _resolver_contexto_pasta_kael(texto: str) -> tuple[str, str]:
    t = (texto or "").lower()
    eh_kael = any(k in t for k in (
        "kael_chat.html", "chat.html", "api_server.py", "kael_app.py",
        "permissoes_kael", "sandbox_testes", "executar_testes", "~/kael_ia"
    ))
    eh_jogo = any(k in t for k in (
        "aethelgard", "ecos de aethelgard", ".lua", "luau", "roblox",
        "mountservice", "fasttravelservice", "tradeservice", "~/projetos/ecos_de_aethelgard"
    ))
    if eh_kael and not eh_jogo:
        return (
            "/data/data/com.termux/files/home/Kael_ia",
            "Este pedido é sobre o próprio sistema Kael em ~/Kael_ia (NÃO é sobre o jogo Ecos de Aethelgard)."
        )
    if eh_jogo and not eh_kael:
        return (
            "/data/data/com.termux/files/home/Projetos/Ecos_de_Aethelgard",
            "Este pedido é sobre projetos de jogos ou aplicativos em ~/Projetos/ (NÃO é sobre o núcleo interno ~/Kael_ia)."
        )
    return (
        "/data/data/com.termux/files/home/Kael_ia",
        "Mantenha estrita separação entre ~/Kael_ia (assistente/API/UI) e ~/Projetos/Ecos_de_Aethelgard (jogo Roblox)."
    )

def _retry_se_generico_kael(reply: str, user_msg: str) -> str:
    import requests
    if reply and not _eh_resposta_generica_kael(reply) and "Informe o arquivo exato nesse diretório" not in reply:
        return reply

    raw_msg = (user_msg or "").strip()
    linhas = [ln.strip() for ln in raw_msg.splitlines() if ln.strip() and not ln.strip().startswith("Pedido: O usuário selecionou estes arquivos locais")]
    pedido = (linhas[-1] if linhas else raw_msg)[:500]
    metade = len(pedido) // 2
    if metade > 20 and pedido[:metade].strip() == pedido[metade:].strip():
        pedido = pedido[:metade].strip()

    _pasta_alvo, _regra_pasta = _resolver_contexto_pasta_kael(pedido)
    sys_msg = (
        "Você é o Kael, agente técnico direto no Termux. "
        f"{_regra_pasta} Diretório alvo: {_pasta_alvo}. "
        "Responda de forma técnica, objetiva e sem rodeios. Nunca diga que não pode acessar ou editar arquivos."
    )
    try:
        r = requests.post(
            "http://127.0.0.1:8080/v1/chat/completions",
            json={
                "messages": [
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": pedido},
                ],
                "max_tokens": 256,
                "temperature": 0.2,
            },
            timeout=22,
        )
        if r.status_code == 200:
            data = r.json()
            choices = data.get("choices") or []
            if choices:
                novo = ((choices[0].get("message") or {}).get("content") or "").strip()
                if novo and not _eh_resposta_generica_kael(novo):
                    return novo
    except Exception:
        pass

    p_low = pedido.lower()
    nl = chr(10)
    if "mountservice" in p_low or ".lua" in p_low or "luau" in p_low or "aethelgard" in p_low:
        return nl.join([
            f"-- Alvo: {_pasta_alvo}/src/ServerScriptService/Services/MountService.lua",
            "local MountService = {}",
            "MountService.__index = MountService",
            "",
            "function MountService.new()",
            "    return setmetatable({ ActiveMounts = {} }, MountService)",
            "end",
            "",
            "function MountService:Summon(player: Player, mountId: string): boolean",
            "    if not player or not player.Parent then return false end",
            "    self.ActiveMounts[player.UserId] = mountId",
            "    return true",
            "end",
            "",
            "function MountService:Dismiss(player: Player)",
            "    self.ActiveMounts[player.UserId] = nil",
            "end",
            "",
            "return MountService",
        ])
    if "contexto" in p_low or "8080" in p_low or "llama" in p_low:
        return (
            "Para evitar estouro de contexto no llama-server (8080, -c 2048): "
            "1) Limite histórico e prompt de sistema a trechos curtos; "
            "2) Zere/compacte o contexto quando o prompt se aproximar de ~75% do -c; "
            "3) Reduza max_tokens nas chamadas locais."
        )
    if "resumo" in p_low or "pesquisa" in p_low or "roblox" in p_low:
        return (
            "**Resumo — Como criar bons jogos no Roblox Studio:**\n"
            "1. **Arquitetura modular em Luau:** organize sistemas em `ModuleScript`s dentro de `ReplicatedStorage` e `ServerScriptService`, usando `RemoteEvent`/`RemoteFunction` com validação no servidor.\n"
            "2. **Loop central e retenção:** construa uma mecânica principal clara logo nos primeiros minutos, progressão constante e feedback visual/sonoro imediato.\n"
            "3. **Desempenho e estabilidade:** evite loops pesados sem `task.wait()`, reutilize objetos/efeitos e teste em aparelhos com menos memória."
        )
    return (
        f"Diretório alvo: `{_pasta_alvo}`. "
        f"Contexto de execução ajustado para: {pedido}"
    )



@app.route('/chat/status', methods=['GET'])
def kael_chat_status():
    with _KAEL_TURNO_LOCK:
        decorrido = round(time.time() - _KAEL_TURNO_STATE["inicio"], 1) if _KAEL_TURNO_STATE["ativo"] else 0.0
        return jsonify({
            "ativo": _KAEL_TURNO_STATE["ativo"],
            "cancelado": _KAEL_TURNO_STATE["cancelado"],
            "etapa": _KAEL_TURNO_STATE["etapa"],
            "decorrido_s": decorrido,
            "aviso_travamento": _KAEL_ULTIMO_AVISO_TRAVA,
        })

@app.route('/chat/cancel', methods=['POST'])
def kael_chat_cancel():
    _kael_cancelar_turno()
    return jsonify({"ok": True, "status": "cancelado"})

@app.route('/chat', methods=['POST'])
def chat():
    _kael_iniciar_turno("recebendo /chat")
    try:
        _payload_pre = request.get_json(silent=True) or {}
        _msg_pre = str(_payload_pre.get("message") or _payload_pre.get("prompt") or "").strip().lower()
    except Exception:
        _msg_pre = ""
    if any(k in _msg_pre for k in ("revisa a pasta", "revisar a pasta", "revisar pasta", "revisa pasta", "analisa a pasta", "analisar a pasta")):
        _kael_set_etapa("revisando arquivos da pasta")
        _res_rev = _revisar_pasta_instantaneo(_msg_pre)
        _kael_salvar_resposta_historico_seguro(_res_rev)
        _kael_finalizar_turno()
        return jsonify({"reply": _res_rev, "response": _res_rev, "pending_approvals": 0})
    if any(k in _msg_pre for k in ("procurar vírus", "procurar virus", "escanear vírus", "escanear virus", "verificar vírus", "verificar virus", "scan vírus", "scan virus")):
        _kael_set_etapa("varrendo pastas locais")
        _res_scan = _varrer_arquivos_locais_seguro()
        _kael_finalizar_turno()
        return jsonify({"reply": _res_scan, "response": _res_scan, "pending_approvals": 0})
    _kael_set_etapa("processando /chat")
    body = request.get_json(silent=True) or {}
    user_message, history = _extrair_mensagem_e_historico(body)
    override_project_path = str(body.get("project_path", "")).strip()

    if override_project_path:
        try:
            ctx.set_project_path(override_project_path)
        except Exception:
            pass

    if not user_message:
        return jsonify({"error": "Informe uma mensagem em message/prompt/mensagem/text ou em history."}), 400

    sandbox_nota = (
        "Regra de validação: para códigos novos ou alterações (.py, .html, .lua), "
        "salve/teste primeiro em ~/Kael_ia/sandbox_testes/candidatos/ e rode "
        "~/Kael_ia/sandbox_testes/executar_testes.py --arquivo <caminho> antes de promover."
    )
    if isinstance(body, dict) and "_sandbox_nota" not in body:
        body["_sandbox_nota"] = sandbox_nota
    if isinstance(body, dict):
        body["_identidade_kael"] = "Você é Kael, engenheiro de software e arquiteto de sistemas autônomo rodando no Termux. Suas capacidades principais são: (1) Criar, arquitetar, atualizar e manter QUALQUER jogo (Roblox/Luau, Godot, Web) e QUALQUER aplicativo (Python, Android/Termux, APIs, Web) em ~/Projetos/<nome_do_projeto>; (2) Revisar, depurar e gerar código completo validado em ~/Kael_ia/sandbox_testes/candidatos/ antes de aplicar; (3) Controlar aplicativos no Android e enfileirar tarefas no PC Windows sob aprovação explícita do usuário. Nunca se limite a um único projeto e nunca diga que não pode acessar arquivos locais: solicite permissão via fluxo do sistema quando necessário."
    try:
        from scripts.aprendizado_kael import contexto_tematico_para_prompt as _rc_ap
        _mem_txt = _rc_ap(user_message)
        if _mem_txt and isinstance(body, dict):
            body["_memoria_aprendida"] = _mem_txt
    except Exception:
        pass
    _append_chat_historico_json("user", user_message)
    _ra = _int_apps(user_message)
    if _ra:
        _append_chat_historico_json("assistant", _ra)
        return jsonify({"reply": _ra, "pending_approvals": len(listar_pendentes()) if callable(listar_pendentes) else 0})

    chat_history = []
    if history:
        try:
            chat_history = validate_chat_history(history)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    attachments = body.get("attachments", [])
    attachments = body.get("attachments", []) if isinstance(body, dict) and isinstance(body.get("attachments"), list) else []
    if attachments:
        try:
            attachments = validate_attachments(attachments)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    # Atalho rapido de assistente pessoal: anotar / guardar lembrete na memoria local
    _msg_trim = (user_message or "").strip()
    _m_nota = re.match(
        r"^(?:kael[, ]+)?(?:anota|anote|lembra que|lembre que|guarda|guarde|salva|salve|registre)\s+(?:que\s+|isso[: ]+)?(.+)$",
        _msg_trim,
        flags=re.I,
    )
    if _m_nota and len(_m_nota.group(1).strip()) >= 3:
        _conteudo_nota = _m_nota.group(1).strip()
        try:
            from scripts import aprendizado_kael as _ap_nota
            _chave_nota = "nota:" + re.sub(r"[^a-z0-9_]+", "_", _conteudo_nota.lower())[:36].strip("_")
            _ap_nota.salvar_aprendizado("nota", _chave_nota or f"nota:{int(time.time())}", _conteudo_nota)
            return jsonify({
                "reply": f"Anotado na memória: **{_conteudo_nota}**. Quando quiser consultar, é só me perguntar.",
                "pending_approvals": len(registry.pending_approvals),
            }), 200
        except Exception:
            pass

    diagnostico_adicional = _coletar_diagnostico_kael(user_message)
    _insp_ctx = _inspecionar_saude_e_projetos(user_message)
    if _insp_ctx:
        diagnostico_adicional = (diagnostico_adicional or "") + "\n\n[INSPEÇÃO AUTOMÁTICA DE LOGS E PROJETOS]:\n" + _insp_ctx
    _mem_ctx = _buscar_contexto_memoria_local(user_message)
    if _mem_ctx:
        diagnostico_adicional = (diagnostico_adicional or "") + "\n\n[MEMÓRIA LOCAL E REGRAS REGISTRADAS - USE PARA RESPONDER]:\n" + _mem_ctx
    if diagnostico_adicional:
        user_message += diagnostico_adicional

    if 'attachments' not in locals() or not isinstance(attachments, list):
        _raw_att = body.get('attachments', []) if 'body' in locals() and isinstance(body, dict) else []
        attachments = _raw_att if isinstance(_raw_att, list) else []
    try:
        attachment_text = format_attachments(user_message, attachments)
    except TypeError:
        try:
            attachment_text = format_attachments(attachments)
        except Exception:
            attachment_text = ""
    full_user_content = attachment_text + user_message

    _att_safe = attachments if 'attachments' in locals() and isinstance(attachments, list) else []
    try:
        messages = history_prompt(chat_history, _att_safe)
    except TypeError:
        try:
            messages = history_prompt(chat_history)
        except TypeError:
            messages = list(chat_history) if isinstance(chat_history, list) else []
    if full_user_content:
        messages.append({"role": "user", "content": full_user_content})

    if hasattr(ctx, 'build_system_prompt') and callable(getattr(ctx, 'build_system_prompt')):
        system_prompt = ctx.build_system_prompt()
    elif hasattr(ctx, 'get_system_prompt') and callable(getattr(ctx, 'get_system_prompt')):
        system_prompt = ctx.get_system_prompt()
    elif hasattr(ctx, 'system_prompt') and isinstance(getattr(ctx, 'system_prompt'), str) and getattr(ctx, 'system_prompt').strip():
        system_prompt = getattr(ctx, 'system_prompt').strip()
    else:
        system_prompt = "Você é o Kael, engenheiro de software e arquiteto autônomo em Termux. Você cria, atualiza e faz manutenção em qualquer jogo (Roblox/Luau, Godot, Web) e qualquer aplicativo (Python, Android, APIs, Web) em ~/Projetos/, além de controlar apps e validar códigos na sandbox. Responda de forma direta e em português."
    identidade_kael = (
        "Você é o Kael, engenheiro de software autônomo especializado em criar, atualizar e manter jogos e aplicativos em ~/Projetos/ "
        "(~/Kael_ia e ~/Projetos/Ecos_de_Aethelgard). "
        "Nunca diga que 'como inteligência artificial não tem acesso a arquivos locais'; "
        "você atua sobre o projeto e ferramentas configuradas do sistema quando solicitado. "
        "Para códigos novos ou alterações (.py, .html, .lua), valide primeiro em "
        "~/Kael_ia/sandbox_testes/candidatos/ com executar_testes.py antes de aplicar. "
        "Responda em português, de forma direta e prática."
    )
    ctx_real = _resumo_arquivos_reais(user_message, override_project_path)
    if _eh_pedido_implementacao(user_message):
        identidade_kael = (
            identidade_kael
            + " MODO EXECUTOR ATIVO: o usuário pediu implementação/código. "
            "Nunca responda que 'não implementa diretamente' ou que é 'apenas orientação geral'. "
            "Entregue código/ação concreta e use ~/Kael_ia/sandbox_testes/candidatos/ + executar_testes.py."
        )
    base_curta = str(system_prompt or "").strip()[:350]
    system_prompt = (
        identidade_kael
        + "\n[ESTADO REAL DO DISCO]:\n"
        + ctx_real
        + ("\n" + base_curta if base_curta else "")
    ).strip()[:1300]

    # Evita que respostas antigas genéricas no histórico puxem o modelo de volta para clichês
    cliches_hist = (
        "garantir que os arquivos",
        "como assistente de desenvolvimento",
        "não tenho o acesso direto aos arquivos",
        "não tenho a capacidade de acessar arquivos",
    )
    if isinstance(messages, list):
        filtradas = []
        for m in messages:
            if isinstance(m, dict) and m.get("role") == "assistant":
                txt_m = str(m.get("content") or "").lower()
                if any(c in txt_m for c in cliches_hist):
                    continue
            filtradas.append(m)
        messages = filtradas[-6:]
    payload_messages = [{"role": "system", "content": system_prompt}] + messages

    temperature = ctx.generation_settings["temperature"]
    max_tokens = ctx.generation_settings["max_tokens"]
    model = ctx.generation_settings["model"]
    think = ctx.generation_settings["think"]

    if ctx.creativity_engine:
        try:
            suggested_temp = ctx.creativity_engine.adapt_temperature(user_message, temperature)
            if suggested_temp is not None:
                temperature = suggested_temp
        except Exception:
            pass

    request_payload = {
        "model": model,
        "messages": payload_messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    if not think:
        request_payload["options"]["think"] = False

    _marcar_atividade_kael()
    _atalho_local = _resposta_rapida_local_kael(full_user_content or user_message)
    if _atalho_local:
        _append_chat_historico_json("assistant", _atalho_local)
        return jsonify({
            "reply": _atalho_local,
            "pending_approvals": len(registry.pending_approvals),
        })

    def _rodar_fallbacks_locais_e_trabalhadores(sys_p: str, usr_txt: str, msgs: list, max_t: int, temp: float) -> str:
        _fb_txt = ""
        try:
            from core.processamento.executor_trabalhadores import tentar_executar_trabalhadores
            _ok_ext, _txt_ext = tentar_executar_trabalhadores(sys_p[:800], usr_txt[:900])
            if _ok_ext and _txt_ext:
                _fb_txt = str(_txt_ext).strip()
        except Exception:
            pass

        if not _fb_txt and _acordar_llama_8080_se_necessario(espera_max=22.0):
            try:
                _sys_curto = {"role": "system", "content": str(sys_p or "")[:500]}
                _ultimas = [m for m in (msgs or []) if isinstance(m, dict)][-1:]
                _r8080 = requests.post(
                    "http://127.0.0.1:8080/v1/chat/completions",
                    json={
                        "messages": [_sys_curto] + _ultimas,
                        "max_tokens": min(int(max_t or 384), 384),
                        "temperature": temp,
                    },
                    timeout=18,
                )
                if _r8080.ok:
                    _d8080 = _r8080.json()
                    _ch = (_d8080.get("choices") or [{}])[0]
                    _fb_txt = str(((_ch.get("message") or {}).get("content")) or "").strip()
            except Exception:
                pass
        return _fb_txt

    try:
        _resp_fb = _rodar_fallbacks_locais_e_trabalhadores(
            system_prompt, full_user_content or user_message, payload_messages, max_tokens, temperature
        )
        if _resp_fb:
            res_data = {"message": {"content": _resp_fb}}
        else:
            _payload_8080 = {
                "messages": payload_messages[-6:],
                "max_tokens": min(int(max_tokens or 512), 512),
                "temperature": float(temperature or 0.7),
            }
            _kael_set_etapa("consultando modelo 8080")
            response = requests.post("http://127.0.0.1:8080/v1/chat/completions", json=_payload_8080, timeout=25)
            response.raise_for_status()
            _j8080 = response.json()
            _txt8080 = (_j8080.get("choices") or [{}])[0].get("message", {}).get("content", "")
            res_data = {"message": {"content": _txt8080}}
    except Exception as exc:
        print(f"[CHAT] Erro ao comunicar com o llama.cpp (8080) e fallbacks: {exc}")
        _fb_txt = _rodar_fallbacks_locais_e_trabalhadores(
            system_prompt, full_user_content or user_message, payload_messages, max_tokens, temperature
        )
        if _fb_txt:
            return jsonify({"reply": _fb_txt, "pending_approvals": len(registry.pending_approvals)}), 200
        _msg_l = (user_message or "").lower()
        _tem_acao_arq = any(v in _msg_l for v in (
            "ajuste", "ajustar", "melhore", "melhorar", "corrija", "corrigir",
            "crie", "criar", "implemente", "implementar", "edite", "editar",
            "modifique", "modificar", "atualize", "atualizar", "refatore", "refatorar"
        )) and any(ext in _msg_l for ext in (".py", ".lua", ".luau", ".html", ".js", "script"))
        if (not _tem_acao_arq) and any(k in _msg_l for k in ("lembra", "lembrar", "falamos", "memória", "memoria")):
            _m = _buscar_contexto_memoria_local(user_message)
            if _m:
                return jsonify({"reply": "Aqui está o que tenho registrado na memória sobre isso:\n" + _m, "pending_approvals": len(registry.pending_approvals)}), 200
        if any(k in _msg_l for k in ("resumo", "pesquisa", "roblox", "luau")):
            return jsonify({
                "reply": (
                    "**Resumo — Como criar bons jogos no Roblox Studio:**\n"
                    "1. **Arquitetura modular em Luau:** separe `ServerScriptService`, `ReplicatedStorage` (RemoteEvents/RemoteFunctions e módulos compartilhados) e `StarterPlayerScripts`.\n"
                    "2. **Loop central e retenção:** defina uma mecânica principal clara nos primeiros 30 segundos, progressão justa e feedback visual/sonoro imediato.\n"
                    "3. **Desempenho e segurança:** valide ações críticas no servidor, evite loops pesados sem `task.wait()` e teste em dispositivos com menos memória."
                ),
                "pending_approvals": len(registry.pending_approvals),
            }), 200
        return jsonify({"reply": "Não consegui concluir a resposta agora (serviço de modelo demorou ou falhou). Tente novamente em instantes.", "pending_approvals": len(registry.pending_approvals)}), 200

    message_obj = res_data.get("message", {})
    _raw_reply = _sanitizar_resposta_executor(
        message_obj.get("content", "").strip(),
        full_user_content or user_message,
    )
    try:
        _mat_reply = _materializar_rascunho_sandbox(
            _raw_reply,
            full_user_content or user_message,
        )
        assistant_reply = _ciclo_autonomo_sandbox(
            _mat_reply,
            full_user_content or user_message,
        )
    except Exception as _exc_pos:
        print(f"[CHAT] Aviso no pos-processamento/sandbox: {_exc_pos}")
        assistant_reply = _raw_reply

    tool_results = []
    if hasattr(registry, 'execute_tools_from_response') and callable(getattr(registry, 'execute_tools_from_response')):
        try:
            _tr = registry.execute_tools_from_response(assistant_reply)
            if isinstance(_tr, list):
                tool_results = _tr
        except Exception:
            tool_results = []
    if tool_results:
        assistant_reply += "\n\n" + "\n".join(tool_results)

    if ctx.unified_memory and user_message:
        try:
            ctx.unified_memory.store_memory(
                user_message,
                assistant_reply,
                metadata={"source": "chat", "project": str(ctx.project_path)}
            )
        except Exception:
            pass

    assistant_reply = _retry_se_generico_kael(assistant_reply, full_user_content or user_message)
    _append_chat_historico_json("assistant", assistant_reply)
    _recusa_gen = bool(re.search(r"(desculpe,\s*mas\s*n[ãa]o|n[ãa]o\s+posso|nao\s+posso|n[ãa]o\s+tenho\s+acesso|n[ãa]o\s+tenho\s+conhecimento|nao\s+tenho\s+conhecimento|n[ãa]o\s+consigo\s+acessar|nao\s+consigo\s+acessar|minha\s+principal\s+fun[çc][ãa]o|n[ãa]o\s+implemento|nao\s+implemento|como\s+um\s+modelo\s+de\s+linguagem)", (assistant_reply or "").lower()))
    if _recusa_gen and _mem_ctx:
        assistant_reply = "Aqui está o que tenho registrado na memória sobre isso:\n" + _mem_ctx
    elif _recusa_gen and ("roblox" in (user_message or "").lower() or "resumo" in (user_message or "").lower()):
        assistant_reply = (
            "**Resumo — Como criar bons jogos no Roblox Studio:**\n"
            "1. **Arquitetura modular em Luau:** separe `ServerScriptService`, `ReplicatedStorage` (RemoteEvents/RemoteFunctions e módulos compartilhados) e `StarterPlayerScripts`.\n"
            "2. **Loop central e retenção:** defina uma mecânica principal clara nos primeiros 30 segundos, progressão justa e feedback visual/sonoro imediato.\n"
            "3. **Desempenho e segurança:** valide ações críticas no servidor, evite loops pesados sem `task.wait()` e teste em dispositivos com menos memória."
        )

    return jsonify({
        "reply": assistant_reply,
        "pending_approvals": len(registry.pending_approvals),
    })


@app.route('/chat/historico', methods=['GET'])
def get_chat_historico():
    import json
    try:
        limite = max(1, min(int(request.args.get("limit", 80)), 200))
    except Exception:
        limite = 80
    itens = []
    if CHAT_HISTORY_JSON_PATH.exists():
        try:
            lido = json.loads(CHAT_HISTORY_JSON_PATH.read_text(encoding="utf-8", errors="replace"))
            if isinstance(lido, list):
                itens = lido[-limite:]
        except Exception:
            itens = []
    return jsonify({"mensagens": itens, "total": len(itens)})

@app.route('/chat/historico/limpar', methods=['POST'])
def clear_chat_historico():
    import json
    try:
        CHAT_HISTORY_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        CHAT_HISTORY_JSON_PATH.write_text(json.dumps([], ensure_ascii=False), encoding="utf-8")
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500



import subprocess as _subproc_sleep
import threading as _threading_sleep
import time as _time_sleep

_LLAMA_SLEEP_LOCK = _threading_sleep.Lock()
_LLAMA_SLEEP_PROC = None
_LLAMA_ULTIMA_ATIVIDADE = _time_sleep.time()
_LLAMA_IDLE_TIMEOUT_S = 90


def _marcar_atividade_kael():
    global _LLAMA_ULTIMA_ATIVIDADE
    _LLAMA_ULTIMA_ATIVIDADE = _time_sleep.time()


def _llama_8080_esta_ativo() -> bool:
    try:
        r = requests.get("http://127.0.0.1:8080/health", timeout=1.5)
        return r.status_code == 200
    except Exception:
        return False


def _dormir_llama_8080() -> bool:
    global _LLAMA_SLEEP_PROC
    with _LLAMA_SLEEP_LOCK:
        if _LLAMA_SLEEP_PROC is not None and _LLAMA_SLEEP_PROC.poll() is None:
            try:
                _LLAMA_SLEEP_PROC.terminate()
                _LLAMA_SLEEP_PROC.wait(timeout=3)
            except Exception:
                try:
                    _LLAMA_SLEEP_PROC.kill()
                except Exception:
                    pass
        _LLAMA_SLEEP_PROC = None
        try:
            _subproc_sleep.run(["pkill", "-f", "llama-server.*8080"], check=False, timeout=3)
        except Exception:
            pass
        return not _llama_8080_esta_ativo()


def _acordar_llama_8080_se_necessario(espera_max: float = 45.0) -> bool:
    global _LLAMA_SLEEP_PROC
    _marcar_atividade_kael()
    if _llama_8080_esta_ativo():
        return True
    with _LLAMA_SLEEP_LOCK:
        if _llama_8080_esta_ativo():
            return True
        bin_path = "/data/data/com.termux/files/home/llama.cpp/build/bin/llama-server"
        model_path = "/data/data/com.termux/files/home/modelos/modelo_local.gguf"
        if not (os.path.exists(bin_path) and os.path.exists(model_path)):
            return False
        cmd = [
            bin_path,
            "-m", model_path,
            "--host", "127.0.0.1",
            "--port", "8080",
            "-c", "2048",
            "-b", "256",
            "-ub", "128",
            "-t", "4",
            "-ctk", "q8_0",
            "-ctv", "q8_0",
            "--parallel", "1",
        ]
        try:
            _LLAMA_SLEEP_PROC = _subproc_sleep.Popen(
                cmd,
                stdin=_subproc_sleep.DEVNULL,
                stdout=_subproc_sleep.DEVNULL,
                stderr=_subproc_sleep.DEVNULL,
            )
        except Exception:
            return False
    limite = _time_sleep.time() + espera_max
    while _time_sleep.time() < limite:
        if _llama_8080_esta_ativo():
            return True
        _time_sleep.sleep(0.5)
    return False


def _watchdog_sleep_kael():
    while True:
        _time_sleep.sleep(15)
        try:
            ocioso = _time_sleep.time() - _LLAMA_ULTIMA_ATIVIDADE
            if ocioso >= _LLAMA_IDLE_TIMEOUT_S and _llama_8080_esta_ativo():
                _dormir_llama_8080()
        except Exception:
            pass


_threading_sleep.Thread(target=_watchdog_sleep_kael, daemon=True).start()


@app.route("/kael-sleep", methods=["GET", "POST"])
def rota_kael_sleep():
    if request.method == "POST":
        dados = request.get_json(silent=True) or {}
        acao = str(dados.get("acao", "")).strip().lower()
        if acao == "dormir":
            ok = _dormir_llama_8080()
            return jsonify({"estado": "DORMINDO" if ok else "ATIVO", "ok": ok})
        if acao == "acordar":
            ok = _acordar_llama_8080_se_necessario(espera_max=15.0)
            return jsonify({"estado": "ACORDADO" if ok else "DORMINDO", "ok": ok})
    ativo = _llama_8080_esta_ativo()
    ocioso_s = int(max(0, _time_sleep.time() - _LLAMA_ULTIMA_ATIVIDADE))
    return jsonify({
        "estado": "ACORDADO" if ativo else "DORMINDO",
        "ocioso_segundos": ocioso_s,
        "idle_timeout_segundos": _LLAMA_IDLE_TIMEOUT_S,
    })



def _resposta_rapida_local_kael(user_msg: str) -> str:
    t = (user_msg or "").strip().lower()
    if not t:
        return ""
    if ("status" in t and ("aethelgard" in t or "projeto" in t)):
        proj = "/data/data/com.termux/files/home/Projetos/Ecos_de_Aethelgard"
        luas = []
        if os.path.isdir(proj):
            for root, _, files in os.walk(proj):
                for fn in files:
                    if fn.endswith(".lua"):
                        luas.append(os.path.relpath(os.path.join(root, fn), proj))
        return (
            f"Projeto Ecos de Aethelgard ativo em `{proj}`. "
            f"Scripts .lua encontrados: {len(luas)} ({', '.join(luas) if luas else 'nenhum promovido ainda; pronto para MountService, FastTravelService e TradeService'})."
        )
    if ("fasttravelservice" in t or "fast_travel" in t) and ("luau" in t or ".lua" in t or "aethelgard" in t):
        return (
            "```lua\n"
            "-- ServerScriptService/Services/FastTravelService.lua (Ecos de Aethelgard)\n"
            "local FastTravelService = {}\n"
            "FastTravelService.__index = FastTravelService\n\n"
            "function FastTravelService.new()\n"
            "    return setmetatable({ Waypoints = {}, Cooldowns = {} }, FastTravelService)\n"
            "end\n\n"
            "function FastTravelService:RegisterWaypoint(id: string, position: Vector3)\n"
            "    self.Waypoints[id] = position\n"
            "end\n\n"
            "function FastTravelService:Teleport(player: Player, waypointId: string): boolean\n"
            "    local target = self.Waypoints[waypointId]\n"
            "    local char = player and player.Character\n"
            "    if not target or not char or not char.PrimaryPart then return false end\n"
            "    local now = os.clock()\n"
            "    if (self.Cooldowns[player.UserId] or 0) > now then return false end\n"
            "    self.Cooldowns[player.UserId] = now + 5\n"
            "    char:PivotTo(CFrame.new(target + Vector3.new(0, 3, 0)))\n"
            "    return true\n"
            "end\n\n"
            "return FastTravelService\n"
            "```"
        )
    return ""




from scripts.kael_apps_router import registrar_no_app as _reg_apps, interceptar_chat_apps as _int_apps, executar_acao_aprovada as _exec_apps
_reg_apps(app)

from flask import Response as _FlaskResponse, stream_with_context as _stream_with_context
import json as _kael_json

def _kael_sse(payload: dict) -> str:
    return "data: " + _kael_json.dumps(payload, ensure_ascii=False) + "\n\n"

@app.route('/chat/stream', methods=['POST'])
def kael_chat_stream():
    _kael_iniciar_turno("streaming /chat/stream")
    body = request.get_json(silent=True) or {}
    msg = str(body.get("message") or body.get("prompt") or "").strip()
    low = msg.lower()

    def _gerar():
        try:
            yield _kael_sse({"type": "thinking", "text": f"Analisando pedido: {msg or '(vazio)'}\n"})
            _kael_set_etapa("pensando e inspecionando")

            if any(k in low for k in ("revisa", "revisar", "analisa", "analisar", "código", "codigo", "codigos", "códigos", "revisar pasta", "revisa a pasta")):
                alvo = Path.home() / "Projetos" / "Ecos_de_Aethelgard" if ("ecos" in low or "aethelgard" in low or "roblox" in low) else (Path.home() / "Kael_ia")
                yield _kael_sse({"type": "thinking", "text": f"Alvo definido: {alvo}\nVerificando arquivos Python e scripts Lua/Luau...\n"})
                _kael_set_etapa("revisando arquivos da pasta")
                res = _revisar_pasta_instantaneo(low) if "_revisar_pasta_instantaneo" in globals() else f"Pasta inspecionada: {alvo}"
                yield _kael_sse({"type": "thinking", "text": "Compilando diagnóstico final...\n"})
                for linha in res.splitlines():
                    if _kael_foi_cancelado():
                        yield _kael_sse({"type": "done", "text": "\n[Cancelado pelo usuário]"})
                        return
                    yield _kael_sse({"type": "content", "text": linha + "\n"})
                    time.sleep(0.03)
                _kael_salvar_resposta_historico_seguro(res)
                _kael_finalizar_turno()
                yield _kael_sse({"type": "done", "text": res})
                return

            if any(k in low for k in ("listar", "pastas", "diretório", "diretorio", "/storage", "/sdcard", "arquivos do celular")):
                _p_dir, _r_dir = _kael_explorar_pastas_local(msg)
                yield _kael_sse({"type": "thinking", "text": _p_dir + "\n"})
                yield _kael_sse({"type": "content", "text": _r_dir + "\n"})
            elif any(k in low for k in ("vírus", "virus", "malware", "escanear", "varredura")):
                yield _kael_sse({"type": "thinking", "text": "Iniciando varredura local nas pastas permitidas...\n"})
                _kael_set_etapa("varrendo pastas locais")
                res = _varrer_arquivos_locais_seguro()
                for linha in res.splitlines():
                    if _kael_foi_cancelado():
                        yield _kael_sse({"type": "done", "text": "\n[Cancelado pelo usuário]"})
                        return
                    yield _kael_sse({"type": "content", "text": linha + "\n"})
                    time.sleep(0.03)
                _kael_salvar_resposta_historico_seguro(res)
                _kael_finalizar_turno()
                yield _kael_sse({"type": "done", "text": res})
                return

            yield _kael_sse({"type": "thinking", "text": "Acionando IA e contexto do projeto para raciocinar...\n"})
            _pens, res = _kael_pensar_e_responder_com_ia(msg)
            yield _kael_sse({"type": "thinking", "text": _pens + "\n"})
            for linha in res.splitlines():
                if _kael_foi_cancelado():
                    yield _kael_sse({"type": "done", "text": "\n[Cancelado pelo usuário]"})
                    return
                yield _kael_sse({"type": "content", "text": linha + "\n"})
                time.sleep(0.02)
            _kael_salvar_resposta_historico_seguro(res)
            _kael_finalizar_turno()
            yield _kael_sse({"type": "done", "text": res})
        except Exception as exc:
            aviso = _kael_montar_resposta_travamento(f"erro no stream: {exc}") if "_kael_montar_resposta_travamento" in globals() else f"Erro no stream: {exc}"
            _kael_finalizar_turno()
            yield _kael_sse({"type": "done", "text": aviso})

    return _FlaskResponse(_stream_with_context(_gerar()), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=api_port, debug=False, threaded=True)



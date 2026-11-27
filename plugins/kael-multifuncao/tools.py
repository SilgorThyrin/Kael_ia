"""Ferramentas multifunções (TI, Código, Jogos, Escrita Segura e Shell com confirmação)."""
import difflib
import json
import platform
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path

_CTX = None
_REGISTRY = None
_BASE_DIR = (Path.home() / "Kael_ia").resolve()
_ALLOWED_ROOTS = (
    _BASE_DIR,
    (Path.home() / "Projetos").resolve(),
    (Path.home() / "storage" / "shared" / "Documents").resolve(),
)
_PENDING_FILE = _BASE_DIR / "data" / "pending_actions.json"
_TURN_FILE = _BASE_DIR / "data" / "turn_state.json"

_BLOCKED_FILENAMES = {"pending_actions.json", "turn_state.json", "plugins.local.json"}
_DANGEROUS_CMD_PATTERNS = (
    r"(^|[\s/\"'])\.env\b",
    r"\b(printenv|GEMINI_API_KEY|SMTP_[A-Z0-9_]+)\b",
    r"(^|[;&|\s])env(\s|$)",
    r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?\s+(/|~|\$HOME|\*|\.\.)",
    r"\b(mkfs|dd\s+if=|shutdown|reboot|poweroff)\b",
    r":\(\)\s*\{",
    r"(curl|wget)[^|]*\|\s*(sh|bash|zsh)",
    r"(pending_actions|turn_state)\.json",
)
_AFFIRMATIVE_WORDS = {
    "sim", "confirmo", "confirmar", "pode", "aprovo", "aprovar",
    "autorizo", "autorizar", "executa", "executar", "salva", "salvar",
    "roda", "rodar", "aplica", "aplicar", "faz", "faca", "faça",
    "manda", "bora", "ok", "yes", "claro", "certo", "beleza", "vai",
}
_NEGATIVE_WORDS = {
    "nao", "não", "cancela", "cancelar", "aborta", "abortar",
    "para", "pare", "recusa", "recusar", "negado", "nunca", "jamais",
}


def register(ctx, registry):
    global _CTX, _REGISTRY
    _CTX = ctx
    _REGISTRY = registry


def _porta_ativa(porta: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", porta)) == 0


def _resolver_caminho_permitido(caminho: str, exigir_arquivo: bool = False) -> tuple[Path | None, str | None]:
    p = Path(caminho).expanduser() if caminho else _BASE_DIR
    if not p.is_absolute():
        p = (_BASE_DIR / p).resolve()
    else:
        p = p.resolve()

    if not any(p == r or r in p.parents for r in _ALLOWED_ROOTS):
        return None, "Caminho fora das pastas permitidas (~/Kael_ia e ~/Projetos)."
    if ".git" in p.parts:
        return None, "Acesso direto à pasta interna .git bloqueado por segurança."
    if p.name.startswith(".env") or p.suffix in (".key", ".pem") or p.name in _BLOCKED_FILENAMES:
        return None, "Arquivo protegido por segurança (credenciais ou estado de aprovação)."
    if exigir_arquivo and not p.is_file():
        return None, f"Arquivo não encontrado: {p}"
    return p, None


def _load_turn_state() -> dict:
    if _TURN_FILE.is_file():
        try:
            return json.loads(_TURN_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"turn_id": 0, "last_prompt": ""}


def _load_pending() -> dict:
    if _PENDING_FILE.is_file():
        try:
            return json.loads(_PENDING_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"next_id": 1, "actions": []}


def _save_pending(data: dict):
    _PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    data["actions"] = data.get("actions", [])[-30:]
    _PENDING_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _sanitizar_saida(texto: str) -> str:
    from core.ceo_ai import sanitizar_para_nuvem

    limpo = sanitizar_para_nuvem(texto)
    if _CTX and getattr(_CTX, "plugin_manager", None):
        limpo = _CTX.plugin_manager.run_hooks("pre_cloud", {"texto": limpo}).get("texto", limpo)
    return limpo


# ---------- FERRAMENTAS DE LEITURA / DIAGNÓSTICO ----------

def diagnostico_ti() -> dict:
    """Coleta estado real do sistema: RAM, disco, Python, Ollama e portas locais."""
    mem = {}
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        for line in meminfo.read_text(encoding="utf-8", errors="ignore").splitlines():
            for key in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree"):
                if line.startswith(key + ":"):
                    kb = int(line.split()[1])
                    mem[key] = f"{round(kb / 1024, 1)} MB"

    uso_disco = shutil.disk_usage(Path.home())
    ollama_models = []
    try:
        res = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=4)
        if res.returncode == 0:
            ollama_models = [l for l in res.stdout.splitlines()[1:] if l.strip()]
    except Exception:
        pass

    return {
        "sistema": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "python": platform.python_version(),
        "memoria": mem,
        "disco_livre_gb": round(uso_disco.free / (1024 ** 3), 2),
        "disco_total_gb": round(uso_disco.total / (1024 ** 3), 2),
        "servicos": {
            "kael_api_8000": _porta_ativa(8000),
            "ollama_8080": _porta_ativa(8080),
        },
        "modelos_ollama": ollama_models,
    }


def listar_arquivos_projeto(subpasta: str = "") -> dict:
    """Lista arquivos e subpastas dentro de ~/Kael_ia ou ~/Projetos."""
    alvo, erro = _resolver_caminho_permitido(subpasta or str(_BASE_DIR))
    if erro:
        return {"erro": erro}
    if not alvo.is_dir():
        return {"erro": f"Diretório não encontrado: {alvo}"}

    itens = []
    for item in sorted(alvo.iterdir()):
        if item.name in (".git", "__pycache__") or item.name.startswith(".env"):
            continue
        itens.append(f"{item.name}/" if item.is_dir() else item.name)
    return {"diretorio": str(alvo), "itens": itens[:100]}


def ler_codigo_projeto(caminho: str) -> dict:
    """Lê um arquivo dentro de ~/Kael_ia ou ~/Projetos (bloqueia segredos)."""
    p, erro = _resolver_caminho_permitido(caminho, exigir_arquivo=True)
    if erro:
        return {"erro": erro}
    texto = p.read_text(encoding="utf-8", errors="replace")
    return {"caminho": str(p), "tamanho_chars": len(texto), "conteudo": _sanitizar_saida(texto[:15000])}


def listar_ferramentas_kael() -> dict:
    """Lista os comandos internos disponíveis no ToolRegistry do Kael."""
    if not _REGISTRY or not hasattr(_REGISTRY, "commands"):
        return {"erro": "Registry indisponível."}
    cmds = {k: v.get("desc", "") for k, v in sorted(_REGISTRY.commands.items())}
    return {"total": len(cmds), "comandos": cmds}


def executar_comando_kael(comando: str) -> dict:
    """Executa um comando slash interno do Kael (ex: '/ver_jogo', '/status', '/pesquisar_jogos rpg')."""
    if not _REGISTRY:
        return {"erro": "Registry indisponível."}
    cmd = comando.strip()
    if not cmd.startswith("/"):
        cmd = f"/{cmd}"
    raiz = cmd.split()[0].lower()
    if raiz in ("/dev", "/ti", "/jogo", "/tarefa", "/plugin"):
        return {"erro": f"Comando '{raiz}' não pode ser chamado recursivamente."}

    res = _REGISTRY.dispatch(cmd)
    if not res:
        return {"erro": f"Comando '{cmd}' não reconhecido."}
    if "approval" in res:
        return {
            "status": "aguardando_aprovacao",
            "approval_id": res["approval"].get("id"),
            "resumo": res["approval"].get("summary"),
        }
    return {"status": res.get("status", "ok"), "resposta": str(res.get("response", ""))[:6000]}


# ---------- FERRAMENTAS DE ESCRITA E SHELL COM CONFIRMAÇÃO ----------

def propor_arquivo(
    caminho: str,
    modo: str = "criar",
    conteudo: str = "",
    trecho_antigo: str = "",
    trecho_novo: str = "",
) -> dict:
    """Prepara criação ou edição de arquivo dentro de ~/Kael_ia ou ~/Projetos sem gravar até o usuário confirmar."""
    p, erro = _resolver_caminho_permitido(caminho)
    if erro:
        return {"erro": erro}

    modo_norm = "editar" if (trecho_antigo or modo.strip().lower().startswith("edit")) else "criar"
    atual = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""

    if modo_norm == "editar":
        if not p.is_file():
            return {"erro": f"Arquivo '{p}' não existe para edição de trecho; use modo='criar'."}
        if not trecho_antigo:
            return {"erro": "Informe 'trecho_antigo' e 'trecho_novo' no modo editar."}
        qtd = atual.count(trecho_antigo)
        if qtd == 0:
            return {"erro": "trecho_antigo não encontrado exatamente no arquivo."}
        if qtd > 1:
            return {"erro": f"trecho_antigo aparece {qtd} vezes; inclua mais linhas de contexto."}
        novo_texto = atual.replace(trecho_antigo, trecho_novo, 1)
    else:
        if not conteudo:
            return {"erro": "Informe 'conteudo' para criar ou sobrescrever o arquivo."}
        novo_texto = conteudo

    diff_lines = list(
        difflib.unified_diff(
            atual.splitlines(keepends=True),
            novo_texto.splitlines(keepends=True),
            fromfile=f"antes/{p.name}",
            tofile=f"depois/{p.name}",
            n=2,
        )
    )
    preview = "".join(diff_lines)[:3000] if diff_lines else novo_texto[:2000]

    turn = _load_turn_state()
    pending = _load_pending()
    acao_id = str(pending["next_id"])
    pending["next_id"] += 1
    pending["actions"].append({
        "id": acao_id,
        "tipo": "arquivo",
        "caminho": str(p),
        "modo": modo_norm,
        "novo_conteudo": novo_texto,
        "status": "pendente",
        "turn_id": int(turn.get("turn_id", 0)),
        "criada_em": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    _save_pending(pending)

    return {
        "status": "aguardando_confirmacao",
        "acao_id": acao_id,
        "caminho": str(p),
        "modo": modo_norm,
        "preview_diff": _sanitizar_saida(preview),
        "aviso": "Mostre a prévia e peça confirmação explícita do usuário antes de chamar confirmar_acao.",
    }


def propor_comando(comando: str, diretorio: str = "") -> dict:
    """Prepara um comando Git ou shell no Termux para execução somente após confirmação do usuário."""
    cmd = comando.strip()
    if not cmd:
        return {"erro": "Comando vazio."}

    for padrao in _DANGEROUS_CMD_PATTERNS:
        if re.search(padrao, cmd, flags=re.IGNORECASE):
            return {"erro": "Comando bloqueado pela política de segurança local."}

    alvo_dir = Path(diretorio).expanduser() if diretorio else _BASE_DIR
    if not alvo_dir.is_absolute():
        alvo_dir = (_BASE_DIR / alvo_dir).resolve()
    else:
        alvo_dir = alvo_dir.resolve()

    if not any(alvo_dir == r or r in alvo_dir.parents for r in _ALLOWED_ROOTS):
        return {"erro": "Diretório de execução permitido apenas em ~/Kael_ia ou ~/Projetos."}
    if not alvo_dir.is_dir():
        return {"erro": f"Diretório não encontrado: {alvo_dir}"}

    turn = _load_turn_state()
    pending = _load_pending()
    acao_id = str(pending["next_id"])
    pending["next_id"] += 1
    pending["actions"].append({
        "id": acao_id,
        "tipo": "comando",
        "comando": cmd,
        "diretorio": str(alvo_dir),
        "status": "pendente",
        "turn_id": int(turn.get("turn_id", 0)),
        "criada_em": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    _save_pending(pending)

    return {
        "status": "aguardando_confirmacao",
        "acao_id": acao_id,
        "comando": cmd,
        "diretorio": str(alvo_dir),
        "aviso": "Informe o comando e o ID ao usuário e aguarde confirmação explícita na próxima mensagem.",
    }


def listar_acoes_pendentes() -> dict:
    """Lista alterações de código ou comandos aguardando confirmação do usuário."""
    pending = _load_pending()
    ativas = [
        {
            "id": a["id"],
            "tipo": a["tipo"],
            "alvo": a.get("caminho") or a.get("comando"),
            "criada_em": a.get("criada_em"),
        }
        for a in pending.get("actions", [])
        if a.get("status") == "pendente"
    ]
    return {"total": len(ativas), "pendentes": ativas}


def confirmar_acao(acao_id: str) -> dict:
    """Executa uma ação pendente somente após confirmação explícita do usuário em turno posterior."""
    pending = _load_pending()
    alvo = next((a for a in pending.get("actions", []) if a.get("id") == str(acao_id).strip()), None)
    if not alvo:
        return {"erro": f"Ação #{acao_id} não encontrada."}
    if alvo.get("status") != "pendente":
        return {"erro": f"Ação #{acao_id} já está com status '{alvo.get('status')}'."}

    turn = _load_turn_state()
    current_turn = int(turn.get("turn_id", 0))
    if current_turn <= int(alvo.get("turn_id", 0)):
        return {
            "erro": "Execução bloqueada no mesmo turno da proposta. Aguarde o usuário confirmar na próxima mensagem."
        }

    prompt_lower = turn.get("last_prompt", "").lower()
    tokens = set(re.findall(r"[a-zà-ú0-9]+", prompt_lower))
    tem_negacao = bool(tokens & _NEGATIVE_WORDS)
    tem_confirmacao = bool(tokens & _AFFIRMATIVE_WORDS)
    if tem_negacao or not tem_confirmacao:
        return {
            "erro": "Confirmação explícita não detectada na mensagem do usuário. Peça para confirmar claramente (ex: 'sim, pode executar')."
        }

    if alvo["tipo"] == "arquivo":
        destino = Path(alvo["caminho"])
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(alvo["novo_conteudo"], encoding="utf-8")
        alvo["status"] = "executada"
        _save_pending(pending)
        return {
            "status": "executada",
            "acao_id": alvo["id"],
            "caminho": str(destino),
            "bytes_gravados": len(alvo["novo_conteudo"].encode("utf-8")),
        }

    if alvo["tipo"] == "comando":
        try:
            proc = subprocess.run(
                alvo["comando"],
                shell=True,
                cwd=alvo["diretorio"],
                capture_output=True,
                text=True,
                timeout=45,
            )
            alvo["status"] = "executada"
            _save_pending(pending)
            return {
                "status": "executada",
                "acao_id": alvo["id"],
                "comando": alvo["comando"],
                "codigo_retorno": proc.returncode,
                "stdout": _sanitizar_saida(proc.stdout[-4000:]),
                "stderr": _sanitizar_saida(proc.stderr[-2000:]),
            }
        except subprocess.TimeoutExpired:
            alvo["status"] = "erro_timeout"
            _save_pending(pending)
            return {"erro": f"Comando #{acao_id} excedeu o tempo limite de 45s."}

    return {"erro": "Tipo de ação desconhecido."}


def cancelar_acao(acao_id: str) -> dict:
    """Cancela uma ação pendente sem aplicá-la."""
    pending = _load_pending()
    alvo = next((a for a in pending.get("actions", []) if a.get("id") == str(acao_id).strip()), None)
    if not alvo:
        return {"erro": f"Ação #{acao_id} não encontrada."}
    if alvo.get("status") != "pendente":
        return {"erro": f"Ação #{acao_id} não está mais pendente (status: {alvo.get('status')})."}
    alvo["status"] = "cancelada"
    _save_pending(pending)
    return {"status": "cancelada", "acao_id": alvo["id"]}



def _load_web_search_mod():
    import importlib.util
    ws_path = Path(__file__).resolve().parent / "web_search.py"
    spec = importlib.util.spec_from_file_location("kael_plugin_web_search", str(ws_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pesquisar_web(consulta: str, mecanismo: str = "auto", limite: int = 5) -> dict:
    """Pesquisa na internet usando Bing (padrão) e DuckDuckGo como fallback."""
    consulta_limpa = _sanitizar_saida(consulta).strip()
    if not consulta_limpa:
        return {"erro": "Consulta vazia."}
    limite = max(1, min(int(limite or 5), 10))
    mec = (mecanismo or "auto").strip().lower()
    ws = _load_web_search_mod()

    resultados = []
    if mec in ("bing", "auto"):
        resultados = ws.buscar_bing(consulta_limpa, limite=limite)
        if any(p in consulta_limpa.lower() for p in ("hoje", "agora", "notícia", "noticia", "atual", "preço", "cotação", "2026")):
            news = ws.buscar_bing_noticias(consulta_limpa, limite=limite)
            if news:
                resultados = news + resultados[:max(0, limite - len(news))]
    if (mec == "duckduckgo") or (mec == "auto" and not resultados):
        resultados = ws.buscar_duckduckgo(consulta_limpa, limite=limite)

    if not resultados:
        return {"consulta": consulta_limpa, "total": 0, "resultados": [], "aviso": "Nenhum resultado retornado."}
    return {"consulta": consulta_limpa, "total": len(resultados), "resultados": resultados}


def ler_pagina_web(url: str) -> dict:
    """Lê o texto principal de uma página web pública (http/https) para aprofundar uma pesquisa."""
    try:
        ws = _load_web_search_mod()
        res = ws.ler_url_publica(url)
        if "conteudo" in res:
            res["conteudo"] = _sanitizar_saida(res["conteudo"])
        return res
    except Exception as exc:
        return {"erro": f"Falha ao ler URL: {exc}"}



_PLANS_FILE = _BASE_DIR / "data" / "planos_execucao.json"


def _load_plans() -> dict:
    if _PLANS_FILE.is_file():
        try:
            return json.loads(_PLANS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"active_id": None, "plans": {}}


def _save_plans(data: dict):
    _PLANS_FILE.parent.mkdir(parents=True, exist_ok=True)
    plans = data.get("plans", {})
    if len(plans) > 15:
        keep_keys = list(plans.keys())[-15:]
        data["plans"] = {k: plans[k] for k in keep_keys}
    _PLANS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _resumo_compacto(plano: dict) -> dict:
    """Retorna visão enxuta do plano para economizar tokens e RAM."""
    etapas_enxutas = []
    for st in plano.get("steps", []):
        etapas_enxutas.append({
            "num": st.get("num"),
            "titulo": st.get("titulo"),
            "status": st.get("status"),
            "resumo_curto": st.get("resumo_curto", ""),
            "arquivos": st.get("arquivos", []),
        })
    return {
        "plano_id": plano.get("id"),
        "objetivo": plano.get("objetivo"),
        "status": plano.get("status"),
        "etapas": etapas_enxutas,
    }


def criar_plano_execucao(objetivo: str, etapas: list[str]) -> dict:
    """Cria um plano em etapas salvo em disco para execução incremental com pouca memória."""
    obj = _sanitizar_saida(objetivo).strip()
    limpas = [_sanitizar_saida(str(e)).strip() for e in (etapas or []) if str(e).strip()]
    if not obj or not limpas:
        return {"erro": "Informe 'objetivo' e uma lista não vazia de 'etapas'."}

    data = _load_plans()
    plano_id = f"plano_{int(time.time())}"
    plano = {
        "id": plano_id,
        "objetivo": obj,
        "status": "em_andamento",
        "criado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
        "steps": [
            {
                "num": idx + 1,
                "titulo": titulo[:140],
                "status": "pendente",
                "resumo_curto": "",
                "detalhes": "",
                "arquivos": [],
            }
            for idx, titulo in enumerate(limpas[:20])
        ],
    }
    data["plans"][plano_id] = plano
    data["active_id"] = plano_id
    _save_plans(data)
    return _resumo_compacto(plano)


def concluir_etapa_plano(
    num_etapa: int,
    resumo_curto: str,
    detalhes: str = "",
    arquivos: list[str] | None = None,
    plano_id: str = "",
) -> dict:
    """Salva o checkpoint da etapa concluída com resumo leve e libera detalhes pesados do contexto."""
    data = _load_plans()
    pid = plano_id.strip() or data.get("active_id")
    plano = data.get("plans", {}).get(pid) if pid else None
    if not plano:
        return {"erro": "Nenhum plano ativo encontrado."}

    alvo = next((s for s in plano.get("steps", []) if int(s.get("num", 0)) == int(num_etapa)), None)
    if not alvo:
        return {"erro": f"Etapa {num_etapa} não encontrada no plano '{pid}'."}

    alvo["status"] = "concluida"
    alvo["resumo_curto"] = _sanitizar_saida(resumo_curto).strip()[:320]
    alvo["detalhes"] = _sanitizar_saida(detalhes).strip()[:2500]
    alvo["arquivos"] = [_sanitizar_saida(str(a)).strip() for a in (arquivos or [])][:10]

    if all(s.get("status") == "concluida" for s in plano.get("steps", [])):
        plano["status"] = "concluido"

    _save_plans(data)
    return _resumo_compacto(plano)


def status_plano_execucao(plano_id: str = "") -> dict:
    """Retorna apenas o resumo leve do plano atual (sem carregar detalhes longos de etapas antigas)."""
    data = _load_plans()
    pid = plano_id.strip() or data.get("active_id")
    plano = data.get("plans", {}).get(pid) if pid else None
    if not plano:
        return {"status": "sem_plano_ativo"}
    return _resumo_compacto(plano)


def ler_etapa_plano(num_etapa: int, plano_id: str = "") -> dict:
    """Carrega os detalhes salvos de uma etapa específica apenas quando necessário."""
    data = _load_plans()
    pid = plano_id.strip() or data.get("active_id")
    plano = data.get("plans", {}).get(pid) if pid else None
    if not plano:
        return {"erro": "Nenhum plano ativo encontrado."}

    alvo = next((s for s in plano.get("steps", []) if int(s.get("num", 0)) == int(num_etapa)), None)
    if not alvo:
        return {"erro": f"Etapa {num_etapa} não encontrada."}
    return alvo


# ---------- SLASH COMMANDS OPCIONAIS ----------

def _executar_modo(ctx, perfil: str, args, extra_ctx: str = ""):
    pedido = " ".join(args) if isinstance(args, list) else str(args or "").strip()
    if not pedido:
        return {"response": "Informe o que deseja fazer após o comando.", "thinking": "Sem argumentos.", "status": "information"}
    if not hasattr(ctx, "ceo") or not ctx.ceo.manager.is_configured:
        return {"response": "⚠️ `GEMINI_API_KEY` não configurada.", "thinking": "API não configurada.", "status": "error"}

    from core.ceo_ai import sanitizar_para_nuvem

    contexto = sanitizar_para_nuvem(
        f"Modo especialista ativo: {perfil}. Projeto atual: {getattr(ctx, 'project_path', '')}. {extra_ctx}".strip()
    )
    if getattr(ctx, "plugin_manager", None):
        contexto = ctx.plugin_manager.run_hooks("pre_cloud", {"texto": contexto}).get("texto", contexto)

    res = ctx.ceo.manager.conversar_com_ferramentas(
        mensagem=f"[{perfil}] {pedido}",
        contexto_extra=contexto,
    )
    acoes = res.get("tools_used") or []
    rodape = ""
    return {
        "response": f"{res['response']}{rodape}",
        "thinking": f"Executado no modo {perfil}.",
        "status": "success",
    }


COMMANDS = {
    "/ti": {
        "handler": lambda ctx, args=None, flags=None: _executar_modo(
            ctx, "TÉCNICO DE TI", args, f"Diagnóstico atual: {json.dumps(diagnostico_ti(), ensure_ascii=False)}"
        ),
        "desc": "Diagnostica sistema, rede, portas, Termux e serviços como Técnico de TI",
        "capability": "read",
    },
    "/dev": {
        "handler": lambda ctx, args=None, flags=None: _executar_modo(ctx, "ENGENHEIRO DE CÓDIGO", args),
        "desc": "Cria, lê e depura códigos em Python, Luau, JS e shell",
        "capability": "read",
    },
    "/jogo": {
        "handler": lambda ctx, args=None, flags=None: _executar_modo(ctx, "CRIADOR DE JOGOS", args),
        "desc": "Cria sistemas, scripts, GDDs e assets usando as ferramentas de jogo do Kael",
        "capability": "read",
    },
    "/tarefa": {
        "handler": lambda ctx, args=None, flags=None: _executar_modo(ctx, "ASSISTENTE MULTIFUNÇÕES", args),
        "desc": "Executa qualquer tarefa geral combinando raciocínio e ferramentas do Kael",
        "capability": "read",
    },
}

GOOGLE_TOOLS = [
    (
        diagnostico_ti,
        {
            "name": "diagnostico_ti",
            "description": "Verifica RAM disponível, espaço em disco, Python, modelos Ollama e portas locais (8000 e 8080).",
            "parameters": {"type": "OBJECT", "properties": {}},
        },
    ),
    (
        listar_arquivos_projeto,
        {
            "name": "listar_arquivos_projeto",
            "description": "Lista arquivos e subpastas dentro de ~/Kael_ia ou ~/Projetos.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "subpasta": {"type": "STRING", "description": "Caminho opcional dentro de ~/Kael_ia ou ~/Projetos."}
                },
            },
        },
    ),
    (
        ler_codigo_projeto,
        {
            "name": "ler_codigo_projeto",
            "description": "Lê arquivos de código ou configuração dentro de ~/Kael_ia ou ~/Projetos.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "caminho": {"type": "STRING", "description": "Caminho relativo a ~/Kael_ia ou absoluto dentro de ~/Kael_ia ou ~/Projetos."}
                },
                "required": ["caminho"],
            },
        },
    ),
    (
        listar_ferramentas_kael,
        {
            "name": "listar_ferramentas_kael",
            "description": "Lista todos os comandos disponíveis no Kael.",
            "parameters": {"type": "OBJECT", "properties": {}},
        },
    ),
    (
        executar_comando_kael,
        {
            "name": "executar_comando_kael",
            "description": "Executa um comando slash interno do Kael (ex: /ver_jogo, /status, /pesquisar_jogos).",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "comando": {"type": "STRING", "description": "Comando slash completo a executar."}
                },
                "required": ["comando"],
            },
        },
    ),
    (
        propor_arquivo,
        {
            "name": "propor_arquivo",
            "description": "Prepara criação ou edição cirúrgica de um arquivo em ~/Kael_ia ou ~/Projetos e devolve prévia para confirmação do usuário.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "caminho": {"type": "STRING", "description": "Caminho dentro de ~/Kael_ia ou ~/Projetos."},
                    "modo": {"type": "STRING", "description": "'criar' (novo/sobrescrever) ou 'editar' (substituir trecho exato)."},
                    "conteudo": {"type": "STRING", "description": "Conteúdo completo quando modo='criar'."},
                    "trecho_antigo": {"type": "STRING", "description": "Trecho exato atual quando modo='editar'."},
                    "trecho_novo": {"type": "STRING", "description": "Novo trecho quando modo='editar'."},
                },
                "required": ["caminho"],
            },
        },
    ),
    (
        propor_comando,
        {
            "name": "propor_comando",
            "description": "Prepara um comando Git ou shell no Termux (em ~/Kael_ia ou ~/Projetos) aguardando confirmação do usuário.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "comando": {"type": "STRING", "description": "Comando Git ou shell a preparar."},
                    "diretorio": {"type": "STRING", "description": "Diretório opcional dentro de ~/Kael_ia ou ~/Projetos."},
                },
                "required": ["comando"],
            },
        },
    ),
    (
        listar_acoes_pendentes,
        {
            "name": "listar_acoes_pendentes",
            "description": "Lista arquivos e comandos preparados que aguardam confirmação do usuário.",
            "parameters": {"type": "OBJECT", "properties": {}},
        },
    ),
    (
        confirmar_acao,
        {
            "name": "confirmar_acao",
            "description": "Executa uma ação pendente pelo ID SOMENTE depois que o usuário confirmar explicitamente na mensagem atual.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "acao_id": {"type": "STRING", "description": "ID numérico da ação pendente."}
                },
                "required": ["acao_id"],
            },
        },
    ),
    (
        cancelar_acao,
        {
            "name": "cancelar_acao",
            "description": "Cancela uma ação pendente pelo ID caso o usuário desista.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "acao_id": {"type": "STRING", "description": "ID numérico da ação pendente."}
                },
                "required": ["acao_id"],
            },
        },
    ),
    (
        pesquisar_web,
        {
            "name": "pesquisar_web",
            "description": "Pesquisa informações atualizadas na internet via Bing (padrão) ou DuckDuckGo.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "consulta": {"type": "STRING", "description": "Termos da busca na internet."},
                    "mecanismo": {"type": "STRING", "description": "'auto' (tenta Bing e depois DuckDuckGo), 'bing' ou 'duckduckgo'."},
                    "limite": {"type": "INTEGER", "description": "Quantidade máxima de resultados (1 a 10)."},
                },
                "required": ["consulta"],
            },
        },
    ),
    (
        ler_pagina_web,
        {
            "name": "ler_pagina_web",
            "description": "Lê o texto de uma página web pública retornada pela pesquisa para obter detalhes completos.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "url": {"type": "STRING", "description": "URL pública http:// ou https://."}
                },
                "required": ["url"],
            },
        },
    ),
    (
        criar_plano_execucao,
        {
            "name": "criar_plano_execucao",
            "description": "Cria um plano em etapas em disco para tarefas multi-etapa mantendo o contexto leve.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "objetivo": {"type": "STRING", "description": "Objetivo geral da tarefa."},
                    "etapas": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Lista ordenada de etapas curtas."},
                },
                "required": ["objetivo", "etapas"],
            },
        },
    ),
    (
        concluir_etapa_plano,
        {
            "name": "concluir_etapa_plano",
            "description": "Marca uma etapa como concluída gravando um resumo curto em disco (e detalhes opcionais fora do contexto principal).",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "num_etapa": {"type": "INTEGER", "description": "Número da etapa concluída."},
                    "resumo_curto": {"type": "STRING", "description": "Resumo objetivo do que foi feito (até ~300 caracteres)."},
                    "detalhes": {"type": "STRING", "description": "Notas técnicas adicionais salvas em disco para consulta eventual."},
                    "arquivos": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Arquivos criados ou alterados."},
                    "plano_id": {"type": "STRING", "description": "ID opcional do plano (usa o plano ativo por padrão)."},
                },
                "required": ["num_etapa", "resumo_curto"],
            },
        },
    ),
    (
        status_plano_execucao,
        {
            "name": "status_plano_execucao",
            "description": "Consulta o progresso e os resumos curtos do plano ativo sem carregar detalhes pesados.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "plano_id": {"type": "STRING", "description": "ID opcional do plano."}
                },
            },
        },
    ),
    (
        ler_etapa_plano,
        {
            "name": "ler_etapa_plano",
            "description": "Lê os detalhes salvos de uma etapa específica quando precisar relembrar algo pontual.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "num_etapa": {"type": "INTEGER", "description": "Número da etapa."},
                    "plano_id": {"type": "STRING", "description": "ID opcional do plano."},
                },
                "required": ["num_etapa"],
            },
        },
    ),
]

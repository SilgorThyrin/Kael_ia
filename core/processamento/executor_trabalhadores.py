import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from roteador_trabalhadores import ordenar_fila_apis


def _carregar_config_apis() -> List[Dict[str, Any]]:
    cfg_path = Path.home() / "Kael_ia" / "config_apis.json"
    if not cfg_path.exists():
        cfg_path = Path("config_apis.json")
    if not cfg_path.exists():
        return []
    try:
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return [x for x in raw if isinstance(x, dict)]
        if isinstance(raw, dict):
            for chave in ("apis", "providers", "items"):
                if isinstance(raw.get(chave), list):
                    return [x for x in raw[chave] if isinstance(x, dict)]
            lista = []
            for k, v in raw.items():
                if isinstance(v, dict):
                    item = dict(v)
                    item.setdefault("id", k)
                    item.setdefault("nome", k)
                    lista.append(item)
            return lista
    except Exception:
        return []
    return []



_BLOQUEADOS_MODELO = (
    "tts", "transcribe", "whisper", "embed", "moderation", "ocr",
    "image", "banana", "lyria", "prompt-guard", "video-detector", "nvclip",
)

def _filtrar_modelos_chat(modelos: list) -> list:
    limpos = []
    for m in modelos:
        ml = m.lower()
        if any(b in ml for b in _BLOQUEADOS_MODELO):
            continue
        if m not in limpos:
            limpos.append(m)
    preferidos = (
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "mistralai/mistral-large-4-1t-a52b",
        "nvidia/nemotron-3.5-lightning-30b-a3b",
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-120b",
    )
    ordenados = [m for m in preferidos if m in limpos] + [m for m in limpos if m not in preferidos]
    return (ordenados or modelos)[:3]

def _extrair_modelos(api: Dict[str, Any]) -> List[str]:
    modelos: List[str] = []
    ativo = str(api.get("modelo_ativo") or api.get("modelo") or api.get("model") or "").strip()
    lista_raw = api.get("modelos") or api.get("models") or []
    if isinstance(lista_raw, list):
        for m in lista_raw:
            if isinstance(m, str) and m.strip():
                modelos.append(m.strip())
            elif isinstance(m, dict):
                mid = str(m.get("id") or m.get("name") or m.get("model") or "").strip()
                if mid:
                    modelos.append(mid)

    modelos = _filtrar_modelos_chat(modelos)
    if ativo and ativo.lower() != "auto":
        return [ativo] + [m for m in modelos if m != ativo]
    return modelos[:6] or ([ativo] if ativo and ativo.lower() != "auto" else [])


def _chamar_gemini_nativo(
    base_url: str,
    api_key: str,
    modelo: str,
    system_prompt: str,
    user_prompt: str,
    timeout: int = 90,
) -> Tuple[bool, str]:
    clean_modelo = modelo.replace("models/", "").strip()
    root = base_url.rstrip("/")
    if "/v1beta" in root:
        idx = root.find("/v1beta") + len("/v1beta")
        endpoint = f"{root[:idx]}/models/{clean_modelo}:generateContent?key={api_key}"
    else:
        endpoint = f"{root}/v1beta/models/{clean_modelo}:generateContent?key={api_key}"

    payload: Dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.35, "maxOutputTokens": 4096},
    }
    if system_prompt.strip():
        payload["systemInstruction"] = {"parts": [{"text": system_prompt.strip()}]}

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "KaelIA/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        candidatos = data.get("candidates") or []
        if not candidatos:
            return False, "sem candidatos"
        partes = ((candidatos[0].get("content") or {}).get("parts")) or []
        texto = "".join(str(p.get("text") or "") for p in partes if isinstance(p, dict)).strip()
        if not texto:
            return False, "resposta vazia"
        return True, texto
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", errors="replace")[:180]
        return False, f"HTTP {e.code}: {corpo}"
    except Exception as exc:
        return False, str(exc)


def _chamar_openai_compativel(
    base_url: str,
    api_key: str,
    modelo: str,
    system_prompt: str,
    user_prompt: str,
    timeout: int = 90,
) -> Tuple[bool, str]:
    root = base_url.rstrip("/")
    if root.endswith("/chat/completions"):
        endpoint = root
    elif root.endswith("/v1") or root.endswith("/openai"):
        endpoint = f"{root}/chat/completions"
    else:
        endpoint = f"{root}/v1/chat/completions"

    mensagens: List[Dict[str, str]] = []
    if system_prompt.strip():
        mensagens.append({"role": "system", "content": system_prompt.strip()})
    mensagens.append({"role": "user", "content": user_prompt})

    payload = {
        "model": modelo,
        "messages": mensagens,
        "temperature": 0.35,
        "max_tokens": 4096,
    }
    headers = {"Content-Type": "application/json", "User-Agent": "KaelIA/1.0"}
    if api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        escolhas = data.get("choices") or []
        if not escolhas:
            return False, "sem choices"
        msg = escolhas[0].get("message") or {}
        texto = str(msg.get("content") or "").strip()
        if not texto:
            return False, "conteudo vazio"
        return True, texto
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", errors="replace")[:180]
        return False, f"HTTP {e.code}: {corpo}"
    except Exception as exc:
        return False, str(exc)


def tentar_executar_trabalhadores(
    prompt_efetivo: str,
    system_prompt: str,
    cb: Callable[[str, str], None],
    contexto_extra: str = "",
) -> bool:
    """
    Retorna True se algum trabalhador externo respondeu com sucesso.
    Retorna False se for dado sensível (fica no local 8080) ou se todos falharem.
    """
    apis = _carregar_config_apis()
    if not apis:
        return False

    plano = ordenar_fila_apis(apis, prompt_efetivo, contexto_extra)
    if plano.get("apenas_local"):
        return False

    fila: List[Dict[str, Any]] = plano.get("fila_externa") or []
    if not fila:
        return False

    categoria = plano.get("categoria", "geral")
    falhas: List[str] = []

    for api in fila:
        nome = str(api.get("nome") or api.get("id") or "API").strip()
        base_url = str(api.get("base_url") or api.get("url") or "").strip()
        api_key = str(api.get("api_key") or api.get("chave") or api.get("key") or "").strip()
        if not base_url:
            continue

        usou_lista_aprovada = False
        modelos = []
        try:
            from lista_modelos_aprovados import obter_modelos_aprovados_provedor, registrar_modelo_valido, remover_modelo_invalido
            modelos = obter_modelos_aprovados_provedor(nome)
            usou_lista_aprovada = bool(modelos)
        except Exception:
            registrar_modelo_valido = lambda *a, **kw: None
            remover_modelo_invalido = lambda *a, **kw: None

        if not modelos:
            usou_lista_aprovada = False
        modelos = []
        try:
            from lista_modelos_aprovados import obter_modelos_aprovados_provedor, registrar_modelo_valido, remover_modelo_invalido
            modelos = obter_modelos_aprovados_provedor(nome)
            usou_lista_aprovada = bool(modelos)
        except Exception:
            registrar_modelo_valido = lambda *a, **kw: None
            remover_modelo_invalido = lambda *a, **kw: None

        if not modelos:
            modelos = _extrair_modelos(api)
        if not modelos:
            modelos = ["gemini-2.5-flash"] if "gemini" in base_url.lower() else ["gpt-4o-mini"]

        usou_nativo_gemini = "generativelanguage.googleapis.com" in base_url.lower() and "/openai" not in base_url.lower()

        for modelo in modelos:
            if usou_nativo_gemini:
                ok, res = _chamar_gemini_nativo(base_url, api_key, modelo, system_prompt, prompt_efetivo)
            else:
                ok, res = _chamar_openai_compativel(base_url, api_key, modelo, system_prompt, prompt_efetivo)

            if ok:
                try:
                    registrar_modelo_valido(nome, modelo)
                except Exception:
                    pass
                try:
                    registrar_modelo_valido(nome, modelo)
                except Exception:
                    pass
                aviso_patch = ""
                try:
                    from auto_evolucao import salvar_patch_se_houver
                    st_patch = salvar_patch_se_houver(res)
                    if st_patch:
                        aviso_patch = f"\n\n> **{st_patch}**"
                except Exception:
                    pass
                cb("content", f"{res}{aviso_patch}\n\n*(Trabalhador: {nome} · Modelo: {modelo} · Rota: {categoria})*")
                return True

            falhas.append(f"{nome}/{modelo}: {res}")
            if usou_lista_aprovada and ("402" in str(res) or "404" in str(res)):
                try:
                    remover_modelo_invalido(nome, modelo)
                except Exception:
                    pass
            if usou_lista_aprovada and ("402" in str(res) or "404" in str(res)):
                try:
                    remover_modelo_invalido(nome, modelo)
                except Exception:
                    pass

    if falhas:
        cb("status", f"\n[Trabalhadores externos indisponíveis ({' | '.join(falhas[-2:])}). Usando Dono Local 8080...]\n")
    return False

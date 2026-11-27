import re
from typing import Any, Dict, List, Tuple

# Termos e arquivos que NUNCA podem sair do ambiente local (porta 8080)
TERMOS_SENSIVEIS = (
    "config_apis.json",
    "api_key",
    "apikey",
    "senha",
    "password",
    "secret",
    "segredo",
    "token",
    ".env",
    "kael_memory.db",
    "credencial",
    "chave privada",
    "modo local",
    "so local",
    "só local",
)

# Ordem preferencial por tipo de tarefa entre os 4 provedores externos
ORDEM_POR_TAREFA: Dict[str, List[str]] = {
    "codigo_pesado": ["groq", "gemini", "nvidia", "mistral"],
    "especialista_codigo": ["nvidia", "gemini", "groq", "mistral"],
    "codigo_rapido": ["groq", "nvidia", "gemini", "mistral"],
    "geral": ["groq", "nvidia", "gemini", "mistral"],
}


def detectar_conteudo_sensivel(prompt: str, contexto_extra: str = "") -> Tuple[bool, str]:
    """Retorna (True, motivo) se o pedido contiver dados privados/restritos."""
    prompt_low = (prompt or "").lower()
    for termo_local in ("modo local", "so local", "só local"):
        if termo_local in prompt_low:
            return True, f"termo_restrito:{termo_local}"

    texto = f"{prompt}\n{contexto_extra}".lower()
    for termo in TERMOS_SENSIVEIS:
        if termo in texto:
            return True, f"termo_restrito:{termo}"

    # Detecta padrões comuns de chaves de API (AIza..., gsk_..., nvapi-..., sk-...)
    if re.search(r"\b(aiza[0-9a-z\-_]{20,}|gsk_[0-9a-z]{20,}|nvapi-[0-9a-z\-_]{20,}|sk-[0-9a-z]{20,})\b", texto):
        return True, "padrao_chave_api"

    return False, "limpo"


def classificar_tarefa(prompt: str) -> str:
    """Classifica o pedido para distribuir entre Gemini, Mistral, Groq e NVIDIA."""
    p = prompt.lower()
    tamanho = len(prompt)

    # 1. Contexto grande ou sistemas Luau completos -> Gemini (fallback NVIDIA/Mistral)
    if tamanho > 900 or any(
        k in p
        for k in (
            "luau",
            "roblox",
            "ecos de aethelgard",
            "ecos_de_aethelgard",
            "mountservice",
            "fasttravelservice",
            "tradeservice",
            "kaelbridgeplugin",
            "arquitetura",
            "sistema completo",
            "varios arquivos",
            "vários arquivos",
        )
    ):
        return "codigo_pesado"

    # 2. Python, JSON, plugins do Kael e refatoração -> Mistral (fallback Gemini/Groq)
    if any(
        k in p
        for k in (
            "python",
            "api_server",
            "plugin",
            "json",
            "refator",
            "flask",
            "fastapi",
            "sqlite",
            "script",
        )
    ):
        return "especialista_codigo"

    # 3. Erros rápidos, syntaxerror, comandos curtos -> Groq (baixa latência)
    if tamanho <= 350 or any(
        k in p
        for k in (
            "erro",
            "syntaxerror",
            "traceback",
            "corrig",
            "patch",
            "comando",
            "termux",
            "git",
            "rapido",
            "rápido",
        )
    ):
        return "codigo_rapido"

    return "geral"


def ordenar_fila_apis(
    apis_ativas: List[Dict[str, Any]], prompt: str, contexto_extra: str = ""
) -> Dict[str, Any]:
    """
    Decide se fica 100% no Dono Local (8080) ou retorna a fila ordenada
    dos 4 trabalhadores externos (Gemini, Groq, Mistral, NVIDIA).
    """
    sensivel, motivo = detectar_conteudo_sensivel(prompt, contexto_extra)
    if sensivel:
        return {
            "apenas_local": True,
            "motivo": motivo,
            "categoria": "cofre_local",
            "fila_externa": [],
        }

    categoria = classificar_tarefa(prompt)
    preferencia = ORDEM_POR_TAREFA.get(categoria, ORDEM_POR_TAREFA["geral"])

    def _score_api(api: Dict[str, Any]) -> Tuple[int, int]:
        ident = f"{api.get('id', '')} {api.get('nome', '')} {api.get('base_url', '')}".lower()
        for idx, provedor in enumerate(preferencia):
            if provedor in ident:
                return (idx, int(api.get("prioridade", 99)))
        return (len(preferencia), int(api.get("prioridade", 99)))

    externas = [
        a
        for a in apis_ativas
        if a.get("ativo", True)
        and "127.0.0.1" not in str(a.get("base_url", ""))
        and "localhost" not in str(a.get("base_url", ""))
    ]
    externas_ordenadas = sorted(externas, key=_score_api)

    return {
        "apenas_local": False,
        "motivo": "delegado_trabalhadores",
        "categoria": categoria,
        "fila_externa": externas_ordenadas,
    }

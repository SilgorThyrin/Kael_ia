import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path.home() / "Kael_ia"
LISTA_FILE = BASE_DIR / "data" / "modelos_aprovados.json"


def carregar_lista_aprovada() -> Dict[str, Any]:
    if not LISTA_FILE.exists():
        return {"atualizado_em": None, "aprovados": {}}
    try:
        data = json.loads(LISTA_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("aprovados"), dict):
            return data
    except Exception:
        pass
    return {"atualizado_em": None, "aprovados": {}}


def salvar_lista_aprovada(aprovados: Dict[str, List[str]]) -> None:
    LISTA_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "atualizado_em": datetime.now().isoformat(),
        "aprovados": aprovados,
    }
    LISTA_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def registrar_modelo_valido(provedor: str, modelo: str) -> None:
    chave = provedor.strip().lower()
    if not chave or not modelo.strip():
        return
    dados = carregar_lista_aprovada()
    aprovados = dados.get("aprovados") or {}
    lista = list(aprovados.get(chave) or [])
    if modelo not in lista:
        lista.append(modelo)
    aprovados[chave] = lista
    salvar_lista_aprovada(aprovados)


def remover_modelo_invalido(provedor: str, modelo: str) -> None:
    chave = provedor.strip().lower()
    dados = carregar_lista_aprovada()
    aprovados = dados.get("aprovados") or {}
    lista = [m for m in (aprovados.get(chave) or []) if m != modelo]
    aprovados[chave] = lista
    salvar_lista_aprovada(aprovados)


def obter_modelos_aprovados_provedor(provedor: str) -> List[str]:
    chave = provedor.strip().lower()
    dados = carregar_lista_aprovada()
    aprovados = dados.get("aprovados") or {}
    lista = aprovados.get(chave) or []
    return [str(m) for m in lista if isinstance(m, str) and m.strip()]


def descobrir_e_salvar_aprovados(forcar: bool = False) -> Dict[str, List[str]]:
    """Testa candidatos rápidos nas APIs externas e salva apenas os que respondem."""
    from executor_trabalhadores import (
        _carregar_config_apis,
        _chamar_gemini_nativo,
        _chamar_openai_compativel,
        _extrair_modelos,
    )

    dados = carregar_lista_aprovada()
    aprovados: Dict[str, List[str]] = dict(dados.get("aprovados") or {})

    for api in _carregar_config_apis():
        if not api.get("ativo", True):
            continue
        nome = str(api.get("nome") or api.get("id") or "").strip()
        chave = nome.lower()
        url = str(api.get("base_url") or api.get("url") or "").strip()
        api_key = str(api.get("api_key") or api.get("chave") or api.get("key") or "").strip()
        if not url or "127.0.0.1" in url or "localhost" in url or not api_key:
            continue

        if not forcar and aprovados.get(chave):
            continue

        candidatos = _extrair_modelos(api)[:5]
        validos: List[str] = []
        usou_gem = "generativelanguage.googleapis.com" in url.lower() and "/openai" not in url.lower()

        for mod in candidatos:
            if usou_gem:
                ok, _ = _chamar_gemini_nativo(url, api_key, mod, "Responda em 1 palavra.", "OK", timeout=15)
            else:
                ok, _ = _chamar_openai_compativel(url, api_key, mod, "Responda em 1 palavra.", "OK", timeout=15)
            if ok and mod not in validos:
                validos.append(mod)

        aprovados[chave] = validos

    salvar_lista_aprovada(aprovados)
    return aprovados


if __name__ == "__main__":
    res = descobrir_e_salvar_aprovados(forcar=True)
    print(json.dumps(res, ensure_ascii=False, indent=2))

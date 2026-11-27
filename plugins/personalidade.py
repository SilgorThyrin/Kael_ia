import json
from pathlib import Path

PLUGIN_INFO = {
    "nome": "Personalidade do Kael",
    "descricao": "Aplica diretrizes de tom e foco do Kael a partir de ~/Kael_ia/personalidade_kael.json."
}

_PADRAO = {
    "nome": "Kael",
    "tom": "direto, tecnico, colaborativo e pragmatico",
    "idioma": "pt-BR",
    "foco_principal": ["desenvolvimento local", "plugins", "Roblox / Luau"],
    "diretrizes": ["Seja objetivo e priorize comandos claros."]
}


def _carregar_perfil() -> dict:
    cfg = Path.home() / "Kael_ia" / "personalidade_kael.json"
    if cfg.exists():
        try:
            dados = json.loads(cfg.read_text(encoding="utf-8"))
            if isinstance(dados, dict):
                return {**_PADRAO, **dados}
        except Exception:
            pass
    return dict(_PADRAO)


def executar(_prompt: str = "") -> str:
    perfil = _carregar_perfil()
    focos = ", ".join(perfil.get("foco_principal") or [])
    regras = " | ".join(perfil.get("diretrizes") or [])
    return (
        f"Perfil ativo ({perfil.get('nome', 'Kael')}): tom={perfil.get('tom')}; "
        f"focos=[{focos}]; regras={regras}"
    )

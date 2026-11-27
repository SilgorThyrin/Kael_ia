import subprocess
from pathlib import Path


def verificar_saude_git() -> dict:
    """Ferramenta real exposta ao Gerente Gemini para checar o repositório Kael_ia."""
    repo = Path.home() / "Kael_ia"
    res = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=5,
    )
    alterados = [l for l in res.stdout.splitlines() if l.strip()]
    return {"arquivos_pendentes": len(alterados), "lista": alterados[:30]}


def cmd_gitcheck(ctx, args=None, flags=None):
    info = verificar_saude_git()
    qtd = info["arquivos_pendentes"]
    lista = "\n".join(f"- `{l}`" for l in info["lista"]) or "Repositório limpo."
    return {
        "response": f"📦 **Status Git ({qtd} pendente(s)):**\n{lista}",
        "thinking": "Verificado via plugin dev-guard.",
        "status": "success",
    }


COMMANDS = {
    "/gitcheck": {
        "handler": cmd_gitcheck,
        "desc": "[Plugin dev-guard] Verifica arquivos pendentes no Git",
        "capability": "read",
    }
}

GOOGLE_TOOLS = [
    (
        verificar_saude_git,
        {
            "name": "verificar_saude_git",
            "description": "Verifica arquivos modificados ou não commitados no repositório Kael_ia.",
            "parameters": {"type": "OBJECT", "properties": {}},
        },
    )
]

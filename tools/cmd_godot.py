"""Authorized headless validation commands for Godot projects."""
from pathlib import Path

from tools.godot_runner import GodotRunner

TOOL_NAME = "godot"


def validar_godot(ctx, args, flags):
    project = Path(ctx.project_path)
    if args:
        project = Path(ctx.projects_root) / args[0]
    runner = GodotRunner(
        ctx.projects_root,
        executable=ctx.config.get("godot_executable"),
    )
    result = runner.validate(project)
    if result["status"] != "success":
        details = result.get("stderr") or result.get("stdout") or result.get("error", "Falha sem detalhes.")
        return {
            "response": f"❌ **Validação Godot falhou**\n\n{details[-4000:]}",
            "thinking": "Verificação headless do projeto Godot.",
            "status": "error",
        }
    return {
        "response": (
            f"✅ **Validação Godot concluída** para `{project.name}` "
            f"(código de saída {result['exit_code']}).\n\n"
            f"{(result.get('stdout') or 'Sem avisos no stdout.')[-3000:]}"
        ),
        "thinking": "Godot foi executado em modo headless com timeout limitado.",
        "status": "success",
    }


COMMANDS = {
    "/validar_godot": {
        "handler": validar_godot,
        "desc": "Executa validação headless do projeto Godot (requer autorização)",
        "capability": "execute",
    }
}

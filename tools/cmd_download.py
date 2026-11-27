"""Approval-gated HTTPS file downloads into the active project."""
from pathlib import Path

from tools.file_download import download_file, validate_download_request


TOOL_NAME = "download"


def _validate(ctx, args, _flags):
    if len(args) != 2:
        raise ValueError("Uso: /baixar_arquivo <URL_HTTPS> <destino-relativo>")
    project_path = getattr(ctx, "project_path", None)
    if project_path is None:
        raise ValueError("Não há projeto ativo para receber o arquivo.")
    policy = getattr(ctx, "permission_policy", None)
    if policy is not None and not policy.is_within_projects_root(project_path):
        raise ValueError("O projeto ativo está fora da pasta de projetos autorizada.")
    validate_download_request(
        args[0],
        args[1],
        project_path,
        resolve_host=False,
    )


def baixar_arquivo(ctx, args, flags):
    _validate(ctx, args, flags)
    project_path = Path(ctx.project_path).resolve()
    result = download_file(args[0], args[1], project_path)
    relative_path = Path(result["path"]).resolve().relative_to(project_path)
    return {
        "status": "success",
        "response": (
            f"Download concluído: `{relative_path.as_posix()}` "
            f"({result['bytes']} bytes). O arquivo não foi executado nem extraído."
        ),
        "thinking": "Arquivo obtido por HTTPS após autorização explícita.",
    }


COMMANDS = {
    "/baixar_arquivo": {
        "handler": baixar_arquivo,
        "validate": _validate,
        "desc": "Baixa arquivo HTTPS de até 50 MiB para o projeto ativo após aprovação",
        "capability": "network",
    },
}

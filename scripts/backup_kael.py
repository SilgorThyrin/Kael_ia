#!/usr/bin/env python
"""Create a source-only Kael archive without local state or private settings."""
import argparse
from datetime import datetime
from pathlib import Path
import zipfile


APP_DIR = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORIES = (
    "ai",
    "api",
    "core",
    "docs",
    "plugins",
    "scripts",
    "tests",
    "tools",
    "ui",
)
ROOT_FILES = (
    ".gitignore",
    "api_server.py",
    "game_architect.py",
    "game_critic.py",
    "game_director.py",
    "game_integrator.py",
    "game_manager.py",
    "kael_assets.py",
    "kael_context.py",
    "kael_core.py",
    "kael_creative.py",
    "kael_engine.py",
    "kael_library.py",
    "kael_loader.py",
    "kael_modules.json",
    "kael_persona.py",
    "kael_system_tools.py",
    "kael_vision.py",
    "kael_websearch.py",
    "refactor_agent.py",
    "requirements.txt",
    "world_builder.py",
)
ALLOWED_SUFFIXES = {
    ".bat", ".css", ".gd", ".gdshader", ".html", ".js", ".json",
    ".lua", ".md", ".py", ".ps1", ".sql", ".toml", ".txt", ".xml", ".yaml", ".yml",
}
EXCLUDED_PARTS = {
    ".git", "__pycache__", "backups", "env", "node_modules", "venv",
}
EXCLUDED_NAMES = {
    ".env",
    "autonomy.local.json",
    "config.json",
    "generation.local.json",
    "kael_memory.db",
    "skills.local.json",
    "ultimas_mensagens.json",
}


def _is_source_file(path):
    if path.name in EXCLUDED_NAMES or path.name.endswith(".pyc") or path.is_symlink():
        return False
    if any(part in EXCLUDED_PARTS for part in path.parts):
        return False
    if path.name != ".gitignore" and path.suffix.lower() not in ALLOWED_SUFFIXES:
        return False
    if path.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".gguf", ".bin"}:
        return False
    if path.suffix.lower() == ".txt" and path.name != "requirements.txt":
        return False
    if ".local." in path.name or path.name.startswith(".generation-"):
        return False
    try:
        return path.is_file() and path.stat().st_size <= 10 * 1024 * 1024
    except OSError:
        return False


def collect_source_files(app_root):
    root = Path(app_root).resolve()
    files = []
    for relative in ROOT_FILES:
        candidate = root / relative
        if _is_source_file(candidate):
            files.append(candidate)
    template = root / "config" / "config.template.json"
    if _is_source_file(template):
        files.append(template)
    for directory in SOURCE_DIRECTORIES:
        source_dir = root / directory
        if source_dir.is_dir():
            files.extend(path for path in source_dir.rglob("*") if _is_source_file(path))
    return sorted(set(files), key=lambda path: str(path.relative_to(root)).lower())


def create_backup(app_root, destination=None):
    root = Path(app_root).resolve()
    destination_dir = (
        Path(destination).expanduser().resolve()
        if destination
        else root.parent / "backups"
    )
    backup_dir = root / "backups"
    if destination_dir == root or (
        root in destination_dir.parents
        and backup_dir != destination_dir
        and backup_dir not in destination_dir.parents
    ):
        raise ValueError("O arquivo de backup dentro da aplicação só pode ficar em backups/.")
    destination_dir.mkdir(parents=True, exist_ok=True)
    archive_path = destination_dir / f"kael-source-{datetime.now():%Y%m%d-%H%M%S-%f}.zip"
    files = collect_source_files(root)
    if not files:
        raise ValueError("Nenhum arquivo de código permitido foi encontrado para o backup.")
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(root).as_posix())
    return archive_path, len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destination",
        help="Pasta local para o arquivo ZIP; por padrão, PortableAI/backups.",
    )
    args = parser.parse_args()
    try:
        archive, file_count = create_backup(APP_DIR, args.destination)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Backup-fonte criado: {archive}")
    print(f"Arquivos incluídos: {file_count}")
    print("Bancos, históricos, projetos, modelos e configuração local foram excluídos.")


if __name__ == "__main__":
    main()

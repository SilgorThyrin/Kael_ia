"""Utilitário de backup do Kael em ~/storage/shared/Documents."""
import os
import tarfile
from datetime import datetime
from pathlib import Path

BASE_DIR = Path.home() / "Kael_ia"
DEST_DIR = Path.home() / "storage" / "shared" / "Documents"

EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "venv",
    ".venv",
}

EXCLUDED_EXTS = {".log", ".pid", ".pyc", ".pyo", ".tmp"}


def _should_exclude(rel_path: Path, is_dir: bool) -> bool:
    for part in rel_path.parts:
        if part in EXCLUDED_DIRS:
            return True
    if not is_dir and rel_path.suffix.lower() in EXCLUDED_EXTS:
        return True
    return False


def criar_backup(source_dir: Path = BASE_DIR, dest_dir: Path = DEST_DIR) -> Path:
    if not source_dir.exists():
        raise FileNotFoundError(f"Diretório de origem não encontrado: {source_dir}")

    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = dest_dir / f"kael_backup_{stamp}.tar.gz"

    with tarfile.open(archive_path, "w:gz") as tar:
        for root, dirs, files in os.walk(source_dir):
            root_path = Path(root)
            rel_root = root_path.relative_to(source_dir)

            # Filtra diretórios excluídos in-place
            dirs[:] = [
                d for d in sorted(dirs)
                if not _should_exclude(rel_root / d, is_dir=True)
            ]

            for fname in sorted(files):
                rel_file = rel_root / fname
                if _should_exclude(rel_file, is_dir=False):
                    continue
                full_file = root_path / fname
                arcname = Path(source_dir.name) / rel_file
                tar.add(full_file, arcname=str(arcname))

    return archive_path


def main():
    out = criar_backup()
    size_kb = out.stat().st_size / 1024
    print(f"✅ Backup criado: {out} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()

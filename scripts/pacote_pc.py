"""Gera pacote .zip limpo do Kael para migração/sincronização no PC (F:\\PortableAI)."""
from datetime import datetime
from pathlib import Path
import zipfile

BASE_DIR = Path.home() / "Kael_ia"
OUT_DIR = Path.home() / "storage" / "shared" / "Documents"

INCLUDE_DIRS = [
    "scripts",
    "Conhecimento",
    "kael_knowledge",
    "data/luau_drafts",
    "plugins/roblox",
]

INCLUDE_FILES = [
    "kael_core.py",
    "kael_engine.py",
    "api_server.py",
    "abrir_kael.bat",
]

EXCLUDE_PARTS = {"__pycache__", ".git"}
EXCLUDE_SUFFIXES = {".pyc", ".log"}


def should_include(path: Path) -> bool:
    if any(part in EXCLUDE_PARTS for part in path.parts):
        return False
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    if path.name.endswith(".bak.lua"):
        return False
    return True


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = OUT_DIR / f"kael_pc_sync_{stamp}.zip"

    count = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel_file in INCLUDE_FILES:
            fp = BASE_DIR / rel_file
            if fp.is_file() and should_include(fp):
                zf.write(fp, arcname=f"Kael_ia/{rel_file}")
                count += 1

        for rel_dir in INCLUDE_DIRS:
            dp = BASE_DIR / rel_dir
            if not dp.is_dir():
                continue
            for fp in sorted(dp.rglob("*")):
                if fp.is_file() and should_include(fp):
                    arc = Path("Kael_ia") / fp.relative_to(BASE_DIR)
                    zf.write(fp, arcname=str(arc))
                    count += 1

    size_kb = zip_path.stat().st_size / 1024
    print(f"✅ Pacote criado: {zip_path}")
    print(f"Arquivos incluídos: {count} | Tamanho: {size_kb:.1f} KB")


if __name__ == "__main__":
    main()

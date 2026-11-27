"""Rotina leve de manutenção: limpa caches/logs e rotaciona backups antigos."""
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path.home() / "Kael_ia"
DOCS_DIR = Path.home() / "storage" / "shared" / "Documents"
KEEP_BACKUPS = 3


def rotate_backups(docs_dir: Path, keep: int = KEEP_BACKUPS) -> int:
    if not docs_dir.exists():
        return 0
    backups = sorted(
        [p for p in docs_dir.iterdir() if p.is_file() and p.name.startswith("kael_backup_") and p.suffix in {".gz", ".zip"}],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    removed = 0
    for old in backups[keep:]:
        try:
            old.unlink()
            removed += 1
        except Exception as e:
            print(f"Falha ao remover backup antigo {old.name}: {e}")
    return removed


def main():
    auditor = BASE_DIR / "scripts" / "auditar_limpeza.py"
    if auditor.is_file():
        subprocess.run([sys.executable, str(auditor), "--perfil", "celular", "--executar"], check=False)

    removed = rotate_backups(DOCS_DIR, KEEP_BACKUPS)
    print(f"Rotação de backups: {removed} arquivo(s) antigo(s) removido(s) (mantidos até {KEEP_BACKUPS}).")


if __name__ == "__main__":
    main()

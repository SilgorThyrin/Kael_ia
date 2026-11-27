"""Resumo rápido de saúde do Kael: disco, portas, banco e lições."""
import json
import shutil
import socket
import sqlite3
from pathlib import Path

BASE_DIR = Path.home() / "Kael_ia"
DOCS_DIR = Path.home() / "storage" / "shared" / "Documents"


def check_port(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.6)
        return s.connect_ex(("127.0.0.1", port)) == 0


def disk_free_gb(path: Path) -> float:
    target = path if path.exists() else Path.home()
    usage = shutil.disk_usage(target)
    return usage.free / (1024 ** 3)


def check_memory_db(db_path: Path) -> str:
    if not db_path.is_file():
        return "ausente"
    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        res = conn.execute("PRAGMA integrity_check;").fetchone()
        conn.close()
        return "ok" if (res and res[0] == "ok") else f"aviso ({res})"
    except Exception as e:
        return f"erro ({e})"


def count_learned_rules(base_dir: Path) -> int:
    rules_file = base_dir / "Conhecimento" / "regras_aprendidas.json"
    if not rules_file.is_file():
        return 0
    try:
        data = json.loads(rules_file.read_text(encoding="utf-8", errors="ignore"))
        return len(data) if isinstance(data, list) else len(data.keys())
    except Exception:
        return 0


def main():
    api_up = check_port(8000)
    llm_up = check_port(8080)
    db_status = check_memory_db(BASE_DIR / "kael_memory.db")
    rules_count = count_learned_rules(BASE_DIR)

    print("=== DIAGNÓSTICO KAEL ===")
    print(f"API (8000):        {'ONLINE' if api_up else 'OFFLINE'}")
    print(f"llama-server (8080): {'ONLINE' if llm_up else 'OFFLINE'}")
    print(f"kael_memory.db:    {db_status}")
    print(f"Regras aprendidas: {rules_count}")
    print(f"Espaço livre (~):  {disk_free_gb(BASE_DIR):.2f} GB")
    if DOCS_DIR.exists():
        print(f"Espaço Docs:       {disk_free_gb(DOCS_DIR):.2f} GB")


if __name__ == "__main__":
    main()

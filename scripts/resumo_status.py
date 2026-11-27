"""Resumo rápido de memória, regras aprendidas, tarefas e saúde do Kael."""
import json
import sqlite3
from pathlib import Path
import diagnostico_kael as diag

BASE_DIR = Path.home() / "Kael_ia"


def _find_rules_file(base_dir: Path):
    candidates = [
        base_dir / "Conhecimento" / "regras_aprendidas.json",
        base_dir / "kael_knowledge" / "regras_aprendidas.json",
        base_dir / "data" / "regras_aprendidas.json",
    ]
    for p in candidates:
        if p.is_file():
            return p
    found = list(base_dir.rglob("regras_aprendidas.json"))
    return found[0] if found else None


def _read_rules(base_dir: Path):
    f = _find_rules_file(base_dir)
    if not f:
        return 0, []
    try:
        raw = json.loads(f.read_text(encoding="utf-8", errors="ignore"))
        if isinstance(raw, list):
            items = [str(x.get("regra") or x.get("lesson") or x) if isinstance(x, dict) else str(x) for x in raw]
            return len(items), items[-3:]
        if isinstance(raw, dict):
            items = [f"{k}: {v}" for k, v in list(raw.items())[-3:]]
            return len(raw), items
    except Exception:
        pass
    return 0, []


def _read_tasks(base_dir: Path):
    # Tenta localizar banco de tarefas autônomas se existir
    for candidate in (base_dir / "data" / "autonomous_tasks.db", base_dir / "autonomous_tasks.db", base_dir / "kael_memory.db"):
        if not candidate.is_file():
            continue
        try:
            conn = sqlite3.connect(str(candidate), timeout=4)
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "tasks" in tables:
                rows = conn.execute("SELECT id, status, description FROM tasks ORDER BY id DESC LIMIT 5").fetchall()
                conn.close()
                return rows
            conn.close()
        except Exception:
            pass
    return []


def main():
    api_up = diag.check_port(8000)
    llm_up = diag.check_port(8080)
    db_status = diag.check_memory_db(BASE_DIR / "kael_memory.db")
    rules_count, recent_rules = _read_rules(BASE_DIR)
    tasks = _read_tasks(BASE_DIR)

    print("=== RESUMO DE STATUS — KAEL ===")
    print(f"Serviços: API(8000)={'ON' if api_up else 'OFF'} | LLM(8080)={'ON' if llm_up else 'OFF'}")
    print(f"Memória (kael_memory.db): {db_status} | Livre: {diag.disk_free_gb(BASE_DIR):.2f} GB")
    print(f"Regras aprendidas: {rules_count}")
    for r in recent_rules:
        print(f"  - {r[:110]}")

    if tasks:
        print("Últimas tarefas:")
        for tid, st, desc in tasks:
            print(f"  - #{tid} [{st}] {str(desc)[:80]}")
    else:
        print("Últimas tarefas: sem tabela 'tasks' em kael_memory.db (apenas 'memories').")


if __name__ == "__main__":
    main()

"""Diagnóstico (dry-run), checagem de integridade e limpeza segura por perfil."""
import argparse
import os
import sqlite3
from pathlib import Path

JUNK_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "cache", "Cache", "tmp", "temp"}
JUNK_EXTS = {".log", ".tmp", ".bak", ".old", ".pyc", ".pyo"}
PROTECTED_NAMES = {".env", "kael_memory.db", ".git", "regras_aprendidas.json", "regras_pensamento.md", "sistema_nao_apagar.md"}


def _load_protected_terms(base_dir: Path) -> list[str]:
    terms = []
    rule_file = base_dir / "kael_knowledge" / "sistema_nao_apagar.md"
    if rule_file.is_file():
        for line in rule_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = line.strip().lstrip("-*# ").strip("`")
            if (len(s) >= 3 and "/" in s) or s.endswith((".db", ".env", ".json", ".gguf")):
                terms.append(s)
    return terms


def _is_protected(path: Path, protected_terms: list[str]) -> bool:
    if path.name in PROTECTED_NAMES:
        return True
    p_str = str(path)
    return any(term in p_str for term in protected_terms)


def check_integrity(base_dir: Path) -> bool:
    """Verifica integridade básica dos arquivos críticos antes de limpar."""
    ok = True
    db_path = base_dir / "kael_memory.db"
    if db_path.is_file():
        try:
            conn = sqlite3.connect(str(db_path))
            res = conn.execute("PRAGMA integrity_check;").fetchone()
            conn.close()
            if not res or res[0] != "ok":
                print(f"[INTEGRIDADE] Aviso em {db_path}: {res}")
                ok = False
        except Exception as e:
            print(f"[INTEGRIDADE] Erro ao checar {db_path}: {e}")
            ok = False
    return ok


def scan_target(target: Path, protected_terms: list[str], min_mb: float = 100.0):
    findings = []
    if not target.exists():
        return findings

    for root, dirs, files in os.walk(target):
        root_path = Path(root)
        if _is_protected(root_path, protected_terms):
            dirs[:] = []
            continue

        kept_dirs = []
        for d in sorted(dirs):
            d_path = root_path / d
            if _is_protected(d_path, protected_terms):
                continue
            if d in JUNK_DIRS:
                size_bytes = sum(f.stat().st_size for f in d_path.rglob("*") if f.is_file())
                findings.append(("DIR_CACHE", d_path, size_bytes))
            else:
                kept_dirs.append(d)
        dirs[:] = kept_dirs

        for fname in sorted(files):
            fpath = root_path / fname
            if _is_protected(fpath, protected_terms) or not fpath.is_file():
                continue
            try:
                size = fpath.stat().st_size
            except OSError:
                continue

            if fpath.suffix.lower() in JUNK_EXTS and size >= 1024:
                findings.append(("ARQ_TEMP_LOG", fpath, size))
            elif size >= min_mb * 1024 * 1024:
                findings.append(("ARQ_GRANDE", fpath, size))

    return findings


def _targets_for_profile(profile: str, base_dir: Path) -> list[Path]:
    if profile == "celular":
        return [
            base_dir,
            Path.home() / "storage" / "shared" / "Download",
            Path.home() / "storage" / "shared" / "Documents",
        ]
    if profile == "pc":
        return [
            Path("C:/PortableAI"),
            Path.home() / "Downloads",
            Path.home() / "AppData" / "Local" / "Temp",
        ]
    if profile == "usb":
        return [Path("F:/PortableAI"), Path("/mnt/usb"), Path("/storage")]
    return [base_dir, Path.home() / "storage" / "shared" / "Download"]


def main():
    parser = argparse.ArgumentParser(description="Auditoria e limpeza segura de arquivos.")
    parser.add_argument("--perfil", choices=["celular", "pc", "usb"], default="celular", help="Perfil de dispositivo.")
    parser.add_argument("--alvo", action="append", dest="alvos", help="Caminho customizado (pode repetir).")
    parser.add_argument("--min-mb", type=float, default=100.0, help="Limite (MB) para sinalizar arquivo grande.")
    parser.add_argument("--executar", action="store_true", help="Apaga apenas DIR_CACHE e ARQ_TEMP_LOG (nunca ARQ_GRANDE).")
    args = parser.parse_args()

    base_dir = Path.home() / "Kael_ia"
    if not check_integrity(base_dir):
        print("Checagem de integridade apontou aviso. Abortando execução por segurança.")
        return

    protected_terms = _load_protected_terms(base_dir)
    targets = [Path(p).expanduser() for p in args.alvos] if args.alvos else _targets_for_profile(args.perfil, base_dir)

    all_items = []
    for t in targets:
        all_items.extend(scan_target(t, protected_terms, min_mb=args.min_mb))

    if not all_items:
        print(f"Nenhum item candidato encontrado para o perfil '{args.perfil}'.")
        return

    total_bytes = sum(size for _, _, size in all_items)
    for kind, path, size in all_items:
        print(f"[{kind}] {path} ({size / (1024 * 1024):.2f} MB)")

    print(f"\nTotal identificado: {total_bytes / (1024 * 1024):.2f} MB ({len(all_items)} itens)")

    if not args.executar:
        print("Modo diagnóstico (nada foi apagado). Para limpar caches/temp/logs, rode com --executar.")
        return

    freed = 0
    for kind, path, size in all_items:
        if kind == "ARQ_GRANDE" or _is_protected(path, protected_terms):
            continue
        try:
            if kind == "DIR_CACHE" and path.is_dir():
                for child in sorted(path.rglob("*"), reverse=True):
                    if child.is_file():
                        child.unlink(missing_ok=True)
                    elif child.is_dir():
                        child.rmdir()
                path.rmdir()
                freed += size
            elif path.is_file():
                path.unlink(missing_ok=True)
                freed += size
        except Exception as exc:
            print(f"Falha ao remover {path}: {exc}")

    print(f"Limpeza concluída. Espaço liberado: {freed / (1024 * 1024):.2f} MB.")


if __name__ == "__main__":
    main()

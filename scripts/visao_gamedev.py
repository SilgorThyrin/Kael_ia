"""Coleta contexto estruturado de projeto (Roblox/Luau, Godot, Web) para o Kael."""
import argparse
import json
import os
from pathlib import Path

BASE_DIR = Path.home() / "Kael_ia"
ROBLOX_PLACE_ID = "105458200861912"

IGNORE_DIRS = {"__pycache__", ".git", ".godot", "node_modules", ".venv", "venv"}


def _ler_trecho(path: Path, max_chars: int = 1800) -> str:
    try:
        txt = path.read_text(encoding="utf-8", errors="replace")
        if len(txt) > max_chars:
            return txt[:max_chars] + "\n... [truncado] ..."
        return txt
    except Exception as e:
        return f"[erro ao ler: {e}]"


def inspecionar_roblox(alvo: Path) -> dict:
    drafts = BASE_DIR / "data" / "luau_drafts"
    raiz = alvo if alvo.exists() else drafts
    scripts_lua = []
    if raiz.is_dir():
        for root, dirs, files in os.walk(raiz):
            dirs[:] = sorted([d for d in dirs if d not in IGNORE_DIRS])
            for fn in sorted(files):
                if fn.lower().endswith((".lua", ".luau")):
                    fp = Path(root) / fn
                    scripts_lua.append({
                        "arquivo": str(fp.relative_to(raiz)),
                        "bytes": fp.stat().st_size,
                        "amostra": _ler_trecho(fp, 1200),
                    })
    return {
        "engine": "roblox_studio",
        "projeto": "Ecos de Aethelgard",
        "place_id": ROBLOX_PLACE_ID,
        "caminho_inspecionado": str(raiz),
        "total_scripts_luau": len(scripts_lua),
        "scripts": scripts_lua[:12],
    }


def inspecionar_godot(alvo: Path) -> dict:
    project_file = alvo / "project.godot" if alvo.is_dir() else None
    cenas, scripts_gd = [], []
    if alvo.is_dir():
        for root, dirs, files in os.walk(alvo):
            dirs[:] = sorted([d for d in dirs if d not in IGNORE_DIRS])
            for fn in sorted(files):
                fp = Path(root) / fn
                rel = str(fp.relative_to(alvo))
                if fn.endswith(".tscn") and len(cenas) < 25:
                    cenas.append({"cena": rel, "amostra": _ler_trecho(fp, 900)})
                elif fn.endswith(".gd") and len(scripts_gd) < 12:
                    scripts_gd.append({"script": rel, "amostra": _ler_trecho(fp, 1200)})
    return {
        "engine": "godot",
        "caminho_inspecionado": str(alvo),
        "tem_project_godot": bool(project_file and project_file.is_file()),
        "project_godot_resumo": _ler_trecho(project_file, 1000) if project_file and project_file.is_file() else "",
        "cenas": cenas,
        "scripts_gd": scripts_gd,
    }


def inspecionar_web(alvo: Path) -> dict:
    exts = {".html", ".htm", ".css", ".js", ".mjs", ".ts", ".json"}
    arquivos = []
    if alvo.is_dir():
        for root, dirs, files in os.walk(alvo):
            dirs[:] = sorted([d for d in dirs if d not in IGNORE_DIRS])
            for fn in sorted(files):
                fp = Path(root) / fn
                if fp.suffix.lower() in exts and len(arquivos) < 15:
                    arquivos.append({
                        "arquivo": str(fp.relative_to(alvo)),
                        "amostra": _ler_trecho(fp, 1200),
                    })
    return {
        "engine": "web",
        "caminho_inspecionado": str(alvo),
        "arquivos": arquivos,
    }


def detectar_e_inspecionar(alvo: Path, engine: str = "auto") -> dict:
    alvo = alvo.expanduser()
    if not alvo.is_absolute():
        alvo = BASE_DIR / alvo

    modo = engine.lower()
    if modo == "auto":
        if (alvo / "project.godot").is_file() or any(alvo.rglob("*.gd")):
            modo = "godot"
        elif any(alvo.rglob("*.lua")) or any(alvo.rglob("*.luau")) or "luau" in str(alvo).lower():
            modo = "roblox"
        else:
            modo = "web"

    if modo in ("roblox", "luau", "studio"):
        return inspecionar_roblox(alvo)
    if modo == "godot":
        return inspecionar_godot(alvo)
    return inspecionar_web(alvo)


def main():
    parser = argparse.ArgumentParser(description="Inspeciona projeto de jogo para o Kael.")
    parser.add_argument("caminho", nargs="?", default="data/luau_drafts", help="Pasta do projeto ou rascunhos.")
    parser.add_argument("--engine", choices=["auto", "roblox", "godot", "web"], default="auto")
    parser.add_argument("--json", action="store_true", help="Saída em JSON puro.")
    args = parser.parse_args()

    dados = detectar_e_inspecionar(Path(args.caminho), args.engine)
    if args.json:
        print(json.dumps(dados, ensure_ascii=False, indent=2))
        return

    print(f"=== VISÃO GAMEDEV [{dados['engine'].upper()}] ===")
    print(f"Caminho: {dados['caminho_inspecionado']}")
    if dados["engine"] == "roblox_studio":
        print(f"Projeto: {dados['projeto']} (PlaceId: {dados['place_id']})")
        print(f"Scripts Luau encontrados: {dados['total_scripts_luau']}")
        for s in dados["scripts"]:
            print(f"  - {s['arquivo']} ({s['bytes']} bytes)")
    elif dados["engine"] == "godot":
        print(f"project.godot presente: {'sim' if dados['tem_project_godot'] else 'não'}")
        print(f"Cenas (.tscn): {len(dados['cenas'])} | Scripts (.gd): {len(dados['scripts_gd'])}")
        for c in dados["cenas"][:8]:
            print(f"  - Cena: {c['cena']}")
        for g in dados["scripts_gd"][:8]:
            print(f"  - Script: {g['script']}")
    else:
        print(f"Arquivos web inspecionados: {len(dados['arquivos'])}")
        for a in dados["arquivos"]:
            print(f"  - {a['arquivo']}")


if __name__ == "__main__":
    main()

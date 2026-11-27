#!/usr/bin/env python3
"""Ambiente central de validação de códigos do Kael (Python, HTML/JS, Luau e API)."""
import argparse
import json
import py_compile
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

BASE_DIR = Path.home() / "Kael_ia"
SANDBOX_DIR = BASE_DIR / "sandbox_testes"
DATA_DIR = BASE_DIR / "data"
RELATORIO_PATH = DATA_DIR / "ultimo_teste_kael.json"
ECOS_DIR = Path.home() / "Projetos" / "Ecos_de_Aethelgard"


def testar_python_arquivo(path: Path) -> dict:
    try:
        py_compile.compile(str(path), doraise=True)
        return {"arquivo": str(path), "tipo": "python", "ok": True, "erro": None}
    except py_compile.PyCompileError as exc:
        return {"arquivo": str(path), "tipo": "python", "ok": False, "erro": str(exc)}


def testar_json_arquivo(path: Path) -> dict:
    try:
        json.loads(path.read_text(encoding="utf-8"))
        return {"arquivo": str(path), "tipo": "json", "ok": True, "erro": None}
    except Exception as exc:
        return {"arquivo": str(path), "tipo": "json", "ok": False, "erro": str(exc)}


def testar_html_js(path: Path) -> dict:
    src = path.read_text(encoding="utf-8")
    problemas = []
    for m in re.finditer(r"<script(?![^>]*src=)[^>]*>(.*?)</script>", src, re.S | re.I):
        js = m.group(1)
        linhas_limpas = []
        for linha in js.splitlines():
            sem_barra = linha.split("//", 1)[0]
            linhas_limpas.append(sem_barra)
        limpo = chr(10).join(linhas_limpas)
        for aberto, fechado in (("(", ")"), ("{", "}"), ("[", "]")):
            diff = limpo.count(aberto) - limpo.count(fechado)
            if diff != 0:
                problemas.append(f"Desbalanceamento de {aberto}{fechado}: diff={diff}")
    return {
        "arquivo": str(path),
        "tipo": "html_js",
        "ok": len(problemas) == 0,
        "erro": "; ".join(problemas) if problemas else None,
    }


def testar_luau_arquivo(path: Path) -> dict:
    validador = BASE_DIR / "scripts" / "validar_luau.py"
    if validador.is_file():
        proc = subprocess.run(
            [sys.executable, str(validador), str(path)],
            capture_output=True,
            text=True,
            timeout=20,
        )
        saida = (proc.stdout + "\n" + proc.stderr).strip()
        return {
            "arquivo": str(path),
            "tipo": "luau",
            "ok": proc.returncode == 0,
            "erro": None if proc.returncode == 0 else saida[:600],
            "detalhe": saida[:600],
        }
    src = path.read_text(encoding="utf-8")
    opens = len(re.findall(r"\b(function|if|for|while|repeat)\b", src))
    ends = len(re.findall(r"\bend\b", src))
    ok = abs(opens - ends) <= 2
    return {
        "arquivo": str(path),
        "tipo": "luau",
        "ok": ok,
        "erro": None if ok else f"Aberturas={opens} vs end={ends}",
    }


def testar_rotas_api(base_url: str = "http://127.0.0.1:8000") -> list[dict]:
    rotas = [
        ("/health", "GET"),
        ("/kael-perm/pending", "GET"),
        ("/chat/historico?limit=5", "GET"),
    ]
    resultados = []
    for rota, metodo in rotas:
        url = base_url + rota
        try:
            req = urllib.request.Request(url, method=metodo)
            with urllib.request.urlopen(req, timeout=4) as resp:
                resultados.append({
                    "rota": rota,
                    "status": resp.status,
                    "ok": 200 <= resp.status < 300,
                })
        except urllib.error.HTTPError as exc:
            resultados.append({
                "rota": rota,
                "status": exc.code,
                "ok": False,
                "erro": f"HTTP {exc.code}",
            })
        except Exception as exc:
            resultados.append({
                "rota": rota,
                "status": None,
                "ok": False,
                "erro": str(exc),
            })
    return resultados


def validar_arquivo_candidato(alvo_str: str) -> dict:
    p = Path(alvo_str)
    if not p.is_absolute():
        if (SANDBOX_DIR / p).exists():
            p = SANDBOX_DIR / p
        elif (BASE_DIR / p).exists():
            p = BASE_DIR / p
    if not p.exists():
        return {"arquivo": alvo_str, "ok": False, "erro": "Arquivo não encontrado."}
    ext = p.suffix.lower()
    if ext == ".py":
        return testar_python_arquivo(p)
    if ext == ".json":
        return testar_json_arquivo(p)
    if ext in (".html", ".htm"):
        return testar_html_js(p)
    if ext == ".lua":
        return testar_luau_arquivo(p)
    return {"arquivo": str(p), "tipo": ext or "desconhecido", "ok": True, "erro": None}


def main():
    parser = argparse.ArgumentParser(description="Executa bateria de testes do Kael.")
    parser.add_argument("--arquivo", help="Valida um arquivo específico novo ou candidato.")
    parser.add_argument("--sem-api", action="store_true", help="Pula checagem HTTP na porta 8000.")
    args = parser.parse_args()

    checks = []
    for rel in ["api_server.py", "kael_app.py", "scripts/permissoes_kael.py"]:
        arq = BASE_DIR / rel
        if arq.is_file():
            checks.append(testar_python_arquivo(arq))

    tpl = BASE_DIR / "templates" / "kael_chat.html"
    if tpl.is_file():
        checks.append(testar_html_js(tpl))

    for jrel in ["data/permissoes_kael.json", "data/chat_historico.json", "data/modelos_aprovados.json"]:
        jarq = BASE_DIR / jrel
        if jarq.is_file():
            checks.append(testar_json_arquivo(jarq))

    if args.arquivo:
        checks.append(validar_arquivo_candidato(args.arquivo))

    api_checks = [] if args.sem_api else testar_rotas_api()

    todos_ok = all(c.get("ok") for c in checks) and all(a.get("ok") for a in api_checks)
    relatorio = {
        "executado_em": datetime.now().isoformat(timespec="seconds"),
        "aprovado": todos_ok,
        "arquivos": checks,
        "api": api_checks,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RELATORIO_PATH.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"=== RELATÓRIO DE TESTES KAEL ({relatorio['executado_em']}) ===")
    for c in checks:
        status = "OK" if c["ok"] else "FALHA"
        print(f"[{status}] ({c.get('tipo')}) {c['arquivo']}" + (f" -> {c['erro']}" if c.get("erro") else ""))
    if api_checks:
        print("--- API (127.0.0.1:8000) ---")
        for a in api_checks:
            st = "OK" if a["ok"] else "FALHA"
            print(f"[{st}] {a['rota']} -> status={a.get('status')} {a.get('erro') or ''}")
    print(f"RESULTADO FINAL: {'APROVADO' if todos_ok else 'REPROVADO (CORRIGIR ANTES DE APLICAR)'}")
    sys.exit(0 if todos_ok else 1)


if __name__ == "__main__":
    main()

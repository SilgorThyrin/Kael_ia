#!/usr/bin/env python
"""Read-only-ish diagnostics for the portable Kael installation."""
import importlib.util
import socket
import sys
import tempfile
import argparse
from pathlib import Path
from urllib.parse import urlparse


APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from core.configuration import load_config


def report(level, message):
    print(f"[{level}] {message}")


def port_open(host, port):
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def check_write_access(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=".kael-write-check-",
        dir=path,
        delete=False,
    ) as file:
        test_file = Path(file.name)
    test_file.unlink()


def api_url(host, port):
    display_host = f"[{host}]" if ":" in host else host
    return f"http://{display_host}:{port}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-runtime", action="store_true")
    args = parser.parse_args()
    if args.print_runtime:
        config = load_config(base_dir=APP_DIR)
        print(f"{config['api_host']}|{config['api_port']}|{config['ollama_url']}")
        return 0

    failed = False
    report("INFO", f"Python {sys.version.split()[0]} · aplicação em {APP_DIR}")
    try:
        config = load_config(base_dir=APP_DIR)
    except ValueError as exc:
        report("ERRO", str(exc))
        return 1
    if sys.version_info < (3, 10):
        report("ERRO", "O Kael requer Python 3.10 ou superior.")
        failed = True

    required_modules = {
        "flask": "Flask",
        "flask_cors": "Flask-CORS",
        "requests": "requests",
    }
    optional_modules = {
        "customtkinter": "CustomTkinter (companion opcional)",
        "duckduckgo_search": "DuckDuckGo Search",
        "sentence_transformers": "Sentence Transformers (memória vetorial opcional)",
        "ollama": "cliente Python Ollama (opcional)",
    }
    for module, label in required_modules.items():
        if importlib.util.find_spec(module) is None:
            report("ERRO", f"Dependência obrigatória ausente: {label}")
            failed = True
        else:
            report("OK", f"Dependência: {label}")
    for module, label in optional_modules.items():
        report(
            "OK" if importlib.util.find_spec(module) else "AVISO",
            f"Dependência opcional: {label}"
            if importlib.util.find_spec(module)
            else f"Dependência opcional ausente: {label}",
        )

    ollama = urlparse(config["ollama_url"])
    ollama_host = ollama.hostname or "127.0.0.1"
    ollama_port = ollama.port or (443 if ollama.scheme == "https" else 80)
    api_host = config["api_host"]
    api_port = config["api_port"]

    if importlib.util.find_spec("requests") is not None:
        import requests

        try:
            response = requests.get(f"{config['ollama_url']}/api/tags", timeout=3)
            response.raise_for_status()
            payload = response.json()
            models = payload.get("models", []) if isinstance(payload, dict) else []
            model_names = [
                item["name"] for item in models
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            ]
            report("OK", f"Ollama responde em {ollama_host}:{ollama_port}.")
            if config["model_name"] in model_names:
                report("OK", f"Modelo configurado disponível: {config['model_name']}")
            else:
                report("AVISO", f"Modelo configurado não encontrado: {config['model_name']}")
                report("INFO", "Modelos instalados: " + (", ".join(model_names) or "(nenhum)"))
        except (requests.RequestException, ValueError) as exc:
            report("AVISO", f"Ollama indisponível em {ollama_host}:{ollama_port}: {exc}")
    else:
        report("AVISO", "Não foi possível testar Ollama sem a dependência requests.")

    if port_open(api_host, api_port):
        if importlib.util.find_spec("requests") is not None:
            try:
                response = requests.get(f"{api_url(api_host, api_port)}/health", timeout=2)
                if response.ok:
                    report("OK", f"API Kael responde na porta {api_port}.")
                else:
                    report("ERRO", f"A porta {api_port} está ocupada por serviço incompatível.")
                    failed = True
            except requests.RequestException as exc:
                report("ERRO", f"A porta {api_port} está ocupada, mas a API não responde: {exc}")
                failed = True
        else:
            report("AVISO", f"A porta configurada para API ({api_port}) está em uso.")
    else:
        report("AVISO", f"API ainda não está iniciada na porta {api_port}.")

    for label, path in (
        ("configuração local", APP_DIR / "config"),
        ("memória", config["memory_dir"]),
        ("projetos", config["projects_root"]),
    ):
        try:
            check_write_access(path)
            report("OK", f"Leitura/escrita permitida: {path}")
        except OSError as exc:
            report("ERRO", f"Sem acesso de escrita à pasta de {label} ({path}): {exc}")
            failed = True

    report("INFO", f"Projeto atual: {config['project_path']}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

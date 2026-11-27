"""Inicializador único do Kael: prepara ambiente, sobe llama-server (8080) e api_server (8000)."""
import argparse
import importlib.util
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REQUIRED_MODULES = {
    "flask": "flask",
    "flask_cors": "flask-cors",
    "requests": "requests",
}

MODEL_CANDIDATES = [
    Path.home() / "storage" / "shared" / "Documents" / "Modelos_GGUF" / "qwen2.5-1.5b-instruct-q4_k_m.gguf",
    BASE_DIR / "models" / "qwen2.5-1.5b-instruct-q4_k_m.gguf",
    Path("F:/PortableAI/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"),
    Path("C:/PortableAI/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"),
]


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def ensure_dirs():
    for rel in ("Conhecimento", "kael_knowledge", "data", "data/luau_drafts", "scripts"):
        (BASE_DIR / rel).mkdir(parents=True, exist_ok=True)


def ensure_python_packages(install_missing: bool = True):
    missing = [pip_name for mod, pip_name in REQUIRED_MODULES.items() if importlib.util.find_spec(mod) is None]
    if not missing:
        print("[PREP] Dependências Python essenciais já instaladas.")
        return
    print(f"[PREP] Dependências ausentes: {', '.join(missing)}")
    if not install_missing:
        return
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", *missing], check=False)


def find_llama_binary() -> str | None:
    for name in ("llama-server", "llama-server.exe"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in (
        Path("F:/PortableAI/llama.cpp/llama-server.exe"),
        Path("C:/PortableAI/llama.cpp/llama-server.exe"),
        Path.home() / "llama.cpp" / "build" / "bin" / "llama-server",
    ):
        if candidate.is_file():
            return str(candidate)
    return None


def find_gguf_model() -> str | None:
    for p in MODEL_CANDIDATES:
        if p.is_file():
            return str(p)
    return None


def start_llama_if_needed(llm_port: int = 8080, ctx_size: int = 2048):
    if port_open(llm_port):
        print(f"[LLM] llama-server já ativo na porta {llm_port}.")
        return

    binary = find_llama_binary()
    model = find_gguf_model()
    if not binary or not model:
        print(f"[AVISO] llama-server ({binary}) ou modelo GGUF ({model}) não encontrado. Pulando subida local.")
        return

    log_file = BASE_DIR / "data" / "llama_server.log"
    print(f"[LLM] Iniciando llama-server na porta {llm_port}...")
    cmd = [
        binary,
        "-m", model,
        "--host", "127.0.0.1",
        "--port", str(llm_port),
        "-c", str(ctx_size),
        "-b", "256",
        "-ub", "128",
        "-t", "4",
        "-ctk", "q8_0",
        "-ctv", "q8_0",
        "--parallel", "1",
    ]
    with open(log_file, "a", encoding="utf-8") as lf:
        subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            stdin=subprocess.DEVNULL,
            stdout=lf,
            stderr=lf,
            start_new_session=True,
        )
    time.sleep(2)


def start_api_if_needed(api_port: int = 8000):
    if port_open(api_port):
        print(f"[KAEL] API já ativa na porta {api_port}.")
        return

    api_server = BASE_DIR / "api_server.py"
    if not api_server.is_file():
        print("[AVISO] api_server.py não encontrado na raiz de ~/Kael_ia.")
        return

    log_file = BASE_DIR / "data" / "kael_server.log"
    print(f"[KAEL] Iniciando api_server.py na porta {api_port}...")
    with open(log_file, "a", encoding="utf-8") as lf:
        subprocess.Popen(
            [sys.executable, str(api_server)],
            cwd=str(BASE_DIR),
            stdout=lf,
            stderr=lf,
            start_new_session=True,
        )


def main():
    parser = argparse.ArgumentParser(description="Prepara ambiente e inicia Kael com llama.cpp.")
    parser.add_argument("--no-install", action="store_true", help="Não instala pacotes Python faltantes.")
    parser.add_argument("--prepare-only", action="store_true", help="Apenas prepara pastas e dependências.")
    parser.add_argument("--port", type=int, default=8000, help="Porta da API do Kael (padrão: 8000).")
    parser.add_argument("--llm-port", type=int, default=8080, help="Porta do llama-server (padrão: 8080).")
    args = parser.parse_args()

    ensure_dirs()
    ensure_python_packages(install_missing=not args.no_install)

    if not args.prepare_only:
        start_llama_if_needed(llm_port=args.llm_port)
        start_api_if_needed(api_port=args.port)


if __name__ == "__main__":
    main()

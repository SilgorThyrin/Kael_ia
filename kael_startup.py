"""
KAEL STARTUP LAUNCHER
C:\PortableAI\kael_startup.py
Orquestra: Ollama -> Modelo -> API Server -> UI
"""
import os
import sys
import time
import socket
import subprocess
import logging
from pathlib import Path

# --- Caminhos base (portátil) ---
ROOT = Path(__file__).resolve().parent
OLLAMA_EXE = ROOT / "Ollama" / "ollama.exe"
KAEL_DIR = ROOT / "kael"
PYTHON_EXE = ROOT / "python" / "python.exe"
LOG_FILE = ROOT / "kael_startup.log"

# --- Config ---
OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 8080
KAEL_API_PORT = 8000
MODEL = "qwen3:8b"
VRAM_LIMIT_MB = 5800  # margem p/ GTX 1060 6GB

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("kael_startup")


def is_port_open(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0


def start_ollama():
    if is_port_open(OLLAMA_HOST, OLLAMA_PORT):
        log.info("Ollama já está rodando.")
        return True
    if not OLLAMA_EXE.exists():
        log.error(f"Ollama não encontrado em {OLLAMA_EXE}")
        return False
    log.info("Iniciando Ollama...")
    # subprocess SEM shell=True (regra de segurança)
    subprocess.Popen(
        [str(OLLAMA_EXE), "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    # espera a porta subir
    for _ in range(15):
        if is_port_open(OLLAMA_HOST, OLLAMA_PORT):
            log.info("Ollama online.")
            return True
        time.sleep(1)
    log.error("Timeout ao iniciar Ollama.")
    return False


def load_model():
    log.info(f"Carregando modelo {MODEL}...")
    try:
        result = subprocess.run(
            [str(OLLAMA_EXE), "run", MODEL, "--keep_alive", "5m"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=120,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            log.error(
                f"Falha ao carregar modelo (codigo {result.returncode}): "
                f"{result.stderr or 'erro desconhecido'}"
            )
            return False
        log.info("Modelo carregado.")
        return True
    except subprocess.TimeoutExpired:
        log.error("Timeout ao carregar o modelo.")
        return False
    except Exception as e:
        log.error(f"Falha ao carregar modelo: {e}")
        return False


def check_vram():
    """Libera modelo se VRAM crítica (Smart Sleep defensivo)."""
    try:
        import pynvml
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(h)
        used_mb = info.used // (1024 * 1024)
        log.info(f"VRAM usada: {used_mb} MB")
        if used_mb > VRAM_LIMIT_MB:
            log.warning("VRAM crítica -> descarregando modelo.")
            subprocess.run([str(OLLAMA_EXE), "stop", MODEL], timeout=10)
    except Exception as e:
        log.debug(f"pynvml indisponível: {e}")


def start_kael_api():
    if not KAEL_DIR.exists():
        log.error(f"Pasta do Kael não encontrada: {KAEL_DIR}")
        return False
    log.info("Iniciando API Server do Kael...")
    proc = subprocess.Popen(
        [str(PYTHON_EXE), "api_server.py"],
        cwd=str(KAEL_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    # espera a API subir
    for _ in range(15):
        if is_port_open("127.0.0.1", KAEL_API_PORT):
            log.info("Kael API online.")
            return True
        time.sleep(1)
    log.warning("API não respondeu no timeout (pode estar OK).")
    return True


def open_ui():
    """Abre a interface (CustomTkinter ou navegador)."""
    chat_html = KAEL_DIR / "chat.html"
    if chat_html.exists():
        log.info("Abrindo chat.html no navegador.")
        os.startfile(str(chat_html))  # Windows
    else:
        log.info("UI CustomTkinter: inicie kael_core.py manualmente.")


def main():
    log.info("=" * 40)
    log.info("KAEL STARTUP INICIADO")
    log.info("=" * 40)
    if not start_ollama():
        sys.exit(1)
    if not load_model():
        sys.exit(1)
    check_vram()
    if not start_kael_api():
        sys.exit(1)
    open_ui()
    log.info("KAEL PRONTO.")


if __name__ == "__main__":
    main()
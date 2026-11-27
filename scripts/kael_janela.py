"""Abre a interface do Kael em janela própria e leve via pywebview (sem navegador)."""
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
import webview

BASE_DIR = Path(__file__).resolve().parent.parent
URL = "http://127.0.0.1:8000"


def aguardar_api(timeout_seg: int = 25) -> bool:
    limite = time.time() + timeout_seg
    while time.time() < limite:
        try:
            with urllib.request.urlopen(URL, timeout=1.5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    iniciar = BASE_DIR / "scripts" / "iniciar_kael.py"
    if iniciar.is_file():
        subprocess.run(
            [sys.executable, str(iniciar), "--port", "8000", "--llm-port", "8080"],
            cwd=str(BASE_DIR),
            check=False,
        )

    aguardar_api(timeout_seg=25)

    webview.create_window(
        title="Kael AI — Ecos de Aethelgard",
        url=URL,
        width=1160,
        height=780,
        min_size=(800, 560),
    )
    webview.start()


if __name__ == "__main__":
    main()

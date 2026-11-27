import shutil
import socket
from pathlib import Path

PLUGIN_INFO = {
    "nome": "Status do Sistema",
    "descricao": "Verifica espaço livre no Termux/armazenamento e portas ativas do Kael."
}

def _porta_ativa(porta: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", porta), timeout=0.5):
            return True
    except OSError:
        return False

def _gb_livres(caminho: Path) -> str:
    try:
        if caminho.exists():
            _, _, livre = shutil.disk_usage(str(caminho))
            return f"{round(livre / (1024 ** 3), 2)} GB"
    except Exception:
        pass
    return "N/A"

def executar(_prompt: str = "") -> str:
    home_livre = _gb_livres(Path.home())
    shared_livre = _gb_livres(Path.home() / "storage/shared")
    portas = {
        "llama-server (8080)": _porta_ativa(8080),
        "api_server (8000)": _porta_ativa(8000),
        "receptor_lan (8099)": _porta_ativa(8099),
    }
    status_portas = ", ".join(f"{k}: {'OK' if v else 'OFF'}" for k, v in portas.items())
    return f"Termux (~): {home_livre} livre | Compartilhado: {shared_livre} livre | Portas -> {status_portas}"

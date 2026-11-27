"""Gerenciador de solicitações de permissão (Aceitar / Recusar) para o Kael."""
import json
import threading
import time
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PERM_FILE = DATA_DIR / "permissoes_kael.json"

_LOCK = threading.Lock()


def _carregar() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not PERM_FILE.is_file():
        return {"pending": [], "history": []}
    try:
        data = json.loads(PERM_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("pending", [])
            data.setdefault("history", [])
            return data
    except Exception:
        pass
    return {"pending": [], "history": []}


def _salvar(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PERM_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def solicitar_permissao(acao: str, alvo: str, detalhes: str = "") -> dict:
    item = {
        "id": str(uuid.uuid4())[:8],
        "acao": acao.strip(),
        "alvo": alvo.strip(),
        "detalhes": detalhes.strip(),
        "status": "pending",
        "criado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with _LOCK:
        data = _carregar()
        data["pending"].append(item)
        _salvar(data)
    return item


def listar_pendentes() -> list[dict]:
    with _LOCK:
        return list(_carregar().get("pending", []))


def resolver_permissao(perm_id: str, aceitar: bool) -> dict | None:
    novo_status = "accepted" if aceitar else "rejected"
    with _LOCK:
        data = _carregar()
        pendentes = data.get("pending", [])
        for idx, item in enumerate(pendentes):
            if item.get("id") == perm_id:
                resolvido = pendentes.pop(idx)
                resolvido["status"] = novo_status
                resolvido["resolvido_em"] = time.strftime("%Y-%m-%d %H:%M:%S")
                data.setdefault("history", []).append(resolvido)
                data["history"] = data["history"][-100:]
                _salvar(data)
                return resolvido
    return None


def consultar_status(perm_id: str) -> str:
    with _LOCK:
        data = _carregar()
        for item in data.get("pending", []):
            if item.get("id") == perm_id:
                return "pending"
        for item in reversed(data.get("history", [])):
            if item.get("id") == perm_id:
                return item.get("status", "rejected")
    return "not_found"


def aguardar_decisao(perm_id: str, timeout_seg: int = 120) -> str:
    limite = time.time() + timeout_seg
    while time.time() < limite:
        st = consultar_status(perm_id)
        if st in ("accepted", "rejected"):
            return st
        time.sleep(0.4)
    resolver_permissao(perm_id, aceitar=False)
    return "rejected"

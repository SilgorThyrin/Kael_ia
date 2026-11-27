"""Hook pre_chat para registrar o turno e a mensagem literal do usuário."""
import json
import time
from pathlib import Path

TURN_STATE_FILE = Path.home() / "Kael_ia" / "data" / "turn_state.json"


def pre_chat(payload: dict) -> dict:
    prompt = payload.get("prompt", "")
    if not isinstance(prompt, str):
        return payload

    TURN_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {"turn_id": 0, "last_prompt": "", "updated_at": 0.0}
    if TURN_STATE_FILE.is_file():
        try:
            state = json.loads(TURN_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    state["turn_id"] = int(state.get("turn_id", 0)) + 1
    state["last_prompt"] = prompt.strip()
    state["updated_at"] = time.time()
    TURN_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

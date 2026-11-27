import json
import requests
from core.configuration import (
    DEFAULT_CONFIG_PATH,
    load_config as load_runtime_config,
    validate_generation_settings,
)

CONFIG_PATH = DEFAULT_CONFIG_PATH
DEFAULT_LLAMA_URL = "http://127.0.0.1:8080"


def load_config():
    return load_runtime_config()


def _get_llama_url(config: dict) -> str:
    url = config.get("llama_url") or config.get("ollama_url") or DEFAULT_LLAMA_URL
    if ":8080" in url:
        return DEFAULT_LLAMA_URL
    return url.rstrip("/")


def _fix_mojibake(text: str) -> str:
    if not text:
        return text
    # Detecta padrão clássico de UTF-8 lido como latin-1 (ex: Ã©, Ã£, Ã§)
    if "Ã" in text or "Â" in text:
        try:
            fixed = text.encode("latin-1").decode("utf-8")
            return fixed
        except UnicodeError:
            pass
    return text


def check_ollama_status():
    config = load_config()
    base_url = _get_llama_url(config)
    try:
        r = requests.get(f"{base_url}/health", timeout=3)
        if r.status_code == 200:
            return True
        r2 = requests.get(f"{base_url}/v1/models", timeout=3)
        return r2.status_code == 200
    except requests.RequestException:
        return False


def generate_response(
    prompt: str,
    system_prompt: str = None,
    think: bool = None,
    settings: dict = None,
    on_chunk=None,
) -> dict:
    """Gera resposta via STREAMING usando llama-server (llama.cpp)."""
    config = load_config()
    if settings is not None:
        generation = validate_generation_settings(settings)
        config.update({
            "model_name": generation["model"],
            "temperature": generation["temperature"],
            "max_tokens": generation["max_tokens"],
            "think": generation["think"],
        })

    base_url = _get_llama_url(config)
    sys_msg = system_prompt if system_prompt is not None else config.get("system_prompt")
    if isinstance(sys_msg, str) and len(sys_msg) > 950:
        sys_msg = sys_msg[:950]

    prompt_seguro = prompt or ""
    if len(prompt_seguro) > 950:
        prompt_seguro = "...[resumo]\n" + prompt_seguro[-900:]

    messages = []
    if sys_msg:
        messages.append({"role": "system", "content": sys_msg})
    messages.append({"role": "user", "content": prompt_seguro})

    payload = {
        "model": config.get("model_name", "qwen2.5-1.5b"),
        "messages": messages,
        "temperature": min(float(config.get("temperature", 0.5)), 0.6),
        "max_tokens": min(int(config.get("max_tokens", 512)), 600),
        "repeat_penalty": 1.15,
        "stream": True,
    }

    try:
        print(f"[KAEL] Gerando via llama.cpp ({base_url})... ", end="", flush=True)

        response = requests.post(
            f"{base_url}/v1/chat/completions",
            json=payload,
            stream=True,
            timeout=(10, 120),
        )
        response.raise_for_status()

        response_parts = []
        thinking_parts = []
        in_think = False
        buf = ""

        loop_detected = False
        recent_lines = []

        def _emit(kind: str, piece: str):
            nonlocal loop_detected, recent_lines
            if not piece or loop_detected:
                return
            if kind == "thinking":
                thinking_parts.append(piece)
            else:
                response_parts.append(piece)
            full_so_far = "".join(response_parts)
            if len(full_so_far) >= 160:
                import re
                segments = re.split(r"[\n.!?]+", full_so_far)
                cleaned_segs = [
                    " ".join(seg.strip().lstrip("-*•0123456789.) ").split()).lower()
                    for seg in segments
                ]
                meaningful = [s for s in cleaned_segs if len(s) >= 35]
                repeated_any = any(meaningful.count(x) >= 3 for x in set(meaningful[-18:]))
                if (len(meaningful) >= 3 and len(set(meaningful[-3:])) == 1) or repeated_any:
                    loop_detected = True
                    if callable(on_chunk):
                        try:
                            on_chunk("content", "\n\n[Aviso: repetição detectada e interrompida automaticamente.]")
                        except Exception:
                            pass
                    return
            if callable(on_chunk):
                try:
                    on_chunk(kind, piece)
                except Exception:
                    pass

        for raw_bytes in response.iter_lines():
            if loop_detected:
                break
            if not raw_bytes:
                continue
            raw_line = raw_bytes.decode("utf-8", errors="replace")
            if raw_line.startswith("data:"):
                data_str = raw_line[5:].strip()
            elif raw_line.lstrip().startswith("{"):
                data_str = raw_line.strip()
            else:
                continue
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            choices = chunk.get("choices") or []
            if not choices and isinstance(chunk, dict) and "response" in chunk:
                choices = [{"delta": {"content": chunk.get("response") or ""}}]
            if not choices:
                continue
            delta = choices[0].get("delta") or {}

            reasoning = delta.get("reasoning_content") or delta.get("reasoning")
            if reasoning:
                _emit("thinking", str(reasoning))

            content = delta.get("content")
            if content:
                buf += str(content)
                while buf:
                    if not in_think:
                        idx = buf.find("<think>")
                        if idx == -1:
                            # Evita cortar tag parcial no final do buffer
                            keep = 0
                            for k in range(1, min(7, len(buf) + 1)):
                                if "<think>".startswith(buf[-k:]):
                                    keep = k
                                    break
                            emit_txt = buf[:-keep] if keep else buf
                            buf = buf[-keep:] if keep else ""
                            if emit_txt:
                                _emit("content", emit_txt)
                            break
                        else:
                            if idx > 0:
                                _emit("content", buf[:idx])
                            buf = buf[idx + len("<think>"):]
                            in_think = True
                    else:
                        end_idx = buf.find("</think>")
                        if end_idx == -1:
                            keep = 0
                            for k in range(1, min(8, len(buf) + 1)):
                                if "</think>".startswith(buf[-k:]):
                                    keep = k
                                    break
                            emit_thk = buf[:-keep] if keep else buf
                            buf = buf[-keep:] if keep else ""
                            if emit_thk:
                                _emit("thinking", emit_thk)
                            break
                        else:
                            if end_idx > 0:
                                _emit("thinking", buf[:end_idx])
                            buf = buf[end_idx + len("</think>"):]
                            in_think = False

        if buf:
            _emit("thinking" if in_think else "content", buf)

        final_response = "".join(response_parts).strip()
        final_thinking = "".join(thinking_parts).strip()
        print("OK")
        return {
            "response": final_response,
            "thinking": final_thinking,
            "status": "success",
        }
        if False:
            if content:
                response_parts.append(content)
                dots += 1
                if dots % 30 == 0:
                    print(".", end="", flush=True)

        print(" OK!")
        full_text = _fix_mojibake("".join(response_parts))
        return {
            "response": full_text,
            "thinking": "",
        }

    except requests.exceptions.Timeout:
        print(" TIMEOUT!")
        message = "llama.cpp parou de responder durante a geração."
        return {"response": f"[ERRO] {message}", "thinking": "", "error": message}
    except requests.RequestException as e:
        print(f" ERRO: {e}")
        message = f"llama.cpp não está respondendo: {e}"
        return {"response": f"[ERRO] {message}", "thinking": "", "error": message}
    except Exception as e:
        print(f" ERRO: {e}")
        message = f"Falha na comunicação com llama.cpp: {e}"
        return {"response": f"[ERRO] {message}", "thinking": "", "error": message}


if __name__ == "__main__":
    print("=" * 40)
    print("TESTE DE CONEXÃO DO KAEL (llama.cpp)")
    print("=" * 40)
    if check_ollama_status():
        print("✅ llama.cpp está online!")
        resultado = generate_response("Explique em 1 frase o que é IA.")
        print(f"\n🤖 RESPOSTA:\n{resultado['response']}")
    else:
        print("❌ llama.cpp está OFFLINE.")
    print("=" * 40)

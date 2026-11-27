#!/usr/bin/env python3
"""
Viva-voz continuo do Kael no Android/Termux (sem navegador).
Usa termux-microphone-record + ffmpeg (com ganho vocal 9x) + whisper.cpp + termux-tts-speak.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.request

API_CHAT_URL = "http://127.0.0.1:8000/chat"
WHISPER_BIN = os.path.expanduser("~/whisper.cpp/build/bin/whisper-cli")
WHISPER_MODEL = os.path.expanduser("~/modelos/whisper/ggml-tiny.bin")
ESTADO_FLAG = os.path.expanduser("~/Kael_ia/data/kael_vivavoz_ativo.flag")
DATA_DIR = os.path.expanduser("~/Kael_ia/data")
GATILHOS = ("ei kael", "hey kael", "oi kael", "ok kael", "e kael", "ei cael", "oi cael", "ei kel", "oi kel")


def _normalizar(texto: str) -> str:
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", str(texto or "").lower())
        if unicodedata.category(c) != "Mn"
    )
    limpo = re.sub(r"[,!.?;:\[\]()]+", " ", sem_acento)
    return re.sub(r"\s+", " ", limpo).strip()


def _limpar_para_fala(resposta: str) -> str:
    txt = re.sub(r"```[\s\S]*?```", " Código gerado e salvo na sandbox. ", str(resposta or ""))
    txt = re.sub(r"[`*_#>-]+", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt[:420] if txt else "Pronto."


def falar(texto: str) -> None:
    msg = _limpar_para_fala(texto)
    print(f"[KAEL VIVA-VOZ] {msg}", flush=True)
    if shutil.which("termux-tts-speak"):
        try:
            subprocess.run(["termux-tts-speak", "-l", "pt-BR", msg], timeout=25, check=False)
        except Exception:
            pass


def extrair_comando(fala_bruta: str):
    norm = _normalizar(fala_bruta)
    for g in GATILHOS:
        pos = norm.find(g)
        if pos != -1:
            return norm[pos + len(g):].strip()
    return None


def enviar_ao_kael(mensagem: str) -> str:
    payload = json.dumps({
        "mensagem": mensagem,
        "origem": "vivavoz_termux_api",
    }).encode("utf-8")
    req = urllib.request.Request(
        API_CHAT_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
            return str(dados.get("reply", "")).strip()
    except Exception as exc:
        return f"Erro ao falar com o servidor do Kael: {exc}"


def _amplitude_wav(wav_path: str) -> float:
    if not shutil.which("sox"):
        return 1.0
    try:
        proc = subprocess.run(
            ["sox", wav_path, "-n", "stat"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        m = re.search(r"Maximum amplitude:\s*([0-9.]+)", proc.stderr or "")
        if m:
            return float(m.group(1))
    except Exception:
        pass
    return 1.0


def gravar_bloco_wav(m4a_path: str, wav_path: str, duracao_s: int = 6) -> bool:
    for p in (m4a_path, wav_path):
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

    try:
        rec = subprocess.run(
            [
                "termux-microphone-record",
                "-f", m4a_path,
                "-l", str(duracao_s),
                "-e", "aac",
                "-r", "16000",
                "-c", "1",
            ],
            capture_output=True,
            timeout=duracao_s + 4,
            check=False,
        )
        if rec.returncode != 0:
            return False
        time.sleep(duracao_s + 0.3)
        subprocess.run(["termux-microphone-record", "-q"], capture_output=True, timeout=4, check=False)
    except Exception:
        return False

    if not os.path.exists(m4a_path) or os.path.getsize(m4a_path) < 1024:
        return False

    try:
        conv = subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", m4a_path,
                "-af", "highpass=f=120,volume=9.0",
                "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
                wav_path,
            ],
            timeout=8,
            check=False,
        )
        return conv.returncode == 0 and os.path.exists(wav_path) and os.path.getsize(wav_path) > 4000
    except Exception:
        return False


def transcrever_wav(wav_path: str) -> str:
    cmd = [
        WHISPER_BIN,
        "-m", WHISPER_MODEL,
        "-l", "pt",
        "-t", "4",
        "-nt",
        "--prompt", "Ei Kael, oi Kael, status do projeto Ecos de Aethelgard.",
        "-f", wav_path,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
        return (proc.stdout or "").strip()
    except Exception:
        return ""


def iniciar_vivavoz() -> None:
    if not os.path.isfile(WHISPER_BIN) or not os.path.isfile(WHISPER_MODEL):
        print("[ERRO] whisper-cli ou ggml-tiny.bin ausente.")
        sys.exit(1)
    if not shutil.which("termux-microphone-record") or not shutil.which("ffmpeg"):
        print("[ERRO] termux-microphone-record ou ffmpeg ausente.")
        sys.exit(1)

    if shutil.which("termux-wake-lock"):
        subprocess.run(["termux-wake-lock"], check=False)

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ESTADO_FLAG, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))

    m4a_tmp = os.path.join(DATA_DIR, "kael_fala_tmp.m4a")
    wav_tmp = os.path.join(DATA_DIR, "kael_fala_tmp.wav")
    aguardando_comando = False
    prazo_comando = 0.0

    falar("Viva-voz do Kael ativado.")

    try:
        while os.path.exists(ESTADO_FLAG):
            dur = 7 if aguardando_comando else 6
            if not gravar_bloco_wav(m4a_tmp, wav_tmp, duracao_s=dur):
                time.sleep(0.3)
                continue

            amp = _amplitude_wav(wav_tmp)
            if amp < 0.09:
                continue

            texto = transcrever_wav(wav_tmp)
            if not texto or "[MÚSICA" in texto.upper() or "[SILÊNCIO" in texto.upper():
                continue

            print(f"[OUVIDO amp={amp:.2f}] {texto}", flush=True)

            if aguardando_comando and time.time() <= prazo_comando:
                aguardando_comando = False
                cmd = _normalizar(texto)
            else:
                aguardando_comando = False
                cmd = extrair_comando(texto)
                if cmd is not None and not cmd:
                    falar("Sim?")
                    aguardando_comando = True
                    prazo_comando = time.time() + 12.0
                    continue

            if not cmd:
                continue

            if _normalizar(cmd) in ("desativar voz", "parar escuta", "desligar viva voz", "dormir agora"):
                falar("Encerrando viva-voz do Kael.")
                break

            resposta = enviar_ao_kael(cmd)
            falar(resposta)
    finally:
        for p in (m4a_tmp, wav_tmp, ESTADO_FLAG):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        if shutil.which("termux-wake-unlock"):
            subprocess.run(["termux-wake-unlock"], check=False)


if __name__ == "__main__":
    iniciar_vivavoz()

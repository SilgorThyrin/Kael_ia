#!/usr/bin/env python3
"""
Assistente de voz nativo do Kael para Android (sem navegador).
Usa Termux:API (termux-speech-to-text, termux-tts-speak, termux-notification)
e se comunica com http://127.0.0.1:8000/chat (com modo sleep automatico).
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
GATILHOS = ("ei kael", "hey kael", "oi kael", "ok kael")
ESTADO_FLAG = os.path.expanduser("~/Kael_ia/data/kael_voz_ativo.flag")


def _tem_comando(nome: str) -> bool:
    return shutil.which(nome) is not None


def _normalizar(texto: str) -> str:
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", str(texto or "").lower())
        if unicodedata.category(c) != "Mn"
    )
    limpo = re.sub(r"[,!.?;:]+", " ", sem_acento)
    return re.sub(r"\s+", " ", limpo).strip()


def _limpar_para_fala(resposta: str) -> str:
    txt = re.sub(r"```[\s\S]*?```", " Código gerado e salvo na sandbox. ", str(resposta or ""))
    txt = re.sub(r"[`*_#>-]+", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt[:420] if txt else "Pronto."


def falar(texto: str) -> None:
    msg = _limpar_para_fala(texto)
    print(f"[KAEL VOZ] {msg}", flush=True)
    if _tem_comando("termux-tts-speak"):
        try:
            subprocess.run(
                ["termux-tts-speak", "-l", "pt-BR", msg],
                timeout=25,
                check=False,
            )
        except Exception:
            pass


def notificar(titulo: str, corpo: str) -> None:
    if _tem_comando("termux-notification"):
        try:
            subprocess.run(
                [
                    "termux-notification",
                    "--id", "kael-assistente",
                    "--title", titulo,
                    "--content", corpo[:180],
                    "--ongoing",
                ],
                timeout=5,
                check=False,
            )
        except Exception:
            pass


def ouvir_uma_vez(timeout_s: int = 12) -> str:
    if not _tem_comando("termux-speech-to-text"):
        return ""
    try:
        proc = subprocess.run(
            ["termux-speech-to-text"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        return (proc.stdout or "").strip()
    except Exception:
        return ""


def extrair_comando(fala_bruta: str):
    norm = _normalizar(fala_bruta)
    for g in GATILHOS:
        pos = norm.find(g)
        if pos != -1:
            resto = norm[pos + len(g):].strip()
            return resto
    return None


def enviar_ao_kael(mensagem: str) -> str:
    payload = json.dumps({
        "mensagem": mensagem,
        "origem": "voz_nativa_android",
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
        return f"Não consegui falar com o servidor do Kael: {exc}"


def loop_assistente() -> None:
    if not _tem_comando("termux-speech-to-text"):
        print("[ERRO] termux-speech-to-text nao encontrado. Instale o pacote termux-api e o app Termux:API.")
        sys.exit(1)

    os.makedirs(os.path.dirname(ESTADO_FLAG), exist_ok=True)
    with open(ESTADO_FLAG, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))

    notificar("Kael Assistente", "Ouvindo 'Ei, Kael' em segundo plano...")
    falar("Assistente de voz do Kael ativado.")

    try:
        while os.path.exists(ESTADO_FLAG):
            fala = ouvir_uma_vez(timeout_s=15)
            if not fala:
                time.sleep(0.6)
                continue

            cmd = extrair_comando(fala)
            if cmd is None:
                continue

            if not cmd:
                falar("Sim?")
                cmd = ouvir_uma_vez(timeout_s=12)
                if not cmd:
                    continue

            if _normalizar(cmd) in ("desativar voz", "parar escuta", "dormir agora"):
                falar("Encerrando escuta de voz do Kael.")
                break

            notificar("Kael Processando", cmd)
            resposta = enviar_ao_kael(cmd)
            notificar("Kael", _limpar_para_fala(resposta))
            falar(resposta)
            time.sleep(0.4)
    finally:
        if os.path.exists(ESTADO_FLAG):
            try:
                os.remove(ESTADO_FLAG)
            except Exception:
                pass
        if _tem_comando("termux-notification-remove"):
            subprocess.run(["termux-notification-remove", "kael-assistente"], check=False)


if __name__ == "__main__":
    loop_assistente()

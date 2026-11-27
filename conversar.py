"""Chat direto no terminal com o Kael (sem curl e sem comandos com barra)."""
import requests

URL = "http://127.0.0.1:8000/chat"
print("💬 Chat livre com o Kael iniciado (digite 'sair' para encerrar).\n")

while True:
    try:
        msg = input("Você > ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not msg:
        continue
    if msg.lower() in ("sair", "exit", "quit"):
        break

    try:
        r = requests.post(URL, json={"prompt": msg}, timeout=240)
        data = r.json()
        print(f"\nKael > {data.get('response', data)}\n")
        if data.get("thinking"):
            print(f"   [{data['thinking']}]\n")
    except Exception as exc:
        print(f"\n⚠️ Erro ao falar com o Kael: {exc}\n")

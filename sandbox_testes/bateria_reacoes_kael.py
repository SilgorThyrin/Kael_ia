import json
import urllib.request

URL = "http://127.0.0.1:8000/chat"

CENARIOS = [
    ("1. Música direta", "Toca Linkin Park no brave"),
    ("2. WhatsApp incompleto (passo 1)", "Envia um zapzap para Amor"),
    ("3. Troca de assunto no meio do fluxo", "Na verdade toca uma música antes"),
    ("4. Música incompleta -> pergunta o que falta", "Põe uma música"),
    ("5. Resposta do passo 2 da música", "Numb"),
    ("6. Pesquisa + Resumo no chat (não abre app)", "Pesquisa como criar os melhores jogos no Roblox Studio e me faz um resumo"),
    ("7. Ensino de regra / memória", "Lembra que prefiro Luau modular e scripts limpos no Ecos de Aethelgard"),
    ("8. Consulta memória FTS5 sobre tema", "Lembra o que falamos sobre Roblox Studio ou Luau?"),
    ("9. Comando PC Windows (permissão/fila)", "Abre o vscode no pc"),
]

def enviar(msg: str) -> dict:
    payload = json.dumps({"message": msg}).encode("utf-8")
    req = urllib.request.Request(
        URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=75) as resp:
        return json.loads(resp.read().decode("utf-8"))

print("=== BATERIA DE TESTES DE REAÇÃO DO KAEL ===\n")
for nome, frase in CENARIOS:
    print(f"[{nome}]")
    print(f"  Você : {frase}")
    try:
        res = enviar(frase)
        reply = (res.get("reply") or "").strip().replace("\n", " | ")
        pend = res.get("pending_approvals", 0)
        print(f"  Kael : {reply[:260]}{'...' if len(reply) > 260 else ''} (pendências={pend})")
    except Exception as exc:
        print(f"  ERRO : {exc}")
    print("-" * 60)

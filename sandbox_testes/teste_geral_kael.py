import json
import os
import sys
import urllib.request
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.expanduser("~/Kael_ia"))
from scripts import controle_apps as ca
from scripts import kael_apps_router as rt

resultados = []

def registrar(nome, ok, detalhe=""):
    status = "OK" if ok else "FALHA"
    resultados.append((status, nome, detalhe))
    print(f"[{status}] {nome}: {detalhe}")

# 1. Teste de Endpoints HTTP reais (127.0.0.1:8000)
for rota in ["/health", "/kael-perm/pending", "/chat/historico?limit=5", "/apps/android", "/apps/pc/fila"]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:8000{rota}", timeout=5) as r:
            body = r.read().decode("utf-8", errors="ignore")
            registrar(f"GET {rota}", r.status == 200, f"HTTP {r.status} ({len(body)} bytes)")
    except Exception as e:
        registrar(f"GET {rota}", False, str(e))

# 2. Teste da identidade multi-projeto no /chat
try:
    req = urllib.request.Request(
        "http://127.0.0.1:8000/chat",
        data=json.dumps({"message": "Liste todas as suas funções"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=8) as r:
        data = json.loads(r.read().decode("utf-8"))
        reply = data.get("reply", "")
        ok = ("~/Projetos/" in reply) and ("Criar, atualizar e manter" in reply)
        registrar("POST /chat (Identidade Multi-Projeto)", ok, reply.splitlines()[0] if reply else "vazio")
except Exception as e:
    registrar("POST /chat (Identidade Multi-Projeto)", False, str(e))

# 3. Teste das Intents Android e Roteador (com subprocess simulado para não abrir apps durante o teste)
fake_proc = MagicMock(returncode=0, stdout="Success", stderr="")
with patch("subprocess.run", return_value=fake_proc) as mock_sub:
    # 3a. Música no Brave (autoplay)
    r_brave = rt.interceptar_chat_apps("Toca linkin park no brave")
    registrar("Roteador Música Brave", "BROWSER_AUTOPLAY" in r_brave or "Tocando" in r_brave, r_brave)

    # 3b. Música no SimpMusic
    r_simp = rt.interceptar_chat_apps("Tocar metallica no simpmusic")
    registrar("Roteador Música SimpMusic", "Tocando" in r_simp or "Abrindo" in r_simp, r_simp)

    # 3c. Pesquisa no YouTube
    r_yt = rt.interceptar_chat_apps("Pesquisar lua roblox studio no youtube")
    registrar("Roteador Pesquisa YouTube", "Pesquisando" in r_yt, r_yt)

    # 3d. WhatsApp
    r_wa = rt.interceptar_chat_apps("Mandar whatsapp 5561999999999: Teste Kael")
    registrar("Roteador WhatsApp", "WhatsApp" in r_wa, r_wa)

    # 3e. Abrir app Android
    r_app = rt.interceptar_chat_apps("Abrir calculator")
    registrar("Roteador Abrir App Android", "Abrindo" in r_app or "não encontrado" in r_app, r_app)

    # 3f. Comando PC Windows (deve exigir permissão)
    r_pc = rt.interceptar_chat_apps("Abrir vscode no pc")
    registrar("Roteador PC Windows (Permissão)", "Permissão necessária" in r_pc, r_pc)

# 4. Verificação dos patches da UI V4 (OLED, Enter quebra linha, Deduplicação)
html_path = os.path.expanduser("~/Kael_ia/templates/kael_chat.html")
html = open(html_path, encoding="utf-8").read()
for tag_id in ["kaelMobileV3Style", "kaelMobileV4Style", "kaelEnterNewlineScript", "kaelDedupBolhaScript"]:
    registrar(f"UI Template ({tag_id})", tag_id in html, "presente" if tag_id in html else "ausente")

falhas = [r for r in resultados if r[0] == "FALHA"]
print("\n==========================================")
print(f"RESUMO GERAL: {len(resultados) - len(falhas)}/{len(resultados)} PASSARAM | FALHAS: {len(falhas)}")
print("==========================================")
sys.exit(1 if falhas else 0)

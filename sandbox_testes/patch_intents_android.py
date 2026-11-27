import os, shutil, time

p_ctrl = os.path.expanduser("~/Kael_ia/scripts/controle_apps.py")
shutil.copy2(p_ctrl, os.path.expanduser(f"~/Kael_ia_backups/controle_apps.bak_{int(time.time())}.py"))
src = open(p_ctrl, encoding="utf-8").read()

bloco_intents = '''

# === INTENTS DE AÇÃO INTERNA EM APPS ANDROID ===
import urllib.parse

def executar_intent_android(especificacao: str) -> dict:
    """
    Formato esperado: 'musica|<app_hint>|<query>' ou 'pesquisa|<app_hint>|<query>' ou 'whatsapp|<destino>|<texto>'
    """
    partes = (especificacao or "").split("|", 2)
    if len(partes) < 3:
        return {"ok": False, "error": "Especificação de intent inválida."}
    tipo, alvo_app, termo = partes[0].strip().lower(), partes[1].strip().lower(), partes[2].strip()
    q_enc = urllib.parse.quote(termo)

    if tipo == "musica":
        pacote = resolver_pacote_android(alvo_app) if alvo_app not in ("", "musica", "música") else ""
        if pacote:
            cmd = [
                "am", "start", "--user", "0",
                "-a", "android.media.action.MEDIA_PLAY_FROM_SEARCH",
                "-e", "query", termo,
                "-p", pacote,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and "Error" not in (res.stderr or ""):
                return {"ok": True, "modo": "MEDIA_PLAY_FROM_SEARCH", "pacote": pacote, "query": termo}
            # Fallback: abre o app e lança busca de mídia genérica
            abrir_app_android(pacote)
        url_ytm = f"https://music.youtube.com/search?q={q_enc}"
        subprocess.run(["am", "start", "--user", "0", "-a", "android.intent.action.VIEW", "-d", url_ytm], capture_output=True, text=True)
        return {"ok": True, "modo": "VIEW_MUSIC_URL", "url": url_ytm, "pacote": pacote}

    if tipo == "pesquisa":
        if "youtube" in alvo_app:
            url = f"https://www.youtube.com/results?search_query={q_enc}"
        else:
            url = f"https://www.google.com/search?q={q_enc}"
        subprocess.run(["am", "start", "--user", "0", "-a", "android.intent.action.VIEW", "-d", url], capture_output=True, text=True)
        return {"ok": True, "modo": "ACTION_VIEW", "url": url}

    if tipo == "whatsapp":
        num = "".join(ch for ch in alvo_app if ch.isdigit())
        url = f"https://wa.me/{num}?text={q_enc}" if num else f"https://api.whatsapp.com/send?text={q_enc}"
        subprocess.run(["am", "start", "--user", "0", "-a", "android.intent.action.VIEW", "-d", url], capture_output=True, text=True)
        return {"ok": True, "modo": "WHATSAPP_URI", "url": url}

    return {"ok": False, "error": f"Tipo de intent desconhecido: {tipo}"}
'''

if "def executar_intent_android(" not in src:
    src = src + "\n" + bloco_intents

cand = os.path.expanduser("~/Kael_ia/sandbox_testes/candidatos/controle_apps_intents.py")
open(cand, "w", encoding="utf-8").write(src)
print("Candidato controle_apps gerado:", cand)

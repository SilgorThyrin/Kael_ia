import os, re

# 1. Adiciona busca de contato na agenda Android (termux-contact-list) em scripts/controle_apps.py
p_ctrl = os.path.expanduser("~/Kael_ia/scripts/controle_apps.py")
src_ctrl = open(p_ctrl, encoding="utf-8").read()

func_contato = '''
def resolver_contato_whatsapp(dest: str) -> str:
    """Resolve nome de contato via termux-contact-list ou extrai dígitos se já for telefone."""
    import json, unicodedata
    dest = (dest or "").strip()
    if not dest:
        return ""
    digitos = "".join(ch for ch in dest if ch.isdigit())
    if len(digitos) >= 8:
        return digitos if digitos.startswith("55") else "55" + digitos

    def _norm(s):
        return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn").strip()

    alvo_norm = _norm(dest)
    cache_path = os.path.expanduser("~/Kael_ia/data/contatos_cache.json")
    contatos = []
    try:
        res = subprocess.run(["termux-contact-list"], capture_output=True, text=True, timeout=6)
        if res.returncode == 0 and res.stdout.strip().startswith("["):
            contatos = json.loads(res.stdout)
            open(cache_path, "w", encoding="utf-8").write(res.stdout)
    except Exception:
        pass
    if not contatos and os.path.exists(cache_path):
        try:
            contatos = json.loads(open(cache_path, encoding="utf-8").read())
        except Exception:
            contatos = []

    for c in contatos:
        nome = _norm(str(c.get("name") or ""))
        if alvo_norm == nome or alvo_norm in nome:
            num = "".join(ch for ch in str(c.get("number") or "") if ch.isdigit())
            if len(num) >= 8:
                return num if num.startswith("55") else "55" + num
    return ""
'''

if "def resolver_contato_whatsapp(" not in src_ctrl:
    src_ctrl = src_ctrl.replace("def executar_intent_android(", func_contato + "\ndef executar_intent_android(", 1)

bloco_wa_antigo = """    if tipo == "whatsapp":
        num = "".join(ch for ch in alvo_app if ch.isdigit())
        url = f"https://wa.me/{num}?text={q_enc}" if num else f"https://api.whatsapp.com/send?text={q_enc}"
        subprocess.run(["am", "start", "--user", "0", "-a", "android.intent.action.VIEW", "-d", url], capture_output=True, text=True)
        return {"ok": True, "modo": "WHATSAPP_URI", "url": url}"""

bloco_wa_novo = """    if tipo == "whatsapp":
        num = resolver_contato_whatsapp(alvo_app)
        if alvo_app and not num:
            return {"ok": False, "error": f"Contato '{alvo_app}' não encontrado na agenda (verifique permissão de Contatos do Termux:API)."}
        if num and termo:
            url = f"https://wa.me/{num}?text={q_enc}"
        elif num:
            url = f"https://wa.me/{num}"
        else:
            url = f"https://api.whatsapp.com/send?text={q_enc}"
        subprocess.run(["am", "start", "--user", "0", "-a", "android.intent.action.VIEW", "-d", url], capture_output=True, text=True)
        return {"ok": True, "modo": "WHATSAPP_URI", "url": url, "telefone": num}"""

assert bloco_wa_antigo in src_ctrl, "Bloco whatsapp antigo não encontrado"
src_ctrl = src_ctrl.replace(bloco_wa_antigo, bloco_wa_novo, 1)
cand_ctrl = os.path.expanduser("~/Kael_ia/sandbox_testes/candidatos/controle_apps_wa.py")
open(cand_ctrl, "w", encoding="utf-8").write(src_ctrl)

# 2. Atualiza regex do WhatsApp em scripts/kael_apps_router.py
p_rt = os.path.expanduser("~/Kael_ia/scripts/kael_apps_router.py")
src_rt = open(p_rt, encoding="utf-8").read()

wa_rt_antigo = """    # 3. Preparar mensagem no WhatsApp (abre o app já preenchido; o envio final é seu)
    m_wa = re.search(r"\\b(?:enviar|mandar)\\s+(?:mensagem\\s+no\\s+)?whatsapp(?:\\s+([0-9+()\\s-]{8,20}))?\\s*[:,-]\\s*(.+)$", raw, re.IGNORECASE)
    if m_wa:
        num = (m_wa.group(1) or "").strip()
        txt = m_wa.group(2).strip()
        res = ca.executar_intent_android(f"whatsapp|{num}|{txt}")
        return "Abrindo WhatsApp com a mensagem pronta." if res.get("ok") else f"Erro ao abrir WhatsApp: {res.get('error')}" """.rstrip()

wa_rt_novo = """    # 3. Preparar mensagem / abrir contato no WhatsApp (com ou sem texto, por nome ou número)
    m_wa = re.search(
        r"\\b(?:enviar|envia|mandar|manda|abrir|abre)\\s+(?:uma\\s+)?(?:mensagem\\s+)?(?:via\\s+|no\\s+|pelo\\s+)?whatsapp(?:\\s+(?:para|pro|pra|de)\\s+([^:,-]+?))?(?:\\s*(?:[:,-]|dizendo|falando)\\s*(.+))?$",
        raw,
        re.IGNORECASE,
    )
    if m_wa and "whatsapp" in low:
        dest = (m_wa.group(1) or "").strip()
        txt = (m_wa.group(2) or "").strip()
        res = ca.executar_intent_android(f"whatsapp|{dest}|{txt}")
        if res.get("ok"):
            alvo_lbl = f" para **{dest}**" if dest else ""
            msg_lbl = f" com o texto: *\"{txt}\"*" if txt else " (conversa aberta)"
            return f"Abrindo WhatsApp{alvo_lbl}{msg_lbl}."
        return f"Não consegui abrir o WhatsApp: {res.get('error')}" """.rstrip()

assert wa_rt_antigo in src_rt, "Bloco router whatsapp antigo não encontrado"
src_rt = src_rt.replace(wa_rt_antigo, wa_rt_novo, 1)
cand_rt = os.path.expanduser("~/Kael_ia/sandbox_testes/candidatos/kael_apps_router_wa.py")
open(cand_rt, "w", encoding="utf-8").write(src_rt)
print("Candidatos WhatsApp gerados com sucesso.")

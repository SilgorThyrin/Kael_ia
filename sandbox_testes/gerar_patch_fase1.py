import os, re, py_compile

src_path = os.path.expanduser("~/Kael_ia/api_server.py")
dst_path = os.path.expanduser("~/Kael_ia/sandbox_testes/candidatos/api_server_apps.py")
with open(src_path, "r", encoding="utf-8") as f:
    src = f.read()

bloco_helpers = '''
# === KAEL FASE 1: CONTROLE DE APPS ANDROID E FILA PC WINDOWS ===
try:
    from scripts import controle_apps as _controle_apps
except Exception:
    _controle_apps = None

def _executar_acao_app_aprovada(resolvido: dict) -> dict:
    if not isinstance(resolvido, dict) or not _controle_apps:
        return {}
    if resolvido.get("status") != "approved":
        return {}
    acao = str(resolvido.get("acao") or "").strip()
    alvo = str(resolvido.get("alvo") or "").strip()
    if acao == "abrir_app_android" and alvo:
        return _controle_apps.abrir_app_android(alvo)
    if acao == "comando_pc" and alvo:
        return _controle_apps.enfileirar_comando_pc(alvo)
    return {}

def _interceptar_comando_apps_chat(user_message: str) -> str:
    if not _controle_apps or not callable(solicitar_permissao):
        return ""
    low = (user_message or "").strip().lower()
    if any(k in low for k in ("listar apps", "quais apps", "apps instalados")):
        res = _controle_apps.listar_apps_android(False)
        amostra = ", ".join(res.get("pacotes", [])[:12])
        cmds_pc = ", ".join(_controle_apps.COMANDOS_PC_PERMITIDOS.keys())
        return f"Apps Android: {res.get('total', 0)} (amostra: {amostra}...). Comandos PC: {cmds_pc}."
    m_pc = re.search(r"\\b(?:abrir|abre|iniciar|executar|sincronizar)\\s+(.+?)\\s+(?:no\\s+pc|no\\s+computador|no\\s+windows)\\b", low)
    if m_pc:
        termo = m_pc.group(1).strip()
        mapa = {"roblox studio": "roblox_studio", "roblox": "roblox_studio", "vscode": "vscode", "vs code": "vscode", "navegador": "navegador", "chrome": "navegador", "aethelgard": "sincronizar_aethelgard"}
        chave = mapa.get(termo, termo.replace(" ", "_"))
        if chave not in _controle_apps.COMANDOS_PC_PERMITIDOS:
            return f"Comando '{termo}' fora da whitelist PC: {list(_controle_apps.COMANDOS_PC_PERMITIDOS.keys())}."
        perm = solicitar_permissao("comando_pc", chave, f"Enfileirar comando {chave} para PC")
        return f"Permissão necessária para PC Windows (id: {perm.get('id')}). Confirme no pop-up para '{chave}'."
    m_and = re.match(r"^(?:kael[,\\s]+)?(?:abrir|abre|iniciar|executar)\\s+(?:o\\s+|a\\s+|app\\s+)?([a-zA-Z0-9._\\s-]{2,40})$", low)
    if m_and:
        termo = m_and.group(1).strip()
        pacote = _controle_apps.resolver_pacote_android(termo)
        if not pacote:
            return f"App Android '{termo}' não encontrado."
        perm = solicitar_permissao("abrir_app_android", pacote, f"Abrir app Android {pacote}")
        return f"Permissão necessária para abrir '{pacote}' (id: {perm.get('id')}). Confirme no pop-up."
    return ""

@app.route("/apps/android", methods=["GET"])
def api_listar_apps_android():
    return jsonify(_controle_apps.listar_apps_android(request.args.get("refresh") == "1")) if _controle_apps else (jsonify({"ok": False}), 500)

@app.route("/apps/pc/fila", methods=["GET"])
def api_listar_fila_pc():
    return jsonify({"ok": True, "comandos": _controle_apps.listar_fila_pc(request.args.get("todos") != "1")}) if _controle_apps else (jsonify({"ok": False}), 500)
'''

alvo_resolve = '    if not resolvido and not reg_resultado:\n        return jsonify({"ok": False, "error": "Permissão não encontrada ou já resolvida."}), 404\n\n    return jsonify({'
subst_resolve = '    if not resolvido and not reg_resultado:\n        return jsonify({"ok": False, "error": "Permissão não encontrada ou já resolvida."}), 404\n\n    execucao_app = _executar_acao_app_aprovada(resolvido)\n    return jsonify({\n        "execucao_app": execucao_app,'
assert alvo_resolve in src
src = src.replace(alvo_resolve, subst_resolve, 1)

alvo_chat = '    _append_chat_historico_json("user", user_message)'
subst_chat = '    _append_chat_historico_json("user", user_message)\n    _resp_apps = _interceptar_comando_apps_chat(user_message)\n    if _resp_apps:\n        _append_chat_historico_json("assistant", _resp_apps)\n        return jsonify({"reply": _resp_apps, "pending_approvals": len(listar_pendentes()) if callable(listar_pendentes) else 0})'
assert alvo_chat in src
src = src.replace(alvo_chat, subst_chat, 1)

alvo_main = "if __name__ == '__main__':"
assert alvo_main in src
src = src.replace(alvo_main, bloco_helpers + "\n\n" + alvo_main, 1)

with open(dst_path, "w", encoding="utf-8") as f:
    f.write(src)
py_compile.compile(dst_path, doraise=True)
print("PATCH_OK:", dst_path)

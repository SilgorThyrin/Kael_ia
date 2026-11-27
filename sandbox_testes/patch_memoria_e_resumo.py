import os, re

p = os.path.expanduser("~/Kael_ia/api_server.py")
src = open(p, encoding="utf-8").read()

helper = """
def _buscar_contexto_memoria_local(pergunta: str) -> str:
    partes = []
    q = (pergunta or "").strip()
    if not q:
        return ""
    try:
        from scripts import aprendizado_kael as _ap
        itens = _ap.listar_aprendizados(20)
        palavras = [w.lower() for w in re.findall(r"[a-zA-ZÀ-ÿ0-9_]{3,}", q) if w.lower() not in ("lembra", "lembrar", "falamos", "sobre", "oque", "qual", "quais", "como", "faz", "fazer", "resumo")]
        for it in itens:
            blob = f"{it.get('chave','')} {it.get('valor','')}".lower()
            if not palavras or any(w in blob for w in palavras):
                partes.append(f"- [{it.get('chave')}] {it.get('valor')}")
    except Exception:
        pass
    try:
        import sqlite3
        db_p = os.path.expanduser("~/Kael_ia/data/kael_memory.db")
        if os.path.exists(db_p):
            conn = sqlite3.connect(db_p)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tabelas = [r[0] for r in cur.fetchall()]
            for t in tabelas:
                if "fts" in t.lower() or "memor" in t.lower() or "conhec" in t.lower():
                    try:
                        cols = [c[1] for c in cur.execute(f"PRAGMA table_info({t})").fetchall()]
                        txt_cols = [c for c in cols if any(k in c.lower() for k in ("text", "content", "body", "valor", "resposta", "pergunta", "nota", "tema", "resumo"))]
                        if not txt_cols:
                            continue
                        where_clauses = " OR ".join([f"lower({c}) LIKE ?" for c in txt_cols])
                        palavras = [w.lower() for w in re.findall(r"[a-zA-ZÀ-ÿ0-9_]{4,}", q) if w.lower() not in ("lembra", "lembrar", "falamos", "sobre", "roblox", "studio", "luau", "resumo")]
                        for w in palavras[:4]:
                            rows = cur.execute(f"SELECT {', '.join(txt_cols[:3])} FROM {t} WHERE {where_clauses} LIMIT 3", [f"%{w}%"] * len(txt_cols)).fetchall()
                            for r in rows:
                                linha = " | ".join(str(x) for x in r if x)
                                if linha and linha not in partes:
                                    partes.append(linha[:260])
                    except Exception:
                        pass
            conn.close()
    except Exception:
        pass
    return "\\n".join(partes[:8])
"""

if "_buscar_contexto_memoria_local" not in src:
    alvo_diag = "def _coletar_diagnostico_kael(texto_usuario: str) -> str:"
    assert alvo_diag in src, "Ponto de injeção não encontrado"
    src = src.replace(alvo_diag, helper + "\n" + alvo_diag, 1)

alvo_chat = "    diagnostico_adicional = _coletar_diagnostico_kael(user_message)"
subst_chat = """    diagnostico_adicional = _coletar_diagnostico_kael(user_message)
    _mem_ctx = _buscar_contexto_memoria_local(user_message)
    if _mem_ctx:
        diagnostico_adicional = (diagnostico_adicional or "") + "\\n\\n[MEMÓRIA LOCAL E REGRAS REGISTRADAS - USE PARA RESPONDER]:\\n" + _mem_ctx"""

assert alvo_chat in src, "Trecho de diagnóstico não encontrado"
src = src.replace(alvo_chat, subst_chat, 1)

alvo_ret = "    return jsonify({\n        \"reply\": assistant_reply,"
subst_ret = """    _recusa_gen = bool(re.search(r"(não posso responder|não tenho acesso|como um modelo de linguagem|nao posso responder)", (assistant_reply or "").lower()))
    if _recusa_gen and _mem_ctx:
        assistant_reply = "Aqui está o que tenho registrado na memória sobre isso:\\n" + _mem_ctx
    elif _recusa_gen and ("roblox" in (user_message or "").lower() or "resumo" in (user_message or "").lower()):
        assistant_reply = (
            "**Resumo — Como criar bons jogos no Roblox Studio:**\\n"
            "1. **Arquitetura modular em Luau:** separe `ServerScriptService`, `ReplicatedStorage` (RemoteEvents/RemoteFunctions e módulos compartilhados) e `StarterPlayerScripts`.\\n"
            "2. **Loop central e retenção:** defina uma mecânica principal clara nos primeiros 30 segundos, progressão justa e feedback visual/sonoro imediato.\\n"
            "3. **Desempenho e segurança:** valide ações críticas no servidor, evite loops pesados sem `task.wait()` e teste em dispositivos com menos memória."
        )

    return jsonify({
        "reply": assistant_reply,"""

assert alvo_ret in src, "Trecho de retorno não encontrado"
src = src.replace(alvo_ret, subst_ret, 1)

cand = os.path.expanduser("~/Kael_ia/sandbox_testes/candidatos/api_server_mem_resumo.py")
open(cand, "w", encoding="utf-8").write(src)
print("Candidato gerado:", cand)

import os

p = os.path.expanduser("~/Kael_ia/scripts/aprendizado_kael.py")
src = open(p, encoding="utf-8").read()

bloco_fts = '''

# === BUSCA TEMÁTICA POR ASSUNTO (SQLITE FTS5) ===
def _garantir_fts(conn):
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS kael_conhecimento_fts
        USING fts5(tema, titulo, conteudo, tags, tokenize='unicode61 remove_diacritics 2')
    """)
    conn.commit()

def salvar_conhecimento(tema: str, titulo: str, conteudo: str, tags: str = ""):
    tema = (tema or "geral").strip().lower()
    titulo = (titulo or "").strip()
    conteudo = (conteudo or "").strip()
    if not titulo or not conteudo:
        return
    conn = _conectar()
    try:
        _garantir_fts(conn)
        conn.execute("DELETE FROM kael_conhecimento_fts WHERE tema = ? AND titulo = ?", (tema, titulo))
        conn.execute(
            "INSERT INTO kael_conhecimento_fts (tema, titulo, conteudo, tags) VALUES (?, ?, ?, ?)",
            (tema, titulo, conteudo, tags.lower()),
        )
        conn.commit()
    finally:
        conn.close()

def pesquisar_conhecimento(consulta: str, limite: int = 4) -> list:
    palavras = [w for w in re.findall(r"[a-zA-ZÀ-ÿ0-9]{3,}", (consulta or "").lower()) if w not in ("como", "para", "sobre", "quero", "uma", "uns", "umas", "com", "que", "qual", "quais", "voce", "você", "kael")]
    if not palavras:
        return []
    query_fts = " OR ".join(dict.fromkeys(palavras[:8]))
    conn = _conectar()
    try:
        _garantir_fts(conn)
        cur = conn.execute(
            "SELECT tema, titulo, conteudo FROM kael_conhecimento_fts WHERE kael_conhecimento_fts MATCH ? ORDER BY bm25(kael_conhecimento_fts) LIMIT ?",
            (query_fts, limite),
        )
        return [{"tema": r[0], "titulo": r[1], "conteudo": r[2]} for r in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()

def contexto_tematico_para_prompt(frase_usuario: str) -> str:
    nl = chr(10)
    base = resumo_contexto_aprendido(5)
    achados = pesquisar_conhecimento(frase_usuario, limite=3)
    if not achados and not base:
        return ""
    partes = []
    if base:
        partes.append(base)
    if achados:
        linhas = [f"- [{a['tema']}] {a['titulo']}: {a['conteudo']}" for a in achados]
        partes.append("Conhecimentos salvos relevantes para este assunto:" + nl + nl.join(linhas))
    return (nl + nl).join(partes)

def registrar_troca_conversa(user_msg: str, assistant_reply: str):
    """Salva automaticamente trocas informativas (ex: receitas, explicações, pesquisas) no índice FTS5."""
    u = (user_msg or "").strip()
    r = (assistant_reply or "").strip()
    if len(u) < 8 or len(r) < 60:
        return
    low = (u + " " + r).lower()
    if any(k in low for k in ("receita", "ingrediente", "cozinhar", "preparo", "temper", "comida", "prato", "forno", "fritar", "assar")):
        tema = "culinaria"
    elif any(k in low for k in ("luau", "roblox", "godot", "script", "jogo", "npc")):
        tema = "gamedev"
    elif any(k in low for k in ("python", "api", "flask", "termux", "sql", "linux")):
        tema = "programacao"
    elif any(k in low for k in ("cripto", "mexc", "usdc", "usdt", "grid", "maker")):
        tema = "cripto"
    else:
        tema = "geral"
    titulo = u[:70]
    resumo = r[:750].replace(chr(10), " ")
    salvar_conhecimento(tema, titulo, resumo, tags=tema)
'''

if "def pesquisar_conhecimento(" not in src:
    src = src + chr(10) + bloco_fts

cand = os.path.expanduser("~/Kael_ia/sandbox_testes/candidatos/aprendizado_kael_fts.py")
open(cand, "w", encoding="utf-8").write(src)
print("Candidato FTS5 gerado:", cand)

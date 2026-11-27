import os
import re
import sqlite3
import time

DB_PATH = os.path.expanduser("~/Kael_ia/data/kael_memory.db")

def _conectar():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kael_learned_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria TEXT NOT NULL,
            chave TEXT NOT NULL UNIQUE,
            valor TEXT NOT NULL,
            uso_count INTEGER DEFAULT 1,
            updated_at REAL NOT NULL
        )
    """)
    conn.commit()
    return conn

def salvar_aprendizado(categoria: str, chave: str, valor: str):
    chave = (chave or "").strip().lower()
    valor = (valor or "").strip()
    if not chave or not valor:
        return
    conn = _conectar()
    try:
        conn.execute("""
            INSERT INTO kael_learned_rules (categoria, chave, valor, uso_count, updated_at)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(chave) DO UPDATE SET
                categoria = excluded.categoria,
                valor = excluded.valor,
                uso_count = kael_learned_rules.uso_count + 1,
                updated_at = excluded.updated_at
        """, (categoria, chave, valor, time.time()))
        conn.commit()
    finally:
        conn.close()

def buscar_aprendizado(chave: str) -> str:
    chave = (chave or "").strip().lower()
    if not chave:
        return ""
    conn = _conectar()
    try:
        cur = conn.execute("SELECT valor FROM kael_learned_rules WHERE chave = ?", (chave,))
        row = cur.fetchone()
        if row:
            conn.execute("UPDATE kael_learned_rules SET uso_count = uso_count + 1, updated_at = ? WHERE chave = ?", (time.time(), chave))
            conn.commit()
            return str(row[0])
        return ""
    finally:
        conn.close()

def listar_aprendizados(limite: int = 20) -> list:
    conn = _conectar()
    try:
        cur = conn.execute(
            "SELECT categoria, chave, valor, uso_count FROM kael_learned_rules ORDER BY uso_count DESC, updated_at DESC LIMIT ?",
            (limite,),
        )
        return [{"categoria": r[0], "chave": r[1], "valor": r[2], "usos": r[3]} for r in cur.fetchall()]
    finally:
        conn.close()

def esquecer_aprendizado(termo: str) -> int:
    termo = (termo or "").strip().lower()
    if not termo:
        return 0
    conn = _conectar()
    try:
        cur = conn.execute("DELETE FROM kael_learned_rules WHERE chave LIKE ? OR valor LIKE ?", (f"%{termo}%", f"%{termo}%"))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()

def resumo_contexto_aprendido(limite: int = 8) -> str:
    itens = listar_aprendizados(limite)
    if not itens:
        return ""
    linhas = [f"- [{i['categoria']}] {i['chave']} -> {i['valor']}" for i in itens]
    return "Preferências e regras aprendidas com o usuário:\n" + "\n".join(linhas)

def observar_e_aprender(frase: str) -> str:
    """
    Detecta ensinamentos explícitos e padrões implícitos nas falas do usuário.
    Retorna confirmação se foi um ensino direto, ou '' se aprendeu silenciosamente.
    """
    raw = (frase or "").strip()
    low = raw.lower()
    if not raw:
        return ""

    # 1. Ensino explícito de gatilho -> ação ("quando eu falar X, faz Y" / "sempre que eu disser X, Y")
    m_gatilho = re.search(
        r"(?:quando\s+eu\s+(?:falar|disser|pedir)|sempre\s+que\s+eu\s+(?:falar|disser|pedir))\s+[\"']?(.+?)[\"']?\s*(?:,|ent[ãa]o|voc[êe])\s*(.+)$",
        raw,
        re.IGNORECASE,
    )
    if m_gatilho:
        gatilho = m_gatilho.group(1).strip().lower()
        acao = m_gatilho.group(2).strip()
        salvar_aprendizado("atalho", f"frase:{gatilho}", acao)
        return f"Aprendido! Sempre que você disser **{gatilho}**, vou executar: *{acao}*."

    # 2. Ensino de apelido de contato ("apelido de X é Y" / "X no whatsapp é Y")
    m_apelido = re.search(
        r"(?:o\s+contato\s+|apelido\s+|chama\s+|salva\s+que\s+)?([a-zA-ZÀ-ÿ0-9_\s]{2,25})\s+(?:é|eh|no\s+whatsapp\s+é|significa)\s+([a-zA-ZÀ-ÿ0-9_+\s]{2,30})$",
        raw,
        re.IGNORECASE,
    )
    if m_apelido and any(p in low for p in ("contato", "apelido", "whatsapp", "zap", "salva que", "lembra que")):
        apelido = m_apelido.group(1).strip().lower()
        real = m_apelido.group(2).strip()
        salvar_aprendizado("contato", f"contato:{apelido}", real)
        return f"Anotei: **{apelido}** corresponde a **{real}**."

    # 3. Preferências explícitas ("lembra que...", "anota aí que...", "minha preferência é...", "prefiro...")
    m_pref = re.search(
        r"^(?:kael[,\s]+)?(?:lembra\s+que|lembre\s+que|anota\s+(?:a[íi]\s+)?que|guarda\s+que|minha\s+prefer[êe]ncia\s+[ée]|eu\s+prefiro)\s+(.+)$",
        raw,
        re.IGNORECASE,
    )
    if m_pref:
        regra = m_pref.group(1).strip().rstrip(".")
        chave = "pref:" + "_".join(regra.lower().split()[:4])
        salvar_aprendizado("preferencia", chave, regra)
        return f"Guardado na minha memória permanente: *{regra}*."

    # 4. Aprendizado silencioso de hábitos reais (ex: player preferido para música)
    m_player = re.search(r"\b(?:tocar|toca|ouvir|ouve|coloca|bota|p[õo]e)\b.+\b(?:no|na|pelo)\s+(brave|simpmusic|spotify|youtube)\b", low)
    if m_player:
        salvar_aprendizado("habito", "player_musica_padrao", m_player.group(1).lower())

    return ""



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


def aprender_de_codigo(caminho_arquivo: str, codigo: str, nota: str = "") -> str:
    """Extrai resumo estrutural leve de um codigo (.py, .lua, .luau, .html, etc.)
    e salva em kael_learned_rules para reuso futuro sem estourar o contexto."""
    texto = (codigo or "").strip()
    if not texto and caminho_arquivo and os.path.isfile(os.path.expanduser(caminho_arquivo)):
        with open(os.path.expanduser(caminho_arquivo), "r", encoding="utf-8", errors="replace") as f:
            texto = f.read().strip()
    if not texto:
        return ""

    arq_norm = (caminho_arquivo or "codigo_sem_nome").strip()
    ext = os.path.splitext(arq_norm)[1].lower()
    linhas = texto.splitlines()

    if ext == ".py":
        defs = re.findall(r"^\s*(?:async\s+)?def\s+([A-Za-z0-9_]+)\s*\(", texto, flags=re.M)
        classes = re.findall(r"^\s*class\s+([A-Za-z0-9_]+)\b", texto, flags=re.M)
        rotas = re.findall(r"@app\.route\(\s*['\"]([^'\"]+)['\"]", texto)
        partes = [f"py({len(linhas)}L)"]
        if classes:
            partes.append("classes:" + ",".join(classes[:6]))
        if defs:
            partes.append("fns:" + ",".join(defs[:10]))
        if rotas:
            partes.append("rotas:" + ",".join(rotas[:8]))
    elif ext in (".lua", ".luau"):
        fns = re.findall(r"(?:function\s+([A-Za-z0-9_.:]+)\s*\(|local\s+function\s+([A-Za-z0-9_]+)\s*\()", texto)
        nomes_fn = [a or b for a, b in fns if (a or b)]
        servicos = re.findall(r"GetService\(\s*['\"]([A-Za-z0-9_]+)['\"]\s*\)", texto)
        partes = [f"luau({len(linhas)}L)"]
        if servicos:
            partes.append("servicos:" + ",".join(dict.fromkeys(servicos))[:120])
        if nomes_fn:
            partes.append("fns:" + ",".join(dict.fromkeys(nomes_fn))[:160])
    else:
        partes = [f"{ext.lstrip('.') or 'cod'}({len(linhas)}L)"]

    if nota:
        partes.append("nota:" + re.sub(r"\s+", " ", nota.strip())[:140])

    resumo = " | ".join(partes)[:380]
    chave = f"codigo:{os.path.basename(arq_norm).lower()}"
    salvar_aprendizado("codigo", chave, resumo)
    return resumo

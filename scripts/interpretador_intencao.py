import json
import re
import urllib.request

RUIDOS_INICIAIS = re.compile(
    r"^(?:ei\s+kael|oi\s+kael|fala\s+kael|kael|por\s+favor|pfv|tem\s+como|pode|poderia|consegue|quero\s+que\s+voc[êe]|quero|queria|me\s+ajuda\s+a|faz\s+o\s+seguinte|ent[ãa]o|agora|a[íi])[,\s]+",
    re.IGNORECASE,
)

# Perguntas teóricas ou pedidos de explicação/resumo NÃO devem abrir apps externos sozinhos
EH_PERGUNTA_OU_ESTUDO = re.compile(
    r"^(?:como\s+(?:fazer|criar|funciona|usar|configurar|programar)|o\s+que\s+[ée]|quais\s+s[ãa]o|por\s+que|me\s+explica|explique|faz\s+um\s+resumo|resuma|resume|me\s+ensina|ensina|dicas\s+de)\b",
    re.IGNORECASE,
)

PEDE_TEXTO_NO_CHAT = re.compile(
    r"\b(?:resumo|resuma|resume|explica|explique|lista|liste|ensina|me\s+diz|me\s+fala|no\s+chat|detalha|detalhe|compara|compare)\b",
    re.IGNORECASE,
)

APPS_MIDIA = ("brave", "chrome", "navegador", "youtube", "simpmusic", "spotify")
APPS_PESQUISA = ("youtube", "brave", "chrome", "navegador", "google")
ALIASES_WA = r"(?:whatsapp|whats|zapzap|zap\s*zap|zap|wpp)"

def limpar_fala(frase: str) -> str:
    txt = (frase or "").strip()
    for _ in range(4):
        novo = RUIDOS_INICIAIS.sub("", txt).strip()
        if novo == txt:
            break
        txt = novo
    return txt

def quebrar_comandos_compostos(frase: str) -> list:
    """Separa comandos encadeados com 'e depois', 'e também', ou 'e <verbo de ação>'."""
    partes = re.split(
        r"\s+(?:e\s+depois|e\s+tamb[ée]m|depois|e\s+(?=(?:toca|tocar|abre|abrir|manda|mandar|envia|enviar|pesquisa|pesquisar|bota|coloca|avisa)))\s+",
        frase.strip(),
        flags=re.IGNORECASE,
    )
    return [p.strip() for p in partes if p.strip()]

def dissecar_local(frase: str, contexto: dict = None) -> dict:
    """
    Analisa uma única intenção em linguagem natural.
    Retorna: {intencao, app, contato, conteudo, falta}
    """
    contexto = contexto or {}
    raw = limpar_fala(frase)
    low = raw.lower()
    if not raw:
        return {"intencao": "desconhecida"}

    # 0. Se é claramente uma pergunta conceitual ou pedido de resumo/explicação no chat, vai para conversa/memória
    if EH_PERGUNTA_OU_ESTUDO.search(low) or (PEDE_TEXTO_NO_CHAT.search(low) and not re.search(r"\b(?:no|na|pelo)\s+(?:youtube|brave|chrome|whatsapp|zap)\b", low)):
        return {"intencao": "conversa_chat", "app": "", "contato": "", "conteudo": raw, "falta": ""}

    # Detecta app explícito citado na frase
    app_destino = ""
    m_app = re.search(
        r"\b(?:no|na|pelo|pela|via)\s+(brave|chrome|navegador|youtube|simpmusic|spotify|whatsapp|whats|zapzap|zap|wpp|pc|computador|windows)\b",
        low,
    )
    if m_app:
        app_destino = m_app.group(1).lower()

    # 1. WHATSAPP / RECADO PARA CONTATO
    eh_wa = bool(re.search(rf"\b{ALIASES_WA}\b", low))
    eh_recado = bool(re.search(r"\b(?:mandar|manda|enviar|envia|falar|fala|avisar|avisa|escrever|escreve|responder|responde)\b.*\b(?:para|pro|pra)\b", low))
    if eh_wa or eh_recado:
        # Resolve pronomes ("pra ele", "pra ela") usando o último contato do contexto
        m_pron = re.search(r"\b(?:para|pro|pra)\s+(?:ele|ela)\b", low)
        contato = ""
        if m_pron and contexto.get("ultimo_contato"):
            contato = contexto["ultimo_contato"]
        else:
            m_dest = re.search(
                rf"\b(?:para|pro|pra)\s+(?:o\s+|a\s+)?([a-zA-ZÀ-ÿ0-9_.\s]{{2,30}}?)(?:\s+(?:no|na|via|pelo)\s+{ALIASES_WA}|\s*(?:[:,-]|dizendo|falando|que)\b|$)",
                raw,
                re.IGNORECASE,
            )
            contato = m_dest.group(1).strip() if m_dest else ""

        m_txt = re.search(r"(?:[:,-]|dizendo|falando|que)\s*(.+)$", raw, re.IGNORECASE)
        conteudo = m_txt.group(1).strip() if m_txt else ""

        if not contato and not conteudo:
            return {"intencao": "whatsapp", "app": "whatsapp", "contato": "", "conteudo": "", "falta": "contato"}
        if contato and not conteudo:
            return {"intencao": "whatsapp", "app": "whatsapp", "contato": contato, "conteudo": "", "falta": "conteudo"}
        return {"intencao": "whatsapp", "app": "whatsapp", "contato": contato, "conteudo": conteudo, "falta": ""}

    # 2. MÚSICA / ÁUDIO (inclui "toca de novo", "outra dele")
    if re.search(r"\b(?:tocar|toca|colocar|coloca|botar|bota|p[õo]e|ouvir|ouve|escutar|escuta|play)\b", low) or re.search(r"\b(?:m[úu]sica|som|faixa|banda|álbum|album)\b", low):
        app_final = app_destino if app_destino in APPS_MIDIA else ""
        if re.search(r"\b(?:de\s+novo|novamente|repete|mesma)\b", low) and contexto.get("ultima_musica"):
            return {"intencao": "musica", "app": app_final, "contato": "", "conteudo": contexto["ultima_musica"], "falta": ""}

        sem_app = re.sub(r"\b(?:no|na|pelo|pela|via)\s+(?:brave|chrome|navegador|youtube|simpmusic|spotify)\b", "", raw, flags=re.IGNORECASE).strip()
        sem_intro = re.sub(
            r"^(?:na\s+verdade|s[óo]|apenas|primeiro|antes)[,\s]+",
            "",
            sem_app,
            flags=re.IGNORECASE,
        ).strip()
        conteudo = re.sub(
            r"^(?:tocar|toca|colocar|coloca|botar|bota|p[õo]e|ouvir|ouve|escutar|escuta|play)\s*(?:uma\s+|um\s+|a\s+|o\s+|algo\s+(?:de|do|da)\s+)?(?:m[úu]sica\s*(?:de|do|da)?\s*|som\s*(?:de|do|da)?\s*)?",
            "",
            sem_intro,
            flags=re.IGNORECASE,
        ).strip(" .!?")
        conteudo = re.sub(r"\s+(?:antes|a[íi]|ai|agora|por\s+favor)$", "", conteudo, flags=re.IGNORECASE).strip(" .!?")
        if not conteudo or conteudo.lower() in ("música", "musica", "som", "algo", "alguma coisa", "aí", "ai", "uma música", "um som", "antes", "agora"):
            return {"intencao": "musica", "app": app_final, "contato": "", "conteudo": "", "falta": "conteudo"}
        return {"intencao": "musica", "app": app_final, "contato": "", "conteudo": conteudo, "falta": ""}

    # 3. PESQUISA EM APP EXTERNO (somente se pediu app externo explicitamente)
    if app_destino in APPS_PESQUISA and re.search(r"\b(?:pesquisar|pesquisa|buscar|busca|procurar|procura|achar|acha|ver)\b", low):
        sem_app = re.sub(r"\b(?:no|na|pelo|pela|via)\s+(?:youtube|brave|chrome|navegador|google)\b", "", raw, flags=re.IGNORECASE).strip()
        conteudo = re.sub(
            r"^(?:pesquisar|pesquisa|buscar|busca|procurar|procura|achar|acha|ver)\s*(?:por\s+|sobre\s+)?",
            "",
            sem_app,
            flags=re.IGNORECASE,
        ).strip(" .!?")
        if not conteudo:
            return {"intencao": "pesquisa", "app": app_destino, "contato": "", "conteudo": "", "falta": "conteudo"}
        return {"intencao": "pesquisa", "app": app_destino, "contato": "", "conteudo": conteudo, "falta": ""}

    # 4. ABRIR APP (ANDROID OU PC WINDOWS)
    m_abrir = re.match(r"^(?:abrir|abre|iniciar|inicia|executar|executa|entrar\s+no|entrar\s+na)\s+(?:o\s+|a\s+|app\s+)?(.+)$", raw, re.IGNORECASE)
    if m_abrir:
        alvo = re.sub(r"\b(?:no\s+pc|no\s+computador|no\s+windows)\b", "", m_abrir.group(1), flags=re.IGNORECASE).strip(" .!?")
        if app_destino in ("pc", "computador", "windows") or re.search(r"\b(?:no\s+pc|no\s+computador|no\s+windows)\b", low):
            return {"intencao": "comando_pc", "app": "pc", "contato": "", "conteudo": alvo, "falta": ""}
        return {"intencao": "abrir_app", "app": alvo, "contato": "", "conteudo": alvo, "falta": ""}

    return {"intencao": "desconhecida"}

def dissecar_com_llm_fallback(frase: str) -> dict:
    """Usa o trabalhador externo apenas para gírias muito indiretas de ação cotidiana."""
    try:
        from scripts.executor_trabalhadores import tentar_executar_trabalhadores
        prompt = (
            "Classifique a frase do usuário em JSON puro (sem markdown):\n"
            '{"intencao":"musica|whatsapp|pesquisa|abrir_app|conversa_chat","app":"","contato":"","conteudo":"","falta":"contato|conteudo|"}\n'
            "Use 'conversa_chat' se for pergunta, resumo, conversa ou programação.\n"
            f"Frase: {frase}"
        )
        res = tentar_executar_trabalhadores(prompt, system_prompt="Classificador de intenção JSON objetivo.")
        txt = (res.get("reply") or "").strip() if isinstance(res, dict) else ""
        m_json = re.search(r"\{.*\}", txt, re.DOTALL)
        if m_json:
            dados = json.loads(m_json.group(0))
            if isinstance(dados, dict) and dados.get("intencao") in ("musica", "whatsapp", "pesquisa", "abrir_app", "conversa_chat"):
                return dados
    except Exception:
        pass
    return {"intencao": "conversa_chat"}

def interpretar_frase(frase: str, contexto: dict = None) -> dict:
    parsed = dissecar_local(frase, contexto=contexto)
    if parsed.get("intencao") != "desconhecida":
        return parsed
    if re.search(r"\b(?:avisa|fala|manda|bota|p[õo]e|toca|abre|procura|som|zap|msg|recado)\b", (frase or "").lower()):
        return dissecar_com_llm_fallback(frase)
    return {"intencao": "conversa_chat"}

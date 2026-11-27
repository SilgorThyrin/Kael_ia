import json
import os
import re
import time
from flask import Blueprint, jsonify, request
from scripts import controle_apps as ca
from scripts.interpretador_intencao import interpretar_frase, quebrar_comandos_compostos
from scripts import aprendizado_kael as ap
from scripts.permissoes_kael import listar_pendentes, solicitar_permissao

apps_bp = Blueprint("kael_apps_bp", __name__)
ESTADO_PATH = os.path.expanduser("~/Kael_ia/data/dialogo_estado.json")
CONTEXTO_PATH = os.path.expanduser("~/Kael_ia/data/contexto_curto.json")

RESUMO_FUNCOES_KAEL = (
    "Sou o Kael, engenheiro de software e arquiteto autônomo do seu ecossistema. Minhas funções ativas:\n"
    "1. **Criar, atualizar e manter jogos**: Roblox (Luau), Godot e Web em `~/Projetos/<nome_do_jogo>`.\n"
    "2. **Criar, atualizar e manter aplicativos**: Python, APIs, bots e ferramentas Web/Termux em `~/Projetos/<nome_do_app>`.\n"
    "3. **Pesquisar, resumir e memorizar assuntos (FTS5)**: organizo conhecimento por tema (gamedev, programação, culinária, cripto) no `kael_memory.db`.\n"
    "4. **Interpretar comandos naturais por voz ou texto**: entendo pedidos livres, compostos ou em passos seguidos para WhatsApp/Zap, músicas e apps Android.\n"
    "5. **Integração com PC Windows**: enfileiro comandos (`roblox_studio`, `vscode`, `navegador`, `sincronizar_aethelgard`) mediante confirmação."
)

def _ler_json_ttl(path: str, ttl: int) -> dict:
    try:
        if os.path.exists(path):
            st = json.loads(open(path, encoding="utf-8").read())
            if time.time() - float(st.get("ts", 0)) < ttl:
                return st
    except Exception:
        pass
    return {}

def _salvar_json_ttl(path: str, dados: dict):
    dados["ts"] = time.time()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(json.dumps(dados, ensure_ascii=False))

def _limpar_estado():
    if os.path.exists(ESTADO_PATH):
        try:
            os.remove(ESTADO_PATH)
        except Exception:
            pass

def _atualizar_contexto(**kwargs):
    ctx = _ler_json_ttl(CONTEXTO_PATH, 600)
    for k, v in kwargs.items():
        if v:
            ctx[k] = v
    _salvar_json_ttl(CONTEXTO_PATH, ctx)

def executar_acao_aprovada(resolvido: dict) -> dict:
    if not isinstance(resolvido, dict) or resolvido.get("status") != "approved":
        return {}
    acao = str(resolvido.get("acao") or "").strip()
    alvo = str(resolvido.get("alvo") or "").strip()
    if acao == "abrir_app_android" and alvo:
        return ca.abrir_app_android(alvo)
    if acao == "intent_app_android" and alvo:
        return ca.executar_intent_android(alvo)
    if acao == "comando_pc" and alvo:
        return ca.enfileirar_comando_pc(alvo)
    return {}

def _processar_unico_comando(raw: str, permitir_estado: bool = True) -> str:
    low = raw.lower().strip()
    if not low:
        return ""

    # -1. Aprendizado contínuo: consulta, esquecimento, ensino explícito e atalhos aprendidos
    if any(k in low for k in ("o que você aprendeu", "o que voce aprendeu", "oque você aprendeu", "oque voce aprendeu", "sua memória", "sua memoria", "regras aprendidas")):
        itens = ap.listar_aprendizados(15)
        if not itens:
            return "Ainda não registrei regras personalizadas. Você pode me ensinar dizendo, por exemplo: *\"Lembra que prefiro Python com FastAPI\"* ou *\"Quando eu falar modo trabalho, abre o vscode no pc\"*."
        linhas = [f"- **{i['chave']}** → {i['valor']} ({i['usos']}x)" for i in itens]
        return "Aqui está o que já aprendi com você:\n" + "\n".join(linhas)

    m_esq = re.match(r"^(?:kael[,\s]+)?(?:esquece|esquecer|apaga\s+da\s+mem[óo]ria)\s+(.+)$", low)
    if m_esq:
        qtd = ap.esquecer_aprendizado(m_esq.group(1).strip())
        return f"Removi {qtd} registro(s) relacionado(s) da memória." if qtd else "Não encontrei nada com esse termo na memória."

    resp_ensino = ap.observar_e_aprender(raw)
    if resp_ensino:
        return resp_ensino

    atalho_aprendido = ap.buscar_aprendizado(f"frase:{low}")
    if atalho_aprendido and atalho_aprendido.lower() != low:
        return _processar_unico_comando(atalho_aprendido, permitir_estado=permitir_estado)

    ctx = _ler_json_ttl(CONTEXTO_PATH, 600)
    estado = _ler_json_ttl(ESTADO_PATH, 180) if permitir_estado else {}

    # 0. Continuidade de conversa (com detecção de cancelamento ou troca de assunto)
    if estado:
        if any(c in low for c in ("cancelar", "cancela", "deixa pra la", "deixa pra lá", "esquece", "nao precisa", "não precisa", "para com isso")):
            _limpar_estado()
            return "Tudo bem, cancelei."

        # Se o usuário mudou de assunto ou corrigiu o destinatário no meio da pergunta ("na verdade manda pro João" / "toca música")
        nova_analise = interpretar_frase(raw, contexto=ctx)
        if nova_analise.get("intencao") not in ("conversa_chat", "desconhecida"):
            _limpar_estado()
            return _processar_unico_comando(raw, permitir_estado=False)

        etapa = estado.get("etapa", "")
        if etapa == "wa_aguardando_contato":
            _limpar_estado()
            contato_real = ap.buscar_aprendizado(f"contato:{low}") or raw
            num = ca.resolver_contato_whatsapp(contato_real)
            if not num:
                return f"Não encontrei '{raw}' na sua agenda. Qual é o número ou nome exato do contato?"
            _atualizar_contexto(ultimo_contato=raw)
            _salvar_json_ttl(ESTADO_PATH, {"etapa": "wa_aguardando_texto", "dest": raw, "num": num})
            return f"Qual mensagem você quer enviar para **{raw}**?"

        if etapa == "wa_aguardando_texto":
            dest = estado.get("dest", "")
            num = estado.get("num", "")
            _limpar_estado()
            _atualizar_contexto(ultimo_contato=dest)
            res = ca.executar_intent_android(f"whatsapp|{num}|{raw}")
            if res.get("ok"):
                return f"Abrindo o WhatsApp para **{dest}** com a mensagem: *{raw}*."
            return f"Não consegui abrir o WhatsApp: {res.get('error')}"

        if etapa == "musica_aguardando_query":
            app_hint = estado.get("app_hint") or ap.buscar_aprendizado("player_musica_padrao") or "brave"
            _limpar_estado()
            _atualizar_contexto(ultima_musica=raw)
            res = ca.executar_intent_android(f"musica|{app_hint}|{raw}")
            if res.get("ok"):
                return f"Tocando **{raw}** no **{app_hint}**."
            return f"Não consegui tocar '{raw}': {res.get('error')}"

        if etapa == "pesquisa_aguardando_query":
            alvo_app = estado.get("alvo_app", "youtube")
            _limpar_estado()
            res = ca.executar_intent_android(f"pesquisa|{alvo_app}|{raw}")
            return f"Pesquisando **{raw}** no **{alvo_app}**." if res.get("ok") else f"Erro na pesquisa: {res.get('error')}"

    # Consultas de identidade e apps
    if any(k in low for k in ("suas funções", "suas funcoes", "o que você faz", "o que voce faz", "suas capacidades", "quem é você", "quem e voce")):
        return RESUMO_FUNCOES_KAEL

    if any(k in low for k in ("listar apps", "quais apps", "apps instalados")):
        res = ca.listar_apps_android(False)
        amostra = ", ".join(res.get("pacotes", [])[:12])
        cmds_pc = ", ".join(ca.COMANDOS_PC_PERMITIDOS.keys())
        return f"Apps Android: {res.get('total', 0)} (amostra: {amostra}...). Comandos PC: {cmds_pc}."

    # Disseca a frase livre
    analise = interpretar_frase(raw, contexto=ctx)
    intencao = analise.get("intencao", "conversa_chat")
    falta = analise.get("falta", "")
    app_alvo = (analise.get("app") or "").strip()
    contato = (analise.get("contato") or "").strip()
    conteudo = (analise.get("conteudo") or "").strip()

    if intencao == "conversa_chat":
        return ""

    if intencao == "whatsapp":
        if falta == "contato" or not contato:
            _salvar_json_ttl(ESTADO_PATH, {"etapa": "wa_aguardando_contato"})
            return "Para qual contato você quer enviar a mensagem no WhatsApp?"
        contato_real = ap.buscar_aprendizado(f"contato:{contato.lower()}") or contato
        num = ca.resolver_contato_whatsapp(contato_real)
        if not num:
            return f"Não encontrei **{contato}** na sua agenda (verifique se o Termux:API tem permissão de Contatos)."
        _atualizar_contexto(ultimo_contato=contato)
        if falta == "conteudo" or not conteudo:
            _salvar_json_ttl(ESTADO_PATH, {"etapa": "wa_aguardando_texto", "dest": contato, "num": num})
            return f"Qual mensagem você quer enviar para **{contato}**?"
        res = ca.executar_intent_android(f"whatsapp|{num}|{conteudo}")
        if res.get("ok"):
            return f"Abrindo o WhatsApp para **{contato}** com a mensagem: *{conteudo}*."
        return f"Não consegui abrir o WhatsApp: {res.get('error')}"

    if intencao == "musica":
        player = app_alvo or ap.buscar_aprendizado("player_musica_padrao") or "brave"
        if falta == "conteudo" or not conteudo:
            _salvar_json_ttl(ESTADO_PATH, {"etapa": "musica_aguardando_query", "app_hint": player})
            return f"Qual música você quer ouvir no **{player}**?"
        _atualizar_contexto(ultima_musica=conteudo)
        res = ca.executar_intent_android(f"musica|{player}|{conteudo}")
        return f"Tocando **{conteudo}** no **{player}**." if res.get("ok") else f"Não consegui tocar '{conteudo}': {res.get('error')}"

    if intencao == "pesquisa":
        motor = app_alvo or "youtube"
        if falta == "conteudo" or not conteudo:
            _salvar_json_ttl(ESTADO_PATH, {"etapa": "pesquisa_aguardando_query", "alvo_app": motor})
            return f"O que você quer pesquisar no **{motor}**?"
        res = ca.executar_intent_android(f"pesquisa|{motor}|{conteudo}")
        return f"Pesquisando **{conteudo}** no **{motor}**." if res.get("ok") else f"Erro na pesquisa: {res.get('error')}"

    if intencao == "comando_pc":
        mapa = {"roblox studio": "roblox_studio", "roblox": "roblox_studio", "vscode": "vscode", "vs code": "vscode", "navegador": "navegador", "chrome": "navegador", "aethelgard": "sincronizar_aethelgard"}
        chave = mapa.get(conteudo.lower(), conteudo.lower().replace(" ", "_"))
        if chave not in ca.COMANDOS_PC_PERMITIDOS:
            return f"Comando '{conteudo}' fora da whitelist PC: {list(ca.COMANDOS_PC_PERMITIDOS.keys())}."
        perm = solicitar_permissao("comando_pc", chave, f"Enfileirar comando {chave} para PC")
        return f"Permissão necessária para PC Windows (id: {perm.get('id')}). Confirme no pop-up para '{chave}'."

    if intencao == "abrir_app" and conteudo:
        pacote = ca.resolver_pacote_android(conteudo)
        if not pacote:
            return f"App Android '{conteudo}' não encontrado."
        res = ca.abrir_app_android(pacote)
        return f"Abrindo **{pacote}**." if res.get("ok") else f"Falha ao abrir {pacote}: {res.get('error')}"

    return ""

def interceptar_chat_apps(user_message: str) -> str:
    raw = (user_message or "").strip()
    if not raw:
        return ""
    partes = quebrar_comandos_compostos(raw)
    if len(partes) <= 1:
        return _processar_unico_comando(raw, permitir_estado=True)

    respostas = []
    for p in partes:
        r = _processar_unico_comando(p, permitir_estado=False)
        if r:
            respostas.append(r)
    return "\n".join(respostas) if respostas else ""

@apps_bp.route("/apps/android", methods=["GET"])
def rota_apps_android():
    return jsonify(ca.listar_apps_android(request.args.get("refresh") == "1"))

@apps_bp.route("/apps/pc/fila", methods=["GET"])
def rota_fila_pc():
    return jsonify({"ok": True, "comandos": ca.listar_fila_pc(request.args.get("todos") != "1")})

def registrar_no_app(app):
    app.register_blueprint(apps_bp)

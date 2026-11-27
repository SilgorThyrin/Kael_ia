# -*- coding: utf-8 -*-
import os
import re
import json
import time
import sqlite3
import threading
import requests
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REGRAS_PATH = os.path.join(BASE_DIR, "Conhecimento", "regras_aprendidas.json")
OLLAMA_URL = "http://127.0.0.1:8080/api/generate"
MODELO_KAEL = "qwen3:8b"
MODELO_VISAO = "moondream"

# Funcoes/classes proibidas (API inventada). wait( e spawn( sao tratados
# por regex separada abaixo porque task.wait( e task.spawn( sao legitimas.
APIS_PROIBIDAS = [
    "SendPacket", "GetInventory", "GetPlayer", "SetHealth",
    "game.Players:GetPlayer",
]

SEMAFORO_GPU = threading.Lock()
LOCK_ESTADO = threading.RLock()
ESTADO = {
    "projeto_ativo": "Ecos_de_Aethelgard",
    "modo_auto": False,
    "status": "Ocioso",
    "fila_roblox": [],
    "mensagens_chat": [],
    "estado_jogo": {},
    "ultimo_comando": "",
    "ultima_resposta": "",
    "ultimo_pensamento": "",
}


def adicionar_mensagem_chat(autor, texto, pensamento="", codigo=""):
    with LOCK_ESTADO:
        ESTADO["mensagens_chat"].append({
            "id": int(time.time() * 1000),
            "hora": datetime.now().strftime("%H:%M:%S"),
            "autor": str(autor),
            "texto": str(texto),
            "pensamento": str(pensamento),
            "codigo": str(codigo),
        })
        ESTADO["mensagens_chat"] = ESTADO["mensagens_chat"][-60:]


def enfileirar_roblox(tarefa):
    with LOCK_ESTADO:
        ESTADO["fila_roblox"].append(tarefa)


def carregar_regras_formatadas():
    try:
        if os.path.exists(REGRAS_PATH):
            with open(REGRAS_PATH, "r", encoding="utf-8") as f:
                regras = json.load(f)
            return "\n".join([
                f"- {r['regra']}" for r in regras[-10:] if isinstance(r, dict)
            ])
    except Exception:
        pass
    return "Nenhuma."


def salvar_regra_aprendizado(regra, erro):
    try:
        regras = []
        if os.path.exists(REGRAS_PATH):
            with open(REGRAS_PATH, "r", encoding="utf-8") as f:
                regras = json.load(f)
        regras.append({
            "regra": regra,
            "erro": erro[:200],
            "timestamp": time.time(),
        })
        with open(REGRAS_PATH, "w", encoding="utf-8") as f:
            json.dump(regras[-30:], f, ensure_ascii=False)
    except Exception:
        pass


def chamar_ollama(prompt, temperatura=0.2, modelo=None):
    try:
        with SEMAFORO_GPU:
            resp = requests.post(
                OLLAMA_URL,
                json={
                    "model": modelo or MODELO_KAEL,
                    "prompt": str(prompt),
                    "stream": False,
                    "options": {
                        "num_ctx": 8192,
                        "temperature": float(temperatura),
                    },
                },
                timeout=600,
            )
            return str(resp.json().get("response", ""))
    except Exception as e:
        return "Erro Ollama: " + str(e)


def chamar_ollama_stream(prompt, temperatura=0.4):
    persona = (
        "Voce e o KAEL, um agente autonomo e engenheiro de software senior "
        "especialista em Roblox/Luau e criacao de jogos. "
        "Responda sempre em portugues do Brasil, de forma tecnica, direta e sem enrolacao. "
        "NUNCA diga que voce e o Qwen, Alibaba, IBM, Granite ou um modelo de linguagem. "
        "Voce e o Kael.\n\n"
        "TAREFA DO USUARIO: "
    )
    prompt_final = persona + prompt

    try:
        with SEMAFORO_GPU:
            resp = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODELO_KAEL,
                    "prompt": prompt_final,
                    "stream": True,
                    "options": {
                        "num_ctx": 4096,
                        "temperature": float(temperatura),
                    },
                },
                stream=True,
                timeout=600,
            )
            for line in resp.iter_lines():
                if line:
                    dados = json.loads(line.decode("utf-8"))
                    yield dados.get("response", "")
    except Exception as e:
        yield f"\n[Erro no Stream: {e}]"


def analisar_screenshot(imagem_b64, pergunta="Descreva a imagem e aponte erros visuais."):
    try:
        requests.post(
            OLLAMA_URL,
            json={"model": MODELO_KAEL, "keep_alive": 0},
        )
        with SEMAFORO_GPU:
            resp = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODELO_VISAO,
                    "prompt": pergunta,
                    "images": [imagem_b64],
                    "stream": False,
                    "options": {"num_ctx": 2048},
                },
                timeout=300,
            )
            return str(resp.json().get("response", ""))
    except Exception as e:
        return "Erro na Visao: " + str(e)


# ==========================================================
# NOVAS FUNCOES (v9.9) - antes faltavam, kael_core chamava e quebrava
# ==========================================================

def _extrair_codigo_lua(texto):
    """Extrai o primeiro bloco Lua de uma resposta do LLM."""
    m = re.search(
        r"```(?:lua|luau)?\s*\n(.*?)```",
        str(texto), re.DOTALL | re.IGNORECASE
    )
    if m:
        return m.group(1).strip()
    return None


def _checar_instance_sem_parent(codigo):
    """
    Detecta Instance.new(...) cuja variavel resultante nunca recebe .Parent.
    Esse e o bug classico em que a Part e criada mas nao aparece no jogo.
    Retorna lista de strings (erros). Nao corrige.
    """
    erros = []
    padrao = r'local\s+(\w+)\s*=\s*Instance\.new\(\s*["\'](\w+)["\']\s*\)'
    for m in re.finditer(padrao, codigo):
        var = m.group(1)
        tipo = m.group(2)
        # Busca var.Parent = em qualquer lugar do codigo
        if not re.search(rf'\b{re.escape(var)}\.Parent\s*=', codigo):
            erros.append(
                f'Instancia "{tipo}" ({var}) criada sem .Parent — '
                f'nao vai aparecer no jogo. Adicione `{var}.Parent = workspace`'
            )
    return erros


def validar_sintaxe_lua_pesada(codigo):
    """
    Valida codigo Lua gerado pelo LLM.
    Retorna (codigo_limpo, lista_de_erros).

    O que faz:
      - Remove fences ```lua ... ``` que sobrou
      - Detecta APIs proibidas (inventadas)
      - Detecta Instance.new sem Parent (objeto nao aparece no jogo)
      - Detecta wait()/spawn() obsoletos, mas aceita task.wait()/task.spawn()

    NAO reindenta. O Granite ja gera indentado; reindentar quebra
    estruturas de if/for/function aninhadas.
    """
    erros = []
    if not codigo or not isinstance(codigo, str):
        return ("", ["Codigo vazio ou invalido"])

    codigo = codigo.strip()

    # Remove fences de markdown que possam ter sobrado
    codigo = re.sub(r'^```(?:lua|luau)?\s*\n', '', codigo)
    codigo = re.sub(r'\n```\s*$', '', codigo)
    codigo = codigo.strip()

    # APIs proibidas (inventadas ou especificas)
    for api in APIS_PROIBIDAS:
        if api in codigo:
            erros.append(f"API proibida detectada: {api}")

    # Instance.new sem Parent
    erros.extend(_checar_instance_sem_parent(codigo))

    # wait( obsoleto — aceita task.wait(
    if re.search(r'(?<!task\.)\bwait\s*\(', codigo):
        erros.append("Uso de wait() — substitua por task.wait()")

    # spawn( obsoleto — aceita task.spawn(
    if re.search(r'(?<!task\.)\bspawn\s*\(', codigo):
        erros.append("Uso de spawn() — substitua por task.spawn()")

    # ---- Deteccoes extras (v9.9.1) baseadas nos bugs dos 4 modelos testados ----

    # Bug 3: math.random() com argumento float (deve ser inteiro)
    for m in re.finditer(
        r'math\.random\(\s*([A-Za-z_]\w*\.Position\.[XYZ]|[A-Za-z_]\w*\.magnitude)\s*[,)]',
        codigo
    ):
        erros.append(
            "math.random() com argumento float — use math.floor(var) antes "
            "ou math.random() sem args para 0-1"
        )
        break

    # Bug 6: FindFirstChildOfClass("SpawnLocation") sem fallback recursivo
    if ('FindFirstChildOfClass("SpawnLocation")' in codigo
            or "FindFirstChildOfClass('SpawnLocation')" in codigo):
        tem_fallback = ("GetDescendants" in codigo and "SpawnLocation" in codigo
                        and codigo.index("GetDescendants") < codigo.index("SpawnLocation"))
        if not tem_fallback:
            erros.append(
                "FindFirstChildOfClass(\"SpawnLocation\") nao e recursivo. "
                "Se o SpawnLocation estiver dentro de um Model, retorna nil. "
                "Use GetDescendants() como fallback."
            )

    # Bug 12: Name:match("literal") sem string.lower (case-sensitive)
    for m in re.finditer(r':match\(\s*["\']([A-Za-z]+)["\']', codigo):
        palavra = m.group(1)
        # Se nao tem string.lower(Name) antes do match, e case-sensitive
        if "string.lower" not in codigo:
            erros.append(
                f'Name:match("{palavra}") e case-sensitive. '
                "Use string.find(string.lower(Name), string.lower(\"" + palavra + "\"))"
            )
            break

    # Bug 11: Acesso a PrimaryPart.Position sem garantir PrimaryPart antes
    if re.search(r'\.PrimaryPart\.(Position|CFrame)', codigo):
        # Aceita se ha "PrimaryPart =" em algum lugar ANTES do primeiro acesso
        primeiro_acesso = re.search(r'\.PrimaryPart\.(Position|CFrame)', codigo).start()
        atribuicao = re.search(r'\.PrimaryPart\s*=', codigo[:primeiro_acesso])
        if not atribuicao:
            erros.append(
                "Acesso a .PrimaryPart.Position/.CFrame antes de garantir "
                "que PrimaryPart existe. Defina PrimaryPart antes ou use nil-check."
            )

    # Bug 4: while/while-not sem contador de seguranca
    if re.search(r'\bwhile\s+(not\s+)?[\w.]+\s*(==\s*false)?\s*do', codigo):
        # Heuristica: tem for i=1 no corpo? tem contador local?
        if not re.search(r'for\s+\w+\s*=\s*1\s*,\s*\d+', codigo):
            if "attempts" not in codigo.lower() and "contador" not in codigo.lower():
                erros.append(
                    "while sem contador de seguranca — pode loop infinito se a "
                    "condicao nunca for satisfeita. Adicione 'for attempts = 1, 100 do' "
                    "ou similar."
                )

    return (codigo, erros)


def validar_codigo_lua(codigo):
    """
    Wrapper leve chamado pelo GameDirector e GameIntegrator.
    Retorna (valido: bool, erros: list).

    Diferenca para validar_sintaxe_lua_pesada: nao tenta corrigir, so valida.
    """
    codigo_limpo, erros = validar_sintaxe_lua_pesada(codigo)
    return (len(erros) == 0, erros)


def gerar_codigo_dual(prompt, temperatura=0.3, **kwargs):
    """
    v9.9 - Single-pass (Opcao A aplicada).
    Antes existia um segundo passe de QA via LLM que alucinava bugs.
    Agora so gera uma vez e extrai o codigo Lua.

    Retorna string com o codigo Lua puro (sem markdown).
    Se falhar na extracao, retorna o texto cru da resposta.
    """
    try:
        resposta = chamar_ollama(prompt, temperatura=temperatura)
        if not resposta or resposta.startswith("Erro Ollama"):
            return resposta

        codigo = _extrair_codigo_lua(resposta)
        if codigo:
            return codigo
        # LLM nao retornou em bloco ```lua — tenta usar o texto inteiro
        # (as vezes o modelo so cospe o codigo direto sem markdown)
        if re.search(r'\b(local|function|if|for|while)\b', resposta):
            return resposta.strip()
        return resposta
    except Exception as e:
        return f"-- Erro em gerar_codigo_dual: {e}"
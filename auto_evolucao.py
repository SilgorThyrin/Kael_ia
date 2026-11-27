import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BASE_DIR = Path.home() / "Kael_ia"
PENDENTE_FILE = BASE_DIR / "data" / "auto_patch_pendente.json"

GATILHOS_AUTO_INSPECAO = (
    "seu chat",
    "teu chat",
    "melhorar o chat",
    "melhore o chat",
    "melhorar seu chat",
    "melhore seu chat",
    "sua interface",
    "kael_chat.html",
    "chat web",
    "proprio chat",
    "próprio chat",
    "proprio codigo",
    "próprio código",
    "modal",
    "layout do chat",
)

GATILHOS_APLICAR = (
    "aplicar melhoria",
    "aplicar patch",
    "confirmar melhoria",
    "pode aplicar no chat",
)


def eh_pedido_auto_evolucao(prompt: str) -> bool:
    p = prompt.lower()
    return any(g in p for g in GATILHOS_AUTO_INSPECAO)


def _tem_patch_pendente() -> bool:
    """Verifica se existe patch pendente salvo em disco."""
    import json
    from pathlib import Path
    candidatos = [
        Path("data/auto_patch_pendente.json"),
        Path.home() / "Kael_ia" / "data" / "auto_patch_pendente.json",
    ]
    for p in candidatos:
        try:
            if p.exists() and p.stat().st_size > 2:
                raw = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(raw, list) and len(raw) > 0:
                    return True
                if isinstance(raw, dict) and (raw.get("patches") or raw.get("arquivo") or raw.get("buscar") is not None):
                    return True
        except Exception:
            continue
    return False


def eh_confirmacao_aplicar(texto: str) -> bool:
    """Aceita frases naturais de confirmação quando há patch pendente."""
    if not isinstance(texto, str):
        return False
    t = " ".join(texto.strip().lower().split())
    if not t:
        return False

    exatas_ou_curtas = {
        "aplicar melhoria",
        "aplicar patch",
        "aplicar",
        "aplica",
        "pode aplicar",
        "manda ver",
        "faz isso",
        "implementa",
        "implementa isso",
        "implementa no codigo",
        "implementa no código",
        "implementa e testa",
        "implementa no codigo e testa",
        "implementa no código e testa",
        "implementa as melhorias",
        "implementa as melhorias no chat",
        "confirma",
        "confirmar",
        "sim",
        "ok",
    }
    if t in exatas_ou_curtas:
        return True

    if not _tem_patch_pendente():
        return False

    # Evita capturar perguntas novas ou pedidos de análise do zero
    if "?" in t or any(p in t for p in ("analise", "analisa", "explica", "por que", "qual ", "como ")):
        return False

    gatilhos_patch = (
        "aplicar",
        "aplica",
        "implementa",
        "manda ver",
        "faz isso",
        "gravar patch",
        "salva isso",
        "salvar isso",
    )
    return any(g in t for g in gatilhos_patch)



def _extrair_trechos_relevantes(arquivo: Path, prompt: str, max_chars: int = 4500) -> str:
    if not arquivo.exists():
        return f"[Arquivo não encontrado: {arquivo}]"

    conteudo = arquivo.read_text(encoding="utf-8", errors="replace")
    if len(conteudo) <= max_chars:
        return conteudo

    linhas = conteudo.splitlines()
    palavras = [
        w for w in re.findall(r"[a-zA-Z0-9_]{4,}", prompt.lower())
        if w not in ("chat", "kael", "melhorar", "melhore", "fazer", "quero", "pode", "como")
    ]

    indices_hit: List[int] = []
    for idx, ln in enumerate(linhas):
        low = ln.lower()
        if any(w in low for w in palavras):
            indices_hit.append(idx)

    # Sempre inclui o topo (estrutura/head/rotas) + o final (scripts/JS/rotas finais)
    blocos: List[str] = []
    topo = "\n".join(linhas[:45])
    blocos.append(f"--- TOPO ({arquivo.name} linhas 1-90) ---\n{topo}")

    usados = set(range(0, min(90, len(linhas))))
    for hit in indices_hit[:3]:
        ini = max(0, hit - 25)
        fim = min(len(linhas), hit + 35)
        if any(i not in usados for i in range(ini, fim)):
            for i in range(ini, fim):
                usados.add(i)
            trecho = "\n".join(f"{i+1}: {linhas[i]}" for i in range(ini, fim))
            blocos.append(f"--- TRECHO ({arquivo.name} linhas {ini+1}-{fim}) ---\n{trecho}")

    ini_fim = max(90, len(linhas) - 110)
    if ini_fim < len(linhas):
        rodape = "\n".join(f"{i+1}: {linhas[i]}" for i in range(ini_fim, len(linhas)))
        blocos.append(f"--- FINAL ({arquivo.name} linhas {ini_fim+1}-{len(linhas)}) ---\n{rodape}")

    junto = "\n\n".join(blocos)
    return junto[:max_chars]


def montar_contexto_auto_evolucao(prompt: str) -> str:
    """Lê o código real do chat/API do Kael para o trabalhador não responder no escuro."""
    if not eh_pedido_auto_evolucao(prompt):
        return ""

    html_path = BASE_DIR / "templates" / "kael_chat.html"
    api_path = BASE_DIR / "api_server.py"

    trecho_html = _extrair_trechos_relevantes(html_path, prompt, max_chars=5000)
    trecho_api = _extrair_trechos_relevantes(api_path, prompt, max_chars=2500)

    return (
        "\n\n=== AUTO-INSPEÇÃO REAL DO KAEL (~/Kael_ia) ===\n"
        "Arquitetura real do Kael:\n"
        "- Interface Web do Chat: ~/Kael_ia/templates/kael_chat.html\n"
        "- Servidor Flask / Rotas SSE: ~/Kael_ia/api_server.py (porta 8000)\n"
        "- Motor Local (Cofre): llama-server (porta 8080)\n"
        "- Roteador de APIs Externas: ~/Kael_ia/roteador_trabalhadores.py e ~/Kael_ia/executor_trabalhadores.py\n\n"
        f"[Código atual de templates/kael_chat.html]\n{trecho_html}\n\n"
        f"[Trechos relevantes de api_server.py]\n{trecho_api}\n\n"
        "INSTRUÇÃO OBRIGATÓRIA PARA MELHORIAS NO PRÓPRIO CHAT:\n"
        "1. Baseie-se EXCLUSIVAMENTE no código real acima (não invente IDs, classes ou rotas inexistentes).\n"
        "2. Entregue a solução objetiva em blocos exatos no formato:\n"
        "ARQUIVO: templates/kael_chat.html (ou api_server.py)\n"
        "<<<BUSCAR>>>\n(trecho exato atual que existe no arquivo)\n"
        "<<<SUBSTITUIR>>>\n(novo código melhorado)\n"
        "<<<FIM>>>\n"
        "3. Ao final, avise que o usuário pode digitar 'aplicar melhoria' para aplicar o patch com backup automático.\n"
    )


def salvar_patch_se_houver(resposta_texto: str) -> Optional[str]:
    """Extrai blocos <<<BUSCAR>>> / <<<SUBSTITUIR>>> da resposta e salva como pendente."""
    padrao = re.compile(
        r"ARQUIVO:\s*([^\n\r]+)\s*<<<BUSCAR>>>\s*(.*?)\s*<<<SUBSTITUIR>>>\s*(.*?)\s*<<<FIM>>>",
        re.DOTALL,
    )
    matches = padrao.findall(resposta_texto)
    if not matches:
        return None

    patches = []
    for arq_rel, buscar, substituir in matches:
        arq_limpo = arq_rel.strip().replace("~/Kael_ia/", "").lstrip("/")
        patches.append(
            {
                "arquivo": arq_limpo,
                "buscar": buscar,
                "substituir": substituir,
            }
        )

    PENDENTE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PENDENTE_FILE.write_text(
        json.dumps(
            {"criado_em": datetime.now().isoformat(), "patches": patches},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return f"{len(patches)} patch(es) pronto(s) em {PENDENTE_FILE.name}. Digite 'aplicar melhoria' para gravar com backup."


def aplicar_patch_pendente() -> Tuple[bool, str]:
    """Aplica o último patch salvo com backup .bak_auto e validação de sintaxe."""
    if not PENDENTE_FILE.exists():
        return False, "Nenhuma melhoria pendente encontrada. Peça primeiro uma melhoria no chat."

    try:
        dados = json.loads(PENDENTE_FILE.read_text(encoding="utf-8"))
        patches = dados.get("patches") or []
    except Exception as exc:
        return False, f"Erro ao ler patch pendente: {exc}"

    if not patches:
        return False, "Arquivo de patch pendente está vazio."

    permitidos = {
        "templates/kael_chat.html",
        "api_server.py",
        "personalidade_kael.json",
        "roteador_trabalhadores.py",
        "executor_trabalhadores.py",
    }

    aplicados: List[str] = []
    for item in patches:
        rel = str(item.get("arquivo") or "").strip()
        if rel not in permitidos:
            return False, f"Arquivo não permitido para auto-patch: {rel}"

        alvo = (BASE_DIR / rel).resolve()
        if not str(alvo).startswith(str(BASE_DIR.resolve())) or not alvo.exists():
            return False, f"Caminho inválido ou inexistente: {rel}"

        conteudo = alvo.read_text(encoding="utf-8")
        buscar = item.get("buscar", "")
        substituir = item.get("substituir", "")

        if buscar not in conteudo:
            return False, f"Trecho <<<BUSCAR>>> não encontrado exatamente em {rel}. Peça ao Kael para gerar novamente."

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = alvo.with_name(f"{alvo.name}.bak_auto_{ts}")
        shutil.copy2(alvo, backup)

        novo_conteudo = conteudo.replace(buscar, substituir, 1)
        alvo.write_text(novo_conteudo, encoding="utf-8")

        # Validação rápida de sintaxe se for Python ou JSON
        if alvo.suffix == ".py":
            import py_compile
            try:
                py_compile.compile(str(alvo), doraise=True)
            except Exception as exc_py:
                shutil.copy2(backup, alvo)
                return False, f"Patch revertido: erro de sintaxe Python em {rel}: {exc_py}"
        elif alvo.suffix == ".json":
            try:
                json.loads(novo_conteudo)
            except Exception as exc_js:
                shutil.copy2(backup, alvo)
                return False, f"Patch revertido: JSON inválido em {rel}: {exc_js}"

        aplicados.append(f"{rel} (backup: {backup.name})")

    PENDENTE_FILE.unlink(missing_ok=True)
    return True, "Melhoria aplicada com sucesso em: " + ", ".join(aplicados)

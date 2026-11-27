import json
import os
import sys
import time
from pathlib import Path
import requests

BASE_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR / ".env"

if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MODEL = "gemini-3.5-flash-lite"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"



def _post_gemini(headers: dict, payload: dict, timeout=(10, 75)):
    fila = [MODEL] + [m for m in (
        "gemini-3.1-flash-lite",
        "gemini-3.7-flash",
        "gemini-3.8-flash",
        "gemini-4-hydrogen",
        "gemini-3.5-flash",
    ) if m != MODEL]
    resp = None
    last_err = None
    for idx, modelo in enumerate(fila):
        if idx > 0:
            espera = min(2 * idx, 8)
            print(f"⏳ Tentando {modelo} em {espera}s...")
            time.sleep(espera)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code not in (404, 429, 503):
                return resp
            last_err = f"HTTP {resp.status_code}"
        except requests.RequestException as exc:
            last_err = str(exc)
            print(f"⚠️ Timeout/erro em {modelo}: {exc}")
    if resp is None:
        raise RuntimeError(f"Todos os modelos falharam: {last_err}")
    return resp

def resolver_seguro(root: Path, rel_path: str) -> Path:
    alvo = (root / rel_path).resolve()
    if alvo != root and root not in alvo.parents:
        raise ValueError("Caminho fora da pasta do projeto.")
    if alvo.name == ".env":
        raise ValueError("Acesso ao arquivo .env bloqueado por segurança.")
    return alvo


def main():
    if not API_KEY:
        print("Erro: configure GEMINI_API_KEY no arquivo .env.")
        sys.exit(1)

    auto_mode = "--auto" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--auto"]
    projeto = Path(args[0] if args else Path.home() / "Projetos" / "Ecos_de_Aethelgard").resolve()

    if not projeto.exists():
        print(f"Pasta não encontrada: {projeto}")
        sys.exit(1)

    print(f"🤖 Agente de Código ativo em: {projeto}")
    print(f"Modo: {'AUTÔNOMO (grava direto)' if auto_mode else 'SUPERVISIONADO (pede s/N)'}")
    print("Digite 'sair' para encerrar.\n")

    def listar_arquivos() -> list[str]:
        ignorados = {".git", "__pycache__", "node_modules", ".venv"}
        arquivos = []
        for p in projeto.rglob("*"):
            if any(part in ignorados for part in p.parts):
                continue
            if p.is_file() and p.name != ".env":
                arquivos.append(str(p.relative_to(projeto)))
        return sorted(arquivos)[:150]

    def ler_arquivo(caminho: str) -> str:
        alvo = resolver_seguro(projeto, caminho)
        if not alvo.is_file():
            return f"Erro: '{caminho}' não existe."
        return alvo.read_text(encoding="utf-8", errors="replace")[:60000]

    def escrever_arquivo(caminho: str, conteudo: str) -> dict:
        alvo = resolver_seguro(projeto, caminho)
        if not auto_mode:
            resp = input(f"\n⚠️ O agente quer alterar '{caminho}' ({len(conteudo)} chars). Aplicar? [s/N]: ")
            if resp.strip().lower() != "s":
                return {"status": "recusado_pelo_usuario"}
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(conteudo, encoding="utf-8")
        print(f"✅ Salvo: {caminho}")
        return {"status": "salvo", "caminho": caminho}

    def editar_trecho(caminho: str, trecho_antigo: str, trecho_novo: str) -> dict:
        alvo = resolver_seguro(projeto, caminho)
        if not alvo.is_file():
            return {"erro": f"Arquivo '{caminho}' não encontrado."}
        conteudo = alvo.read_text(encoding="utf-8")
        ocorrencias = conteudo.count(trecho_antigo)
        if ocorrencias == 0:
            return {"erro": "trecho_antigo não encontrado exatamente no arquivo."}
        if ocorrencias > 1:
            return {"erro": f"trecho_antigo aparece {ocorrencias} vezes; inclua mais linhas de contexto."}
        if not auto_mode:
            resp = input(f"\n⚠️ O agente quer editar trecho em '{caminho}'. Aplicar? [s/N]: ")
            if resp.strip().lower() != "s":
                return {"status": "recusado_pelo_usuario"}
        alvo.write_text(conteudo.replace(trecho_antigo, trecho_novo, 1), encoding="utf-8")
        print(f"✅ Editado: {caminho}")
        return {"status": "editado", "caminho": caminho}

    tool_map = {
        "listar_arquivos": listar_arquivos,
        "ler_arquivo": ler_arquivo,
        "escrever_arquivo": escrever_arquivo,
        "editar_trecho": editar_trecho,
    }

    tools_decl = [{
        "function_declarations": [
            {
                "name": "listar_arquivos",
                "description": "Lista os arquivos do projeto.",
                "parameters": {"type": "OBJECT", "properties": {}},
            },
            {
                "name": "ler_arquivo",
                "description": "Lê o conteúdo de um arquivo do projeto.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {"caminho": {"type": "STRING"}},
                    "required": ["caminho"],
                },
            },
            {
                "name": "escrever_arquivo",
                "description": "Cria ou sobrescreve um arquivo com o código completo atualizado.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "caminho": {"type": "STRING"},
                        "conteudo": {"type": "STRING"},
                    },
                    "required": ["caminho", "conteudo"],
                },
            },
            {
                "name": "editar_trecho",
                "description": "Substitui um trecho exato de código em um arquivo existente (preferir em arquivos grandes).",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "caminho": {"type": "STRING"},
                        "trecho_antigo": {"type": "STRING"},
                        "trecho_novo": {"type": "STRING"},
                    },
                    "required": ["caminho", "trecho_antigo", "trecho_novo"],
                },
            },
        ]
    }]

    system = (
        "Você é um engenheiro de software autônomo. Antes de editar qualquer código, "
        "use listar_arquivos e ler_arquivo para entender o projeto real. Ao modificar, "
        "prefira editar_trecho em arquivos existentes e use escrever_arquivo apenas para arquivos novos ou pequenos e explique brevemente o que alterou."
    )

    while True:
        pedido = input("\nVocê > ").strip()
        if not pedido:
            continue
        if pedido.lower() in {"sair", "exit", "quit"}:
            break

        contents = [{"role": "user", "parts": [{"text": pedido}]}]
        headers = {"Content-Type": "application/json", "x-goog-api-key": API_KEY}

        for _ in range(15):
            payload = {
                "system_instruction": {"parts": [{"text": system}]},
                "contents": contents,
                "tools": tools_decl,
                "generationConfig": {"temperature": 0.2},
            }
            try:
                r = _post_gemini(headers, payload, timeout=(10, 75))
            except Exception as exc:
                print(f"Erro de conexão: {exc}")
                break
            if not r.ok:
                print(f"Erro API ({r.status_code}): {r.text}")
                break

            candidate = r.json()["candidates"][0]["content"]
            parts = candidate.get("parts", [])
            calls = [p["functionCall"] for p in parts if "functionCall" in p]

            if not calls:
                texto = "".join(p.get("text", "") for p in parts).strip()
                print(f"\nAgente > {texto}")
                break

            contents.append(candidate)
            respostas = []
            for call in calls:
                nome = call["name"]
                kwargs = call.get("args", {})
                print(f"🔧 [{nome}] {kwargs.get('caminho', '')}")
                try:
                    res = tool_map[nome](**kwargs)
                except Exception as exc:
                    res = {"erro": str(exc)}
                respostas.append({
                    "functionResponse": {"name": nome, "response": {"result": res}}
                })
            contents.append({"role": "user", "parts": respostas})
        else:
            print("\n⚠️ Limite de passos atingido antes de concluir. Diga \"continue\" ou reduza os arquivos.")


if __name__ == "__main__":
    main()

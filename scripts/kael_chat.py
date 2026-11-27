"""Chat de terminal estilo VC Coder para o Kael (llama.cpp :8080 ou API :8000)."""
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
import requests

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

BASE_DIR = Path.home() / "Kael_ia"
API_URL = "http://127.0.0.1:8000"
LLAMA_URL = "http://127.0.0.1:8080"

SYSTEM_PROMPT = (
    "Você é Kael no modo VC Coder: um assistente de engenharia de software e game dev "
    "direto, técnico e objetivo em português. Use apenas os arquivos, caminhos e fatos "
    "fornecidos no contexto; nunca invente caminhos inexistentes nem entregue código "
    "genérico de exemplo quando o usuário pedir revisão real do projeto."
)


def snapshot_workspace(max_files: int = 80) -> str:
    """Coleta resumo real dos arquivos e pastas de ~/Kael_ia."""
    if not BASE_DIR.exists():
        return f"Pasta {BASE_DIR} não encontrada."

    ignore_dirs = {"__pycache__", ".git", ".venv", "venv", "node_modules"}
    entries = []
    for root, dirs, files in os.walk(BASE_DIR):
        dirs[:] = sorted([d for d in dirs if d not in ignore_dirs])
        for fname in sorted(files):
            if fname.endswith((".pyc", ".log")):
                continue
            fpath = Path(root) / fname
            rel = fpath.relative_to(BASE_DIR)
            try:
                size_kb = fpath.stat().st_size / 1024
                entries.append(f"- {rel} ({size_kb:.1f} KB)")
            except OSError:
                entries.append(f"- {rel}")
            if len(entries) >= max_files:
                break
        if len(entries) >= max_files:
            break

    header = f"Diretório base: {BASE_DIR} (total listado: {len(entries)} arquivos)"
    return header + "\n" + "\n".join(entries)


def chat_via_api(mensagem: str) -> str | None:
    try:
        r = requests.post(
            f"{API_URL}/chat",
            json={"mensagem": mensagem, "prompt": mensagem},
            timeout=90,
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("response") or data.get("resposta") or str(data)
    except Exception:
        return None
    return None


def chat_via_llama_stream(historico: list[dict]) -> str | None:
    payload = {
        "messages": historico,
        "stream": True,
        "temperature": 0.25,
    }
    try:
        with requests.post(
            f"{LLAMA_URL}/v1/chat/completions",
            json=payload,
            stream=True,
            timeout=120,
        ) as r:
            r.raise_for_status()
            chunks = []
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                raw = line[6:].strip()
                if raw == "[DONE]":
                    break
                obj = json.loads(raw)
                delta = obj.get("choices", [{}])[0].get("delta", {}).get("content", "")
                if delta:
                    print(delta, end="", flush=True)
                    chunks.append(delta)
            print()
            return "".join(chunks)
    except Exception as e:
        print(f"\n[Erro llama-server :8080]: {e}")
        return None


def run_shell(cmd_str: str):
    if not cmd_str.strip():
        print("Uso: /cmd <comando>")
        return
    try:
        args = shlex.split(cmd_str)
        res = subprocess.run(args, cwd=str(BASE_DIR), text=True, capture_output=True, timeout=60)
        if res.stdout:
            print(res.stdout.rstrip())
        if res.stderr:
            print(res.stderr.rstrip())
        if res.returncode != 0:
            print(f"[exit {res.returncode}]")
    except Exception as e:
        print(f"[Erro ao executar]: {e}")


def read_file_cmd(rel_path: str):
    if not rel_path.strip():
        print("Uso: /ler <caminho_relativo_ou_absoluto>")
        return
    p = Path(rel_path.strip()).expanduser()
    if not p.is_absolute():
        p = BASE_DIR / p
    if not p.is_file():
        print(f"[Arquivo não encontrado]: {p}")
        return
    content = p.read_text(encoding="utf-8", errors="replace")
    print(f"--- {p} ({len(content.splitlines())} linhas) ---")
    print(content[:4000])
    if len(content) > 4000:
        print("... [truncado no terminal] ...")


def extract_best_code_block(text: str) -> str:
    blocks = []
    parts = text.split("```")
    for idx in range(1, len(parts), 2):
        raw_block = parts[idx]
        lines = raw_block.splitlines()
        if lines and len(lines[0].strip().split()) == 1 and lines[0].strip().isalpha():
            lines = lines[1:]
        cleaned = "\n".join(lines).strip()
        if cleaned:
            blocks.append(cleaned)
    if blocks:
        return max(blocks, key=len)
    return text.strip()


def save_code_cmd(arg: str, last_reply: str):
    target = arg.strip() or "data/luau_drafts/rascunho_kael.lua"
    p = Path(target).expanduser()
    if not p.is_absolute():
        p = BASE_DIR / p
    code = extract_best_code_block(last_reply)
    if not code:
        print("[Nada para salvar na última resposta]")
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(code + "\n", encoding="utf-8")
    print(f"[Salvo]: {p}")


def print_help():
    print(
        "Comandos VC Coder:\n"
        "  /ajuda               Mostra esta ajuda\n"
        "  /revisar             Lista arquivos reais da pasta e pede melhorias objetivas\n"
        "  /diag                Roda scripts/diagnostico_kael.py\n"
        "  /luau <arquivo>      Valida script Luau com scripts/validar_luau.py\n"
        "  /ler <arquivo>       Exibe conteúdo de um arquivo\n"
        "  /salvar [arquivo]    Salva o maior bloco de código da última resposta\n"
        "  /cmd <comando>       Executa comando no diretório ~/Kael_ia\n"
        "  /limpar              Limpa histórico da conversa\n"
        "  /sair                Encerra o chat"
    )


def main():
    use_api = "--api" in sys.argv
    historico = [{"role": "system", "content": SYSTEM_PROMPT}]
    last_reply = ""

    print("=== KAEL VC CODER (terminal) ===")
    print(f"Backend: {'Kael API (:8000)' if use_api else 'llama.cpp (:8080)'} | Digite /ajuda")

    while True:
        try:
            entrada = input("\nkael> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSaindo...")
            break

        if not entrada:
            continue
        if entrada in ("/sair", "/exit"):
            break
        if entrada in ("/ajuda", "/help"):
            print_help()
            continue
        if entrada in ("/limpar", "/clear"):
            historico = historico[:1]
            print("[Contexto limpo]")
            continue
        if entrada == "/diag":
            run_shell("python3 scripts/diagnostico_kael.py")
            continue
        if entrada.startswith("/luau "):
            alvo = entrada[6:].strip()
            run_shell(f"python3 scripts/validar_luau.py {shlex.quote(alvo)}")
            continue
        if entrada.startswith("/ler "):
            read_file_cmd(entrada[5:])
            continue
        if entrada == "/salvar" or entrada.startswith("/salvar "):
            sub = entrada[7:] if entrada.startswith("/salvar ") else ""
            save_code_cmd(sub, last_reply)
            continue
        if entrada.startswith("/cmd "):
            run_shell(entrada[5:])
            continue

        prompt_enviado = entrada
        if entrada == "/revisar":
            print("\n" + snapshot_workspace())
            continue
        if "pasta" in entrada.lower():
            snap = snapshot_workspace()
            prompt_enviado = (
                f"{entrada}\n\n[INVENTÁRIO REAL DA PASTA]\n{snap}\n"
                "Liste melhorias concretas baseadas apenas nos arquivos acima."
            )

        if use_api:
            resp = chat_via_api(prompt_enviado)
            if resp is not None:
                last_reply = resp
                print(f"\n{resp}")
            else:
                historico.append({"role": "user", "content": prompt_enviado})
                print()
                reply = chat_via_llama_stream(historico)
                if reply:
                    last_reply = reply
                    historico.append({"role": "assistant", "content": reply})
        else:
            historico.append({"role": "user", "content": prompt_enviado})
            print()
            reply = chat_via_llama_stream(historico)
            if reply:
                last_reply = reply
                historico.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()

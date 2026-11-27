"""Gerenciador unificado do Kael (api_server.py + llama-server) no Android/Termux."""
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path.home() / "Kael_ia"
DATA_DIR = BASE_DIR / "data"
API_LOG = DATA_DIR / "kael_server.log"
LLAMA_LOG = DATA_DIR / "llama_server.log"
API_PID_FILE = DATA_DIR / "kael_server.pid"
LLAMA_PID_FILE = DATA_DIR / "llama_server.pid"

API_PORT = 8000
LLAMA_PORT = 8080
URL = f"http://127.0.0.1:{API_PORT}"

MODEL_PATH = Path.home() / "modelos" / "modelo_local.gguf"
LLAMA_BIN_CANDIDATES = [
    Path.home() / "llama.cpp" / "build" / "bin" / "llama-server",
    Path(os.environ.get("PREFIX", "/data/data/com.termux/files/usr")) / "bin" / "llama-server",
]


def porta_ativa(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _ler_pid(pid_file: Path) -> int | None:
    if pid_file.is_file():
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
            if pid > 0:
                return pid
        except Exception:
            pass
    return None


def _encontrar_llama_bin() -> Path | None:
    for candidate in LLAMA_BIN_CANDIDATES:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def _aguardar_porta(port: int, proc: subprocess.Popen, tentativas: int = 40) -> bool:
    for _ in range(tentativas):
        if porta_ativa(port):
            return True
        if proc.poll() is not None:
            return False
        time.sleep(0.5)
    return porta_ativa(port)


def iniciar_llama() -> bool:
    if porta_ativa(LLAMA_PORT):
        return True

    llama_bin = _encontrar_llama_bin()
    if not llama_bin or not MODEL_PATH.exists():
        return False

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log_handle = open(LLAMA_LOG, "a", encoding="utf-8")
    proc = subprocess.Popen(
        [
            str(llama_bin),
            "-m", str(MODEL_PATH),
            "--host", "127.0.0.1",
            "--port", str(LLAMA_PORT),
            "-c", "2048",
            "-b", "256",
            "-ub", "128",
            "-t", "4",
            "-ctk", "q8_0",
            "-ctv", "q8_0",
            "--parallel", "1",
        ],
        cwd=str(BASE_DIR),
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    LLAMA_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    return _aguardar_porta(LLAMA_PORT, proc, tentativas=40)


def iniciar_api() -> bool:
    if porta_ativa(API_PORT):
        return True

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log_handle = open(API_LOG, "a", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(BASE_DIR / "api_server.py")],
        cwd=str(BASE_DIR),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    API_PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    return _aguardar_porta(API_PORT, proc, tentativas=30)


def _matar_processo(pid_file: Path, padrao_pkill: str):
    pid = _ler_pid(pid_file)
    if pid:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except Exception:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
        time.sleep(0.5)
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass
        pid_file.unlink(missing_ok=True)

    subprocess.run(["pkill", "-f", padrao_pkill], capture_output=True)


def fechar_tudo():
    _matar_processo(API_PID_FILE, "api_server.py")
    _matar_processo(LLAMA_PID_FILE, "llama-server")
    print("🛑 Kael e llama.cpp encerrados com segurança.")


def abrir_navegador():
    subprocess.run(["termux-open-url", URL], capture_output=True)


def status_servicos():
    api_ok = "ONLINE" if porta_ativa(API_PORT) else "OFFLINE"
    llama_ok = "ONLINE" if porta_ativa(LLAMA_PORT) else "OFFLINE"
    print(f"API Kael ({API_PORT}): {api_ok} | llama.cpp ({LLAMA_PORT}): {llama_ok}")



PASTAS_PADRAO = [
    BASE_DIR,
    BASE_DIR / "scripts",
    BASE_DIR / "data" / "luau_drafts",
    BASE_DIR / "core",
]


def _coletar_arquivos_pasta(pasta: Path, max_chars: int = 9000) -> str:
    exts = {".py", ".lua", ".luau", ".json", ".md", ".txt", ".bat", ".sh"}
    ignore = {"__pycache__", ".git", "node_modules", ".venv", "venv"}
    partes = []
    total = 0

    for root, dirs, files in os.walk(pasta):
        dirs[:] = sorted([d for d in dirs if d not in ignore])
        for fname in sorted(files):
            fp = Path(root) / fname
            if fp.suffix.lower() not in exts:
                continue
            try:
                txt = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            rel = fp.relative_to(pasta)
            bloco = f"\n--- ARQUIVO: {rel} ---\n{txt[:2200]}"
            if total + len(bloco) > max_chars:
                break
            partes.append(bloco)
            total += len(bloco)
        if total >= max_chars:
            break

    return "".join(partes)


def _consultar_llama_correcao(prompt: str) -> str:
    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "Você é Kael, revisor técnico direto em português. "
                    "Aponte bugs, riscos e melhorias concretas nos arquivos enviados "
                    "e forneça código corrigido pronto para uso."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.25,
        "stream": False,
    }
    req = urllib.request.Request(
        f"http://127.0.0.1:{LLAMA_PORT}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]


def corrigir_pasta():
    print("\n=== SELECIONAR PASTA PARA CORRIGIR ===")
    for idx, p in enumerate(PASTAS_PADRAO, start=1):
        print(f"  {idx}) {p}")
    print("  0) Digitar outro caminho de pasta")

    escolha = input("Pasta > ").strip()
    if escolha == "0":
        custom = input("Caminho da pasta > ").strip()
        alvo = Path(custom).expanduser()
        if not alvo.is_absolute():
            alvo = BASE_DIR / alvo
    elif escolha.isdigit() and 1 <= int(escolha) <= len(PASTAS_PADRAO):
        alvo = PASTAS_PADRAO[int(escolha) - 1]
    else:
        print("Seleção cancelada.")
        return

    if not alvo.is_dir():
        print(f"❌ Pasta inválida: {alvo}")
        return

    instrucao = input("O que corrigir/melhorar (Enter para revisão geral) > ").strip()
    if not instrucao:
        instrucao = "Revise bugs, falhas de lógica, segurança e melhorias práticas."

    visao_script = BASE_DIR / "scripts" / "visao_gamedev.py"
    gamedev_resumo = ""
    if visao_script.is_file():
        res_visao = subprocess.run(
            [sys.executable, str(visao_script), str(alvo)],
            cwd=str(BASE_DIR),
            text=True,
            capture_output=True,
            timeout=20,
        )
        if res_visao.stdout.strip():
            gamedev_resumo = "\n[INSPEÇÃO GAMEDEV]\n" + res_visao.stdout.strip() + "\n"
    contexto = gamedev_resumo + _coletar_arquivos_pasta(alvo)
    if not contexto.strip():
        print("⚠️ Nenhum arquivo de código/texto compatível encontrado na pasta.")
        return

    if not iniciar_llama():
        print(f"❌ llama.cpp ({LLAMA_PORT}) não está disponível para analisar a pasta.")
        return

    print("⏳ Analisando pasta com llama.cpp...")
    prompt = f"Pasta: {alvo}\nObjetivo: {instrucao}\n{contexto}"
    try:
        resposta = _consultar_llama_correcao(prompt)
    except Exception as e:
        print(f"❌ Falha ao consultar llama.cpp: {e}")
        return

    out_dir = DATA_DIR / "revisoes_pasta"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"revisao_{alvo.name}.md"
    out_file.write_text(resposta + "\n", encoding="utf-8")

    print("\n" + resposta)
    print(f"\n💾 Relatório salvo em: {out_file}")


def menu():
    llama_ok = iniciar_llama()
    if not llama_ok:
        print(f"⚠️ llama.cpp não subiu na porta {LLAMA_PORT} (verifique {LLAMA_LOG} ou {MODEL_PATH}).")

    api_ok = iniciar_api()
    if not api_ok:
        print("⚠️ Não foi possível iniciar o api_server.py. Veja o log em:")
        print(f"   {API_LOG}")
        if API_LOG.is_file():
            print("\n--- Últimas linhas do log ---")
            print("\n".join(API_LOG.read_text(encoding="utf-8", errors="ignore").splitlines()[-20:]))
        return

    abrir_navegador()
    print(f"✅ Kael ativo em {URL}")
    status_servicos()
    print("Comandos: 'chat' (terminal), 'status', 'fechar' (desliga tudo), 'sair' (mantém em segundo plano).\n")

    while True:
        try:
            try:
                cmd = input("Kael App > ").strip().lower()
            except (EOFError, OSError):
                import time
                while True:
                    time.sleep(5)
        except (EOFError, KeyboardInterrupt):
            print("\nServiços mantidos em segundo plano.")
            break

        if cmd in ("fechar", "parar", "stop", "sair tudo"):
            fechar_tudo()
            break
        if cmd == "chat":
            subprocess.run([sys.executable, str(BASE_DIR / "conversar.py")], cwd=str(BASE_DIR))
        elif cmd == "status":
            status_servicos()
        elif cmd in ("pasta", "corrigir"):
            corrigir_pasta()
        elif cmd in ("sair", "exit", "ocultar"):
            print("Kael e llama.cpp continuam rodando em segundo plano. Rode 'kael-off' para desligar.")
            break
        elif cmd:
            print("Comandos: 'chat', 'pasta', 'status', 'fechar', 'sair'.")


if __name__ == "__main__":
    arg = sys.argv[1].strip().lower() if len(sys.argv) > 1 else ""
    if arg in ("fechar", "parar", "stop", "--stop"):
        fechar_tudo()
    elif arg == "status":
        status_servicos()
    elif arg == "chat":
        iniciar_llama()
        iniciar_api()
        subprocess.run([sys.executable, str(BASE_DIR / "conversar.py")], cwd=str(BASE_DIR))
    else:
        menu()

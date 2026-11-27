import os
import re

alvos = [os.path.expanduser("~/Kael_ia/api_server.py")]
scripts_dir = os.path.expanduser("~/Kael_ia/scripts")
for fn in os.listdir(scripts_dir):
    if fn.endswith(".py"):
        alvos.append(os.path.join(scripts_dir, fn))

for path in alvos:
    src = open(path, encoding="utf-8").read()
    if "11434" not in src:
        continue

    novo = src.replace("http://127.0.0.1:11434/api/chat", "http://127.0.0.1:8080/v1/chat/completions")
    novo = novo.replace("http://localhost:11434/api/chat", "http://127.0.0.1:8080/v1/chat/completions")
    novo = novo.replace("127.0.0.1:11434", "127.0.0.1:8080")
    novo = novo.replace("localhost:11434", "127.0.0.1:8080")
    novo = novo.replace('"/api/chat"', '"/v1/chat/completions"')
    novo = novo.replace("'/api/chat'", "'/v1/chat/completions'")
    # Garante compatibilidade de leitura da resposta (Ollama usa ["message"]["content"], llama.cpp usa ["choices"][0]["message"]["content"])
    novo = re.sub(
        r'\.get\(\s*["\']message["\']\s*,\s*\{\}\s*\)\.get\(\s*["\']content["\']\s*,\s*["\']["\']\s*\)',
        '["choices"][0]["message"]["content"] if "choices" in data and data["choices"] else data.get("message", {}).get("content", "")',
        novo,
    )
    novo = novo.replace("Erro de comunicacao com o Ollama local:", "Erro de comunicacao com o llama.cpp local (8080):")

    cand = os.path.expanduser(f"~/Kael_ia/sandbox_testes/candidatos/{os.path.basename(path)}")
    open(cand, "w", encoding="utf-8").write(novo)
    print("Candidato gerado:", cand)

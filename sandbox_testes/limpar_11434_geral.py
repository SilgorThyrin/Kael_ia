import os
import re

base_dir = os.path.expanduser("~/Kael_ia")
alterados = []

for root, dirs, files in os.walk(base_dir):
    if "sandbox_testes" in root or "__pycache__" in root or ".git" in root:
        continue
    for fn in files:
        if not fn.endswith((".py", ".json")):
            continue
        path = os.path.join(root, fn)
        try:
            src = open(path, encoding="utf-8").read()
        except Exception:
            continue

        if "11434" in src or "/api/chat" in src:
            novo = src.replace("http://127.0.0.1:11434/api/chat", "http://127.0.0.1:8080/v1/chat/completions")
            novo = novo.replace("http://localhost:11434/api/chat", "http://127.0.0.1:8080/v1/chat/completions")
            novo = novo.replace("http://127.0.0.1:11434", "http://127.0.0.1:8080")
            novo = novo.replace("http://localhost:11434", "http://127.0.0.1:8080")
            novo = novo.replace("11434", "8080")
            novo = novo.replace("/api/chat", "/v1/chat/completions")
            
            # Se for Python, valida sintaxe antes de salvar
            if fn.endswith(".py"):
                compile(novo, path, "exec")
            
            open(path, "w", encoding="utf-8").write(novo)
            alterados.append(path)

print("Arquivos atualizados:", alterados)

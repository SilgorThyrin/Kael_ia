# -*- coding: utf-8 -*-
import subprocess

ALLOWLIST_COMANDOS = [
    "sfc /scannow",
    "chkdsk C: /f",
    "ipconfig /flushdns",
    "powercfg /batteryreport",
]

# Palavras que NUNCA podem aparecer no comando, sob hipótese alguma
BLOCKLIST_PALAVRAS_CHAVE = [
    "rm -rf", "rm -r", "del /f /s /q", "format", "wipe", "dd ", "su ", "root", "shutdown /r /t 0"
]

def executar_comando_sistema(comando: str) -> str:
    # 1. Verifica a Blocklist (Segurança Absoluta)
    comando_lower = comando.lower()
    for palavra_proibida in BLOCKLIST_PALAVRAS_CHAVE:
        if palavra_proibida in comando_lower:
            return f"🚫 ERRO DE SEGURANÇA: Comando contém operação proibida ('{palavra_proibida}'). O KAEL bloqueou esta ação."

    # 2. Verifica se está na Allowlist (ou é um comando de leitura seguro do Windows)
    # Para simplificar, vamos permitir comandos de leitura comuns se não estiverem na blocklist
    if comando not in ALLOWLIST_COMANDOS and not comando_lower.startswith(("dir ", "tasklist", "systeminfo")):
        return f"⚠️ Comando não está na lista de permissões do KAEL."

    # 3. Executa com segurança (shell=False previne injeção de comandos)
    try:
        args = comando.split()
        # Adiciona 'cmd /c' apenas para comandos nativos do Windows que precisam dele
        if args[0] in ["sfc", "chkdsk", "ipconfig", "powercfg"]:
            args = ["cmd", "/c"] + args
            
        resultado = subprocess.run(args, capture_output=True, text=True, timeout=60, shell=False)
        if resultado.returncode == 0:
            return resultado.stdout.strip()
        else:
            return f"ERRO DE EXECUÇÃO: {resultado.stderr.strip()}"
    except Exception as e:
        return f"ERRO DE SISTEMA: {str(e)}"
@echo off
title Fechando Kael...
echo Encerrando processos do Kael...

:: Mata Ollama
taskkill /F /IM ollama.exe >nul 2>&1

:: Mata APENAS o python que esta rodando kael_core.py (nao todos os python do PC)
wmic process where "name='python.exe' and commandline like '%%kael_core%%'" delete >nul 2>&1
wmic process where "name='pythonw.exe' and commandline like '%%kael_core%%'" delete >nul 2>&1

:: Mata a janela do companion, se existir
wmic process where "name='pythonw.exe' and commandline like '%%kael_companion%%'" delete >nul 2>&1

echo Kael encerrado.
timeout /t 2 /nobreak >nul
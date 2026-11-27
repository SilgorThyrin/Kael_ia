@echo off
chcp 65001 >nul
title Instalador de Dependencias - Kael IA
color 0A

echo ============================================================
echo    INSTALADOR AUTOMATICO DE DEPENDENCIAS - KAEL IA
echo ============================================================
echo.
echo Este script vai baixar e instalar:
echo   - Python 3.11 (portable)
echo   - Ollama (motor de IA local)
echo   - Modelos phi3.5 e qwen2.5-coder:7b
echo.
echo Espaco necessario: ~6GB
echo Tempo estimado: 10-20 minutos
echo.
pause

set "TARGET_DIR=C:\PortableAI"
cd /d "%TARGET_DIR%"

:: ============================================================
:: 1. PYTHON PORTABLE
:: ============================================================
echo.
echo [1/3] Baixando Python 3.11 Portable...
if not exist "python" mkdir python

powershell -Command "& {Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip' -OutFile 'python_embed.zip'}"

if exist "python_embed.zip" (
    echo Extraindo Python...
    powershell -Command "& {Expand-Archive -Path 'python_embed.zip' -DestinationPath 'python' -Force}"
    del python_embed.zip
    echo OK Python extraido.
) else (
    echo ERRO: Falha ao baixar Python.
    pause
    exit /b 1
)

:: ---- FIX CRITICO: habilitar 'import site' no _pth ----
echo Habilitando site-packages no Python embeddable...
if exist "python\python311._pth" (
    powershell -Command "(Get-Content 'python\python311._pth') -replace '#import site', 'import site' | Set-Content 'python\python311._pth'"
    echo OK python311._pth corrigido.
) else (
    echo AVISO: python311._pth nao encontrado, tentando outros nomes...
    for %%F in (python\python3*._pth) do (
        powershell -Command "(Get-Content '%%F') -replace '#import site', 'import site' | Set-Content '%%F'"
        echo OK %%F corrigido.
    )
)

:: pip
echo Instalando pip...
cd python
powershell -Command "& {Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'get-pip.py'}"
python.exe get-pip.py
del get-pip.py

echo Instalando bibliotecas (flask, requests, flask-cors, psutil, pynvml)...
python.exe -m pip install flask requests flask-cors psutil pynvml --quiet

cd ..
echo OK Python + libs instalados.

:: ============================================================
:: 2. OLLAMA
:: ============================================================
echo.
echo [2/3] Baixando Ollama...
if not exist "Ollama" mkdir Ollama

powershell -Command "& {Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile 'OllamaSetup.exe'}"

if exist "OllamaSetup.exe" (
    echo Instalando Ollama...
    start /wait OllamaSetup.exe /S
    del OllamaSetup.exe
    echo OK Ollama instalado.

    if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
        copy "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" "Ollama\ollama.exe" >nul
        echo OK Ollama copiado para a pasta do projeto.
    )
) else (
    echo ERRO: Falha ao baixar Ollama.
    pause
    exit /b 1
)

:: ============================================================
:: 3. MODELOS
:: ============================================================
echo.
echo [3/3] Baixando modelos (phi3.5 + qwen2.5-coder:7b)...
set OLLAMA_MODELS=%TARGET_DIR%\Modelos_Ollama
if not exist "%OLLAMA_MODELS%" mkdir "%OLLAMA_MODELS%"

start "" "Ollama\ollama.exe" serve
timeout /t 5 /nobreak >nul

Ollama\ollama.exe pull phi3.5
Ollama\ollama.exe pull qwen2.5-coder:7b

echo.
echo ============================================================
echo    INSTALACAO CONCLUIDA!
echo ============================================================
echo Modelos salvos em: %OLLAMA_MODELS%
echo.
echo Proximo passo: execute INICIAR_KAEL.bat
echo.
pause
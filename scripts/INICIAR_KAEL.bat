@echo off
setlocal
chcp 65001 >nul
title Iniciando Kael

for %%I in ("%~dp0..") do set "KAEL_APP=%%~fI"
for %%I in ("%KAEL_APP%\..") do set "PORTABLE_ROOT=%%~fI"
set "PYTHON_EXE=%PORTABLE_ROOT%\python\python.exe"
set "OLLAMA_EXE=%PORTABLE_ROOT%\Ollama\ollama.exe"

if not exist "%PYTHON_EXE%" (
    echo [ERRO] Python portatil nao encontrado: "%PYTHON_EXE%"
    echo Execute este script dentro da pasta PortableAI ou configure a distribuicao.
    pause
    exit /b 1
)

for /f "tokens=1-3 delims=|" %%A in ('"%PYTHON_EXE%" "%KAEL_APP%\scripts\diagnose_kael.py" --print-runtime') do (
    if not defined KAEL_API_HOST set "KAEL_API_HOST=%%A"
    if not defined KAEL_API_PORT set "KAEL_API_PORT=%%B"
    if not defined KAEL_OLLAMA_URL set "KAEL_OLLAMA_URL=%%C"
)
if not defined KAEL_API_HOST set "KAEL_API_HOST=127.0.0.1"
if not defined KAEL_API_PORT set "KAEL_API_PORT=8000"
if not defined KAEL_OLLAMA_URL set "KAEL_OLLAMA_URL=http://127.0.0.1:11434"

if "%KAEL_API_HOST%"=="::1" (
    set "API_HOST_URL=[::1]"
) else (
    set "API_HOST_URL=%KAEL_API_HOST%"
)
set "API_URL=http://%API_HOST_URL%:%KAEL_API_PORT%"

echo [1/3] Verificando Ollama...
curl.exe --silent --fail "%KAEL_OLLAMA_URL%/api/tags" >nul 2>&1
if errorlevel 1 (
    if /I "%KAEL_OLLAMA_URL%"=="http://127.0.0.1:11434" (
        if exist "%OLLAMA_EXE%" (
            start "Kael Ollama" /D "%PORTABLE_ROOT%\Ollama" "%OLLAMA_EXE%" serve
        ) else (
            echo [AVISO] Ollama nao responde e o executavel portatil nao foi encontrado.
        )
    ) else if /I "%KAEL_OLLAMA_URL%"=="http://localhost:11434" (
        if exist "%OLLAMA_EXE%" (
            start "Kael Ollama" /D "%PORTABLE_ROOT%\Ollama" "%OLLAMA_EXE%" serve
        ) else (
            echo [AVISO] Ollama nao responde e o executavel portatil nao foi encontrado.
        )
    ) else (
        echo [AVISO] Servidor Ollama configurado nao responde: %KAEL_OLLAMA_URL%
    )
)

echo [2/3] Iniciando ou verificando a API do Kael...
curl.exe --silent --fail "%API_URL%/health" >nul 2>&1
if errorlevel 1 (
    start "Kael API Server" /D "%KAEL_APP%" "%PYTHON_EXE%" api_server.py
) else (
    echo API Kael ja esta respondendo em %API_URL%.
)

set "API_READY="
for /L %%I in (1,1,30) do (
    curl.exe --silent --fail "%API_URL%/health" >nul 2>&1
    if not errorlevel 1 set "API_READY=1"
    if defined API_READY goto api_ready
    timeout /t 1 /nobreak >nul
)

:api_ready
if not defined API_READY (
    echo [ERRO] A API nao respondeu em %API_URL%. Verifique o diagnostico abaixo.
    "%PYTHON_EXE%" "%KAEL_APP%\scripts\diagnose_kael.py"
    pause
    exit /b 1
)

echo [3/3] Executando diagnostico e abrindo a interface...
"%PYTHON_EXE%" "%KAEL_APP%\scripts\diagnose_kael.py"
if exist "%PORTABLE_ROOT%\kael_companion.py" (
    start "Kael Companion" "%PORTABLE_ROOT%\python\pythonw.exe" "%PORTABLE_ROOT%\kael_companion.py"
)
start "" "%API_URL%/"
echo.
echo Kael iniciado. O launcher nao encerra processos existentes nem mata o Ollama.
pause

@echo off
setlocal
chcp 65001 >nul
title Reparar dependencias do Kael

for %%I in ("%~dp0..") do set "KAEL_APP=%%~fI"
for %%I in ("%KAEL_APP%\..") do set "PORTABLE_ROOT=%%~fI"
set "PYTHON_EXE=%PORTABLE_ROOT%\python\python.exe"

if not exist "%PYTHON_EXE%" (
    echo [ERRO] Python portatil nao encontrado: "%PYTHON_EXE%"
    pause
    exit /b 1
)

"%PYTHON_EXE%" -m pip --version
if errorlevel 1 (
    echo [ERRO] pip nao esta disponivel neste Python.
    echo Instale ou repare pip no ambiente portatil antes de continuar.
    pause
    exit /b 1
)

echo Instalando ou reparando dependencias declaradas...
"%PYTHON_EXE%" -m pip install -r "%KAEL_APP%\requirements.txt"
if errorlevel 1 (
    echo [ERRO] A instalacao de dependencias falhou.
    pause
    exit /b 1
)

echo.
echo Verificando instalacao, modelo, portas e permissoes...
"%PYTHON_EXE%" "%KAEL_APP%\scripts\diagnose_kael.py"
set "DIAGNOSTIC_RESULT=%ERRORLEVEL%"
echo.
if not "%DIAGNOSTIC_RESULT%"=="0" (
    echo O diagnostico encontrou pendencias. Leia os itens [ERRO] e [AVISO] acima.
)
pause
exit /b %DIAGNOSTIC_RESULT%

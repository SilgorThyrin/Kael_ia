@echo off
echo ==========================================================
echo  CONFIGURANDO OLLAMA PARA SALVAR NA PASTA DO KAEL
echo ==========================================================

:: Define a pasta de modelos dentro do diretorio atual do Kael
set OLLAMA_MODELS=%~dp0Modelos_Ollama

:: Cria a pasta se ela nao existir
if not exist "%OLLAMA_MODELS%" (
    echo Criando pasta: %OLLAMA_MODELS%
    mkdir "%OLLAMA_MODELS%"
)

echo.
echo ✅ Pasta definida com sucesso: %OLLAMA_MODELS%
echo.
echo [1/2] Baixando Phi-3.5 (Gerador Rapido - 3.8B)...
echo (Isso pode levar alguns minutos dependendo da sua internet)
ollama pull phi3.5

echo.
echo [2/2] Baixando Qwen 2.5 Coder (Revisor Critico - 7B)...
ollama pull qwen2.5-coder:7b

echo.
echo ==========================================================
echo  ✅ CONCLUIDO!
echo  Os modelos foram salvos em: %OLLAMA_MODELS%
echo  Agora voce pode fechar esta janela.
echo ==========================================================
pause
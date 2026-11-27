# Configuracao portatil, diagnostico e backup

## Instalar ou reparar

1. Confirme que o Python portatil esta em `PortableAI\python\python.exe`.
2. Execute `kael\scripts\REPARAR_KAEL.bat` para instalar/reconciliar as dependencias declaradas e executar o diagnostico.
3. Execute `kael\scripts\INICIAR_KAEL.bat`. Ele nao encerra processos existentes; se API ou Ollama ja responderem, reutiliza-os.

O template publico e `kael\config\config.template.json`. Copie-o para `config.json` somente se ainda nao houver configuracao local. O arquivo `config.json` e local e nao deve ser sincronizado.

## Configuracao por ambiente

As variaveis de ambiente substituem os valores de `config/config.json`:

- `KAEL_CONFIG_PATH`: caminho do arquivo JSON local; caminhos relativos partem da pasta `kael`.
- `KAEL_OLLAMA_URL`, `KAEL_MODEL`, `KAEL_TEMPERATURE`, `KAEL_MAX_TOKENS`, `KAEL_THINK`, `KAEL_SYSTEM_PROMPT`.
- `KAEL_PROJECTS_ROOT`, `KAEL_PROJECT_PATH`, `KAEL_MEMORY_DIR`.
- `KAEL_API_HOST` (somente `127.0.0.1`, `localhost` ou `::1`) e `KAEL_API_PORT`.

Sem configuracao, caminhos de projetos e memoria sao calculados a partir da pasta da aplicacao, nao de um caminho absoluto de uma maquina especifica. As preferencias alteradas pela interface ficam em `config/generation.local.json`.

## Diagnostico

O diagnostico verifica dependencias Python, resposta do Ollama, modelo configurado, porta da API e acesso de escrita as pastas de configuracao, memoria e projetos:

```powershell
..\python\python.exe scripts\diagnose_kael.py
```

Uma API ainda nao iniciada e um Ollama offline sao avisos; dependencias ausentes, configuracao invalida, porta ocupada por outro servico ou pastas sem escrita sao erros.

## Backup e sincronizacao

Crie um ZIP local somente com fontes e documentacao:

```powershell
..\python\python.exe scripts\backup_kael.py
```

Por padrao, o arquivo fica em `PortableAI\backups`. Para escolher outro destino, use `--destination "E:\BackupsKael"`. O arquivo inclui somente pastas de codigo permitidas, `requirements.txt` e o template publico. Nao inclui projetos, skills locais, configuracao privada, `.env`, historico, bancos, modelos, ambientes virtuais ou a propria pasta de backups.

Para sincronizar o codigo com Git, revise `git status` e o diff antes de staging. O `.gitignore` exclui bancos, historico, configuracoes locais, modelos e backups; nao force a inclusao desses dados. O backup ZIP e local e nao e enviado automaticamente a nenhum servico.

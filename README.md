<div align="center">

# Kael AI (`Kael_ia`)

**Agente de IA autônomo, portátil e 100% local-first para Android (Termux), PC Windows e desenvolvimento de jogos.**

[![Kael CI](https://github.com/SilgorThyrin/Kael_ia/actions/workflows/ci.yml/badge.svg)](https://github.com/SilgorThyrin/Kael_ia/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg)](#)

</div>

---

## Visão Geral

O **Kael AI** é um assistente de engenharia, automação e criação de jogos projetado para operar diretamente no smartphone Android via **Termux**, sem depender da nuvem para raciocinar, ler projetos ou validar código. Ele combina inferência local leve com economia de bateria (**wake-on-demand + auto-sleep**), exploração controlada do armazenamento do aparelho e comunicação em rede local (LAN) com **PC Windows**, **Roblox Studio** e **Godot 4**.

---

## Principais Recursos

* **Motor Local com Gestão Inteligente de Bateria (`llama.cpp`):**
  * Executa `llama-server` na porta `127.0.0.1:8080` com `~/modelos/modelo_local.gguf` (`-c 2048`).
  * **Wake-on-Demand & Auto-Sleep:** O servidor de inferência acorda automaticamente apenas quando uma pergunta exige raciocínio do modelo e entra em suspensão após ociosidade.
* **Interface Web Moderna (`[http://127.0.0.1:8000](http://127.0.0.1:8000)`):**
  * Layout escuro estilo pílula com chips interativos **Pensar** (raciocínio colapsável em tempo real) e **Pesquisar**.
  * Renderização completa de **tabelas Markdown**, blocos de código, listas e barra de ações por resposta (**Copiar**, **Gostei**, **Não gostei**, **Ouvir**, **Regenerar**).
  * **Voz Bidirecional em Streaming:** Reconhecimento de fala (`pt-BR`) e síntese de voz (TTS) enviada frase por frase durante a geração.
* **Acesso Seguro ao Armazenamento do Dispositivo:**
  * Exploração direta de pastas e arquivos em `/storage/emulated/0` e `~/Kael_ia` formatada em tabelas, com bloqueio de partições protegidas do sistema (`/system`, `/proc`, `/sys`, `/dev`) e suporte a `MANAGE_EXTERNAL_STORAGE` no módulo `android_assist`.
* **Pipeline para Desenvolvimento de Jogos (Roblox Studio & Godot 4):**
  * Validador estático de scripts Luau (`scripts/validar_luau.py`) com checagem de balanceamento de blocos e instâncias.
  * Geração e organização de sistemas modulares para RPGs (*Ecos de Aethelgard*: `MountService`, `FastTravelService`, `TradeService`, `MagicService`) e bridge para plugin do Roblox Studio (`KaelBridgePlugin.lua`).
  * Validação headless para cenas e recursos do **Godot 4**.
* **Ponte LAN para PC Windows:**
  * Execução remota e sincronização de tarefas entre o Termux e o Windows (`scripts/receptor_lan.py` e `scripts/INICIAR_KAEL.bat`) via rede local.
* **Segurança, Sandbox e Testes Automatizados:**
  * Allowlist rigorosa de comandos, permissões granulares com expiração, validação em sandbox antes de sobrescrever arquivos, suíte de **111 testes unitários** e verificação contínua via **GitHub Actions**.

---

## Arquitetura do Sistema

| Camada | Componente | Porta / Caminho | Responsabilidade |
| :--- | :--- | :--- | :--- |
| **Inferência LLM** | `llama-server` (`llama.cpp`) | `127.0.0.1:8080` | Execução local do modelo GGUF com wake-on-demand e auto-sleep |
| **Backend & API** | `api_server.py` / `kael_app.py` | `0.0.0.0:8000` | Streaming SSE (`/chat/stream`), ferramentas locais, memória SQLite e ciclo de vida |
| **Frontend Web** | `templates/kael_chat.html` | `[http://127.0.0.1:8000](http://127.0.0.1:8000)` | Interface responsiva com tabelas, pensamento visível, voz e atalhos |
| **Camada Android** | `android_assist/` | `KaelAssist.apk` | Activity nativa com `TextToSpeech`, `SpeechRecognizer` e permissões de storage |
| **Bridges & Tools** | `plugins/` & `scripts/` | LAN / Studio | Integração Roblox Studio, validação Luau/Godot e receptor Windows |

---

## Instalação e Execução no Termux

### 1. Preparar o ambiente Android
    pkg update && pkg install -y python git clang cmake
    termux-setup-storage

### 2. Clonar e configurar o projeto
    git clone [https://github.com/SilgorThyrin/Kael_ia.git](https://github.com/SilgorThyrin/Kael_ia.git)
    cd Kael_ia
    pip install -r requirements.txt
    cp config/config.template.json config/config.json

Coloque o modelo GGUF quantizado em `~/modelos/modelo_local.gguf` e certifique-se de que `llama-server` está no `PATH`.

### 3. Iniciar o Kael
    cd ~/Kael_ia
    python3 kael_app.py start

Acesse `[http://127.0.0.1:8000](http://127.0.0.1:8000)` no navegador do celular (ou pelo IP local na mesma rede Wi-Fi).

---

## Estrutura do Projeto

    Kael_ia/
    ├── api_server.py          # Servidor Flask/SSE principal, wake-on-demand 8080 e tools locais
    ├── kael_app.py            # Gerenciador de processos (start, status, chat, fechar)
    ├── kael_core.py           # Núcleo cognitivo, carregamento modular e política de permissões
    ├── ai/                    # Cliente llama.cpp/OpenAI-compat, compressor de contexto e memória
    ├── core/                  # Motor autônomo, sandbox, indexador de projetos e plugin bridge
    ├── templates/             # Interface web (kael_chat.html)
    ├── android_assist/        # Código-fonte Android (KaelAssistActivity.kt e AndroidManifest.xml)
    ├── plugins/               # Plugins de integração (Roblox Studio, status, personalidade)
    ├── scripts/               # Validadores Luau, ponte LAN Windows e utilitários de manutenção
    ├── tests/                 # Suíte de testes unitários automatizados
    └── .github/workflows/     # Integração contínua (Kael CI)

---

## Testes e Validação

    python3 -m compileall -q . -x "build_termux|__pycache__|\.git"
    python3 -m unittest discover -s tests -p "test_*.py"

---

## Licença

Distribuído sob a licença **MIT**. Consulte o arquivo [LICENSE](LICENSE) para mais detalhes.

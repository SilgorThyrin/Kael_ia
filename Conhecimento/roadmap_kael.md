# Roadmap do Kael

## Fase 1 — Pensamento Prévio, Memória e Autonomia Confiável (Em andamento)
- Carregar regras_pensamento.md no contexto do Kael para validar utilidade/precisão antes de responder e fazer dry-run mental antes de gerar código.
- Consolidar lições de erro e resultados de tarefas em kael_memory.db e regras_aprendidas.json com deduplicação e contexto enxuto.
- Executar etapas de planos de forma contínua quando seguras, mantendo aprovação explícita para comandos destrutivos ou alterações fora de áreas permitidas.
- Incluir verificação rápida de saúde (portas 8000 e 8080) e backup limpo em ~/storage/shared/Documents.

## Fase 2 — Manutenção Multidispositivo e Rotinas Agendadas
- Expandir auditar_limpeza.py com perfis para celular/Termux, PC e armazenamento externo/portátil, sempre com diagnóstico prévio e confirmação antes de apagar.
- Criar rotinas periódicas leves de limpeza de caches/logs antigos e backup automático sem acumular arquivos duplicados.
- Automatizar checagem de integridade de arquivos críticos (kael_memory.db, .env, regras_aprendidas.json) antes de limpezas ou atualizações.
- Adicionar diagnóstico de espaço livre, processos travados e arquivos grandes/duplicados com relatório resumido.

## Fase 3 — Projetos, Validação de Código e Orquestração Híbrida
- Pré-validar scripts Luau para Ecos de Aethelgard (sintaxe, referências nulas/ausentes, RemoteEvents, mineração de Aetherium, magias, montarias e IA dos Corrupted Echoes) antes de enviar ao Roblox Studio.
- Usar regras_aprendidas.json e task_outcome para evitar repetir erros de API, rotas ou sintaxe já corrigidos.
- Balancear execução local via llama-server (porta 8080) para tarefas rápidas/locais e modelos na nuvem para raciocínio pesado ou arquitetura extensa.
- Criar comandos rápidos de resumo de status (memória, tarefas pendentes, espaço em disco e últimas lições aprendidas).

# Roadmap Mestre do Kael

Visao: um assistente local multiproposito para suporte de TI, desenvolvimento de jogos, organizacao pessoal e tarefas gerais. Em jogos, Kael deve conseguir seguir um GDD, implementar, testar, corrigir e entregar um projeto jogavel. Autonomia ampla vale somente dentro do escopo local autorizado; acoes externas ou irreversiveis continuam sob confirmacao.

## Estado atual confirmado no codigo

- API Flask local na porta configurada (8000 por padrao), cliente Ollama, historico local e interface web em `ui/chat.html`.
- Registry modular, comandos de projeto, Roblox Studio Bridge e um plugin experimental para Godot.
- Memoria vetorial existente em SQLite/SentenceTransformers, separada do indice documental local FTS5.
- Agentes autonomos existentes para tarefas e criacao/correcao. O `/tarefa` agora persiste plano e etapas, aplica limites, lista execucoes e permite retomar checkpoints; etapas interrompidas exigem revisao explicita. Ainda faltam criterios objetivos de jogo jogavel e validacao de ponta a ponta.
- Launcher portatil verifica o modelo e abre a interface; o reparo de dependencias e o diagnostico estao documentados em `PORTABLE_SETUP.md`.
- Solicitacoes de permissao com "Permitir uma vez" e "Negar" para comandos mutaveis, salvamento por `<kael_save>` e etapas autonomas. As permissoes expiram em 10 minutos e ficam em memoria; nao sao uma sandbox nem um sistema generico de autorizacao de qualquer ferramenta.
- Politica local com quatro niveis: sempre pedir, supervisionado, autonomia no projeto e autonomia em pastas autorizadas. A autorizacao persistente de pastas e salva somente na configuracao local.
- A UI permite informar o caminho de uma pasta, pedir autorizacao, navegar um nivel por vez, ler arquivos textuais permitidos e revogar o acesso. O seletor do navegador nao revela o caminho absoluto ao servidor; por isso a autorizacao usa o caminho local digitado/colado pelo usuario.
- No nivel maximo, Kael pode criar e editar arquivos diretamente na pasta autorizada, com backup em sobrescritas. Subpastas precisam de autorizacao propria; exclusoes, rede, sistema e Studio continuam exigindo permissao.
- O caminho `projects_root` agora e exposto pelo contexto para os comandos de criacao de projeto.
- UI com seletor de arquivos/pastas, arvore relativa selecionada e envio controlado de texto ao modelo local. Conteudo de anexos nao e salvo no historico; ficam somente os nomes.
- Menu de comandos com botoes que preenchem o chat sem enviar automaticamente; downloads HTTPS publicos podem ser gravados no projeto ativo somente apos aprovacao, com limite de 50 MiB, destino relativo e sem execucao/extracao automatica.
- RAG local indexa documentos escolhidos pelo usuario, registra fonte/versao/URL/licenca, busca trechos citaveis e permite substituir ou remover uma fonte.
- Validacao headless de Godot com limite de tempo, confinamento ao diretorio de projetos e autorizacao antes da execucao.
- Propostas locais de codigo passam por teste/validacao numa copia temporaria e exigem uma segunda aprovacao para gravacao; sem runner compativel ou com falha, nao ha gravacao.
- Validadores de codigo disponiveis: `unittest` para Python, `node --test` para JavaScript e recursos web quando ha testes Node, e validacao headless do editor para GDScript/cenas Godot. A validacao Godot confirma importacao/sintaxe, nao gameplay. Luau/Roblox permanece bloqueado ate existir runner compativel.
- O Ollama recebe uma unica requisicao por geracao; o modelo de embeddings carrega sob demanda em CPU e a busca avalia no maximo as 5.000 memorias mais recentes.
- O compressor respeita estritamente `max_chars` e reporta erro quando sistema + mensagem atual nao cabem no limite.
- Painel de RAM, CPU, VRAM e temperatura GPU, com deteccao opcional de NVML.

## Fase 0 - Base local e distribuicao

- [x] Inicializacao do Ollama, API e interface local.
- [x] Configuracao portatil de caminhos e dependencias.
- [x] Verificar configuracoes por ambiente e evitar caminhos absolutos especificos da maquina; a API permanece em loopback.
- [x] Criar instalacao/reparo idempotente e diagnostico que reporte dependencias, modelo, portas e permissao de escrita.
- [x] Configurar backup-fonte local e politica de sincronizacao sem enviar bancos, historicos, modelos ou configuracao privada.

## Fase 1 - Interface conversacional

- [x] Layout escuro responsivo, conversas locais e estado de conexao.
- [x] Cartoes de permissao integrados a conversa, com detalhes e decisao explicita.
- [x] Servir a UI pela API local em vez de depender de abrir o HTML como arquivo.
- [x] Adicionar busca/renomeacao/exclusao de conversas e exportacao controlada.
- [x] Adicionar anexos com selecao explicita de arquivos/pastas, arvore, tipos textuais e limites; so o modelo local recebe o conteudo e o historico persiste apenas nomes.
- [x] Melhorar acessibilidade: foco, leitor de tela, atalhos configuraveis e estados de carregamento/erro.
- [x] Adicionar seletor de modelo e configuracoes de geracao com valores validados.

## Fase 2 - Permissoes e seguranca de ferramentas

- [x] Pedir autorizacao individual antes das principais operacoes de escrita e alteracao no Studio.
- [x] Permitir uma vez ou negar; decisoes sao consumidas uma unica vez e expiradas.
- [x] Agente autonomo pausa para autorizacao em cada subtarefa mutavel.
- [x] Declarar capacidades por comando/ferramenta (leitura, escrita de projeto, rede e Studio) e aplicar politica central.
- [x] Exigir aprovacao por download externo, validar HTTPS e enderecos publicos, limitar tamanho e confinar o destino ao projeto sem sobrescrever arquivos existentes.
- [ ] Mostrar plano, arquivos afetados e diff antes de permitir escrita; oferecer revisao por arquivo.
  - [x] Exibir diff completo em aprovacoes de `<kael_save>` e bloquear a gravacao se o destino mudar desde a previa.
  - [x] Permitir selecionar por arquivo o que sera gravado nos pedidos `<kael_save>`.
  - [ ] Estender previsualizacao e decisao por arquivo aos comandos e etapas autonomas.
- [ ] Implementar cancelamento e expiracao com estado visivel, retomada segura e fila persistida.
- [x] Criar backup local antes de sobrescrever arquivo por fluxo autonomo.
- [ ] Implementar restauracao generica de backup e undo para todas as mudancas no Studio.
  - [x] Adicionar backup/restauracao tipados para terreno e assets gerados pelo Kael no Roblox.
- [x] Restringir CORS as origens da interface local.
- [ ] Adicionar token de sessao local para acoes de escrita e validar explicitamente a origem.
- [ ] Validar caminhos, tamanho/quantidade de arquivos, tipos permitidos e destino de cada ferramenta.
- [ ] Registrar auditoria local: pedido, escopo, decisao, resultado e arquivos alterados.
- [x] Separar permissao por categoria; autorizacao de projeto nao libera rede, Studio ou sobrescrita.
- [x] Autorizar pastas locais individualmente, sem herdar permissao para subpastas, com listagem limitada, leitura textual, bloqueio de segredos e revogacao.
- [x] Oferecer quatro niveis de autorizacao e permitir escrita automatica somente dentro de pastas autorizadas no nivel maximo; sobrescritas geram backup.
- [x] Mostrar diff e pedir autorizacao para alteracoes propostas fora do nivel maximo de pastas autorizadas.
- [x] Testar/validar alteracoes de codigo em copia temporaria e pedir uma segunda aprovacao antes da gravacao; bloquear sem runner compativel ou quando a validacao falha.

## Fase 3 - RAG de documentacao e contexto de projeto

- [x] Indexar documentos locais escolhidos pelo usuario para consulta (a coleta/download oficial continua manual).
- [x] Guardar fonte, versao, URL/licenca, secao e trecho em cada registro.
- [x] Recuperar trechos relevantes por SQLite FTS5 e incluir citacoes no contexto do modelo.
- [x] Indexar scripts do projeto atual sob demanda, com exclusoes, limites de tamanho e contagem, bloqueio de arquivos/valores com cara de segredo e redacao de e-mails.
- [x] Substituir/reindexar ou remover uma fonte sem alterar a memoria de conversacao.
- [x] Testar consultas vazias, atualizacao de fonte, citacoes e limites de documentos.

## Fase 4 - Integracoes Roblox e Godot confiaveis

- [x] Fila de tarefas e envio de estado entre Kael e plugin Roblox.
- [x] Plugin Godot experimental para enviar estado da cena.
- [x] Versionar o protocolo Roblox (v1), validar payloads e associar ID/estado a cada tarefa.
- [x] Fazer o plugin confirmar tarefas e retornar resultados ou erros; tarefas entregues expiram sem repeticao automatica.
- [x] Remover a execucao de Lua arbitrario pelo plugin e restringir tarefas do Studio a acoes tipadas.
- [x] Bloquear criacao/alteracao de scripts Luau no Studio ate existir runner compativel; nao tratar scripts sem teste como aprovados.
- [x] Adicionar geracao tipada de terreno Roblox com presets, seed, limite de area/operacoes e backup restauravel; nunca limpar o terreno global.
- [x] Adicionar criacao de assets estaticos por catalogo, com limite de quantidade, checagem de solo/espacamento e backup/restauracao tipados.
- [x] Enviar amostra compacta de alturas do terreno e incluir uma avaliacao de valor/custo/risco/testes para scripts, assets e terreno em Roblox, Godot e web.
- [x] Encaminhar propostas de terreno/asset para Godot e web pelo fluxo central de testes e segunda aprovacao; testes Node novos podem fazer parte da mesma proposta.
- [ ] Criar geradores deterministas de cena/terreno/assets para Godot e web; hoje esses motores dependem de propostas do modelo e seus validadores.
- [ ] Validar o protocolo e as acoes no Roblox Studio real; a validacao automatizada atual cobre somente o servidor Flask.
- [ ] Adicionar autenticacao local entre API e plugin; o `client_id` identifica a instancia, mas ainda nao e credencial.
- [x] Executar validacao headless de Godot com timeout e limite de pasta; cada execucao exige aprovacao.
- [ ] Isolar o processo do Godot em sandbox antes de validar projetos nao confiaveis.
- [ ] Criar validacao Luau estatica e testes no Studio em ambiente/experiencia de teste.
- [ ] Comparar estado antes/depois e permitir desfazer operacoes suportadas.
- [ ] Mostrar conexao real, heartbeat e fila de cada plugin no painel.

## Fase 5 - Autonomia supervisionada e autocorrecao

- [x] Planejamento e execucao de tarefas em ciclos separados.
- [x] Interromper a execucao para pedir autorizacao antes de cada subtarefa.
- [x] Oferecer autonomia persistente limitada ao projeto, com confirmacao para sobrescritas e operacoes externas.
- [ ] Exibir o plano completo e deixar o usuario aprovar, editar ou remover etapas.
- [ ] Limitar ciclos, tempo, tokens, arquivos, chamadas de rede e tamanho de saida por tarefa.
  - [x] Limitar plano a 8 etapas de ate 500 caracteres, descricao a 2.000 caracteres, impedir novas etapas apos 30 minutos e limitar retomadas a 3.
  - [ ] Limitar tokens, arquivos alterados, chamadas de rede e saida do modelo por tarefa.
- [ ] Implementar checkpoints, retomada apos falha e cancelamento imediato.
  - [x] Persistir plano e resultado de cada etapa; retomar tarefas interrompidas sem repetir etapas concluidas.
  - [x] Marcar etapa interrompida como incerta e exigir `--repetir-incerta` para executa-la novamente.
  - [x] Adicionar `/tarefas`, `/retomar_tarefa` e exibicao do estado da tarefa.
  - [ ] Cancelar imediatamente uma operacao externa que ja esteja em execucao.
- [ ] Rodar testes e validacoes antes/depois de cada mudanca.
  - [x] Antes da gravacao, testar Python com `unittest`, JavaScript com `node --test` e validar GDScript com Godot headless, sempre em copia temporaria e com autorizacao para executar.
  - [x] Permitir que testes Node novos e recursos web (`HTML`, `CSS`, `SVG`) facam parte da mesma previa; validar cenas/recursos Godot (`.tscn`, `.tres`) com o editor headless.
  - [x] Exigir aprovacao separada para a gravacao depois de validacao aprovada.
  - [x] Bloquear linguagens sem runner compativel; Luau/Roblox nao pode ser aplicado automaticamente.
  - [ ] Expandir runners para outras linguagens e validar tambem depois da gravacao.
- [ ] Comparar resultados com criterios objetivos; repetir correcao no maximo N vezes configuravel.
- [ ] Exigir confirmacao separada para operacoes irreversiveis, execucao de codigo e alteracoes no Studio.
- [ ] Produzir relatorio final com plano, testes, arquivos alterados e pendencias.

## Fase 6 - Desempenho e observabilidade

- [x] Deteccao opcional de VRAM via pynvml e configuracao de limite.
- [x] Dashboard local de RAM, CPU, VRAM e temperatura; VRAM/temperatura dependem de NVML.
- [ ] Mostrar uso do modelo, fila e latencia.
- [ ] Smart Sleep com regras testaveis, estados visiveis e sem descarregar modelo durante operacao ativa.
- [ ] Streaming de respostas e progresso de ferramentas, com cancelamento.
- [ ] Perfilagem antes de otimizar; manter Scalene opcional e fora do caminho normal de inicializacao.
- [ ] Testes de carga, limites de memoria e recuperacao depois de timeout do Ollama.
  - [x] Remover a consulta redundante `/api/tags` antes de cada geracao.
  - [x] Carregar embeddings sob demanda em CPU e limitar cada busca as 5.000 memorias mais recentes.
  - [x] Fazer o compressor respeitar estritamente o limite de caracteres e falhar explicitamente quando o conteudo obrigatorio nao cabe.

## Fase 7 - Skills e extensibilidade

- [x] Criar formato de skill com manifesto, versao e capacidades declaradas; capacidades nao concedem permissoes.
- [x] Carregar/descarregar skills sob demanda pela UI, com validacao e isolamento de manifestos invalidos.
- [x] Revisar instrucoes e confirmar skills locais antes de habilita-las; nenhuma skill ganha permissao implicitamente.
- [ ] Suportar atualizacao, rollback e diagnostico de compatibilidade.

## Fase 8 - Distribuicao para mobile

Fase adiada a pedido do usuario ate existir um servidor/dispositivo mobile disponivel.

- [ ] Definir modelo de ameacas, identidade de dispositivo e protocolo antes de implementar conexao remota.
- [ ] Prototipar cliente mobile na mesma rede, inicialmente somente para status, notificacoes e aprovacao.
- [ ] Usar autenticacao mutua, criptografia e pareamento explicito; nao expor API sem autenticacao na LAN.
- [ ] Delegar tarefas leves; acordar o PC apenas por acao configurada e confirmada.
- [ ] Implementar fila resiliente e sincronizacao sem conflitos.

## Proximas entregas recomendadas

1. Validar os novos geradores tipados e a restauracao no Roblox Studio real; implementar um runner Luau confiavel antes de liberar escrita de scripts Roblox.
2. Criar geradores de cena, terreno e assets para Godot e web, cada um com teste compativel e aprovacao.
3. Adicionar autenticacao/pareamento local e comparacao visual antes/depois das mudancas no Studio.
4. Implementar validacao Luau e sandbox para projetos Godot nao confiaveis; definir criterios verificaveis de jogo jogavel e fechar o ciclo de autocorrecao.
5. Completar Smart Sleep, streaming/cancelamento e atualizacao/rollback de skills. A fase mobile fica adiada.

## Criterios de qualidade

- Escritas autonomas so podem ocorrer em projetos novos dentro de `projects_root` ou diretamente em pastas autorizadas no nivel maximo; as demais alteracoes pedem aprovacao.
- Aprovacoes sao de uso unico, especificas ao recurso e nao podem ser reutilizadas.
- Erros, timeouts e recusas sao apresentados sem indicar sucesso falso.
- Cada alteracao autonoma tem plano, autorizacao, validacao e caminho de recuperacao.
- O comportamento continua local por padrao e qualquer comunicacao externa e visivel e configuravel.

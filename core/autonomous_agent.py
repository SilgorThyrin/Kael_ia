"""
KAEL AUTONOMOUS AGENT v5.2 - Cria e Corrige jogos automaticamente
Fases de CRIAÇÃO:
  1. Pesquisa de referência (web_research)
  2. Geração do GDD
  3. Criação da estrutura
  4. Geração de scripts principais
  5. Validação via plugin
  6. Correção iterativa
"""
import time
import json
import re
import threading
from collections import deque
from pathlib import Path


class AutonomousAgent:
    TASK_CAPABILITIES = {
        "pesquisar_referencias": "network",
        "validar_no_studio": "studio",
        "validar_godot": "execute",
        "limpar_flutuantes": "studio",
        "gerar_gdd": "project_write",
        "criar_estrutura": "project_write",
        "gerar_scripts_base": "project_write",
        "corrigir_scripts_com_erro": "project_write",
    }

    def __init__(self, ctx):
        self.ctx = ctx
        self.active = False
        self.mode = None  # "criar" ou "corrigir"
        self.task_queue = deque()
        self.completed_tasks = []
        self.errors_detected = []
        self.max_iterations = 15
        self.current_iteration = 0
        self.pending_task_permission = None
        self.pending_task_permission_expires = 0
        self._permission_lock = threading.Lock()
        
        # Configuração do projeto (para modo "criar")
        self.project_config = {
            "genero": "aventura",
            "nome": "NovoJogo",
            "engine": "roblox",
            "ref": []
        }
    
    def activate(self, mode="criar"):
        """Ativa o agente autônomo."""
        self.active = True
        self.mode = mode
        self.current_iteration = 0
        self.task_queue.clear()
        self.completed_tasks.clear()
        print(f"[AUTÔNOMO] Modo autônomo ATIVADO ({mode})")
    
    def deactivate(self):
        """Desativa o agente autônomo."""
        self.active = False
        print(f"[AUTÔNOMO] Modo autônomo DESATIVADO após {self.current_iteration} iterações")
    
    def set_project(self, genero, nome, engine, ref):
        """Configura o projeto para criação."""
        safe_name = re.sub(r'[^\w\-]', '_', str(nome)).strip("._")
        if not safe_name:
            raise ValueError("O nome do projeto não contém caracteres válidos.")
        projects_root = Path(getattr(
            self.ctx,
            "projects_root",
            self.ctx.project_path.parent,
        ))
        project_path = (projects_root / safe_name).resolve()
        policy = getattr(self.ctx, "permission_policy", None)
        if policy is not None and not policy.is_within_projects_root(project_path):
            raise ValueError("O destino do projeto está fora da pasta de projetos permitida.")

        self.project_config = {
            "genero": genero,
            "nome": safe_name,
            "engine": engine,
            "ref": ref
        }
        self.ctx.project_path = project_path
        self._build_creation_tasks()
    
    def _build_creation_tasks(self):
        """Monta a fila de tarefas para criar o jogo do zero."""
        cfg = self.project_config
        self.task_queue.clear()
        
        # Fase 1: Pesquisa
        if cfg['ref']:
            self.task_queue.append({
                "tipo": "pesquisar_referencias",
                "genero": cfg['genero'],
                "exemplos": cfg['ref']
            })
        
        # Fase 2: GDD
        self.task_queue.append({
            "tipo": "gerar_gdd",
            "genero": cfg['genero'],
            "nome": cfg['nome'],
            "engine": cfg['engine']
        })
        
        # Fase 3: Estrutura
        self.task_queue.append({
            "tipo": "criar_estrutura",
            "nome": cfg['nome'],
            "genero": cfg['genero'],
            "engine": cfg['engine']
        })
        
        # Fase 4: Scripts principais (gera 3 scripts base)
        self.task_queue.append({
            "tipo": "gerar_scripts_base",
            "nome": cfg['nome'],
            "genero": cfg['genero'],
            "engine": cfg['engine']
        })
        
        # Engine validation requires separate approval before executing project code.
        self.task_queue.append({
            "tipo": "validar_godot" if cfg["engine"] == "godot" else "validar_no_studio"
        })
        
        print(f"[AUTÔNOMO] {len(self.task_queue)} tarefas de criação enfileiradas")
    
    def receive_game_state(self, estado):
        """Recebe estado do jogo (plugin) e detecta problemas."""
        if not self.active:
            return
        
        self.current_iteration += 1
        if self.current_iteration > self.max_iterations:
            print(f"[AUTÔNOMO] Limite de iterações ({self.max_iterations}) atingido")
            self.deactivate()
            return
        
        tarefas = []
        
        # Detecta blocos flutuantes
        if 'instancias' in estado:
            flutuantes = [obj for obj in estado['instancias'] if obj.get('y', 0) < -100]
            if flutuantes:
                tarefas.append({
                    "tipo": "limpar_flutuantes",
                    "modo": "REMOVER",
                    "backup": True,
                    "max_distance": 50
                })
        
        # Detecta erros de script (reportados pelo plugin)
        if hasattr(self.ctx, 'plugin_bridge') and self.ctx.plugin_bridge:
            erros = self.ctx.plugin_bridge.errors[-5:]
            if erros:
                tarefas.append({
                    "tipo": "corrigir_scripts_com_erro",
                    "erros": erros
                })
        
        for t in tarefas:
            self.task_queue.append(t)
            print(f"[AUTÔNOMO] Tarefa de correção enfileirada: {t['tipo']}")
        
        if not tarefas:
            print(f"[AUTÔNOMO] ✅ Jogo limpo após {self.current_iteration} iterações!")
            self.deactivate()
    
    def get_next_task(self):
        """Retorna a próxima tarefa e a executa."""
        with self._permission_lock:
            if self.pending_task_permission:
                if time.time() < self.pending_task_permission_expires:
                    return {"aguardando_permissao": True}
                self.pending_task_permission = None
                self.pending_task_permission_expires = 0

        if not self.task_queue:
            return None
        
        tarefa = self.task_queue.popleft()
        print(f"[AUTÔNOMO] Executando: {tarefa['tipo']}")

        capability = self.TASK_CAPABILITIES.get(tarefa.get("tipo"), "confirm")
        policy = getattr(self.ctx, "permission_policy", None)
        requires_approval = (
            policy.requires_approval(capability, getattr(self.ctx, "project_path", None))
            if policy is not None
            else True
        )

        if requires_approval:
            registry = getattr(self.ctx, "registry", None)
            if registry is None:
                self.task_queue.appendleft(tarefa)
                return {"sucesso": False, "erro": "Registro de permissões indisponível."}

            expires_at = time.time() + 600

            def execute_approved_task():
                try:
                    if not self.active:
                        return {
                            "status": "denied",
                            "response": "O agente foi interrompido; a etapa não foi executada.",
                        }
                    resultado = self._execute_task(tarefa)
                    self.completed_tasks.append({"tarefa": tarefa, "resultado": resultado})
                    if resultado.get("aguardando_aprovacao"):
                        return {
                            "status": "pending_approval",
                            "response": resultado.get("erro", "A etapa aguarda testes e aprovação."),
                        }
                    return {
                        "status": "success" if resultado.get("sucesso") else "error",
                        "response": (
                            f"Etapa autônoma '{tarefa['tipo']}' concluída."
                            if resultado.get("sucesso")
                            else f"Etapa autônoma '{tarefa['tipo']}' falhou: {resultado.get('erro', 'erro desconhecido')}"
                        ),
                    }
                finally:
                    with self._permission_lock:
                        self.pending_task_permission = None
                        self.pending_task_permission_expires = 0

            def reject_task():
                self.completed_tasks.append({
                    "tarefa": tarefa,
                    "resultado": {"sucesso": False, "erro": "Negada pelo usuário"},
                })
                self.deactivate()
                with self._permission_lock:
                    self.pending_task_permission = None
                    self.pending_task_permission_expires = 0

            permission = registry.create_approval(
                title="Permissão para etapa autônoma",
                summary=f"O agente quer executar: {tarefa['tipo']}",
                details=json.dumps(tarefa, ensure_ascii=False, indent=2)[:4000],
                callback=execute_approved_task,
                on_reject=reject_task,
            )
            with self._permission_lock:
                self.pending_task_permission = permission["id"]
                self.pending_task_permission_expires = expires_at
            return {"aguardando_permissao": True, "permission": permission}

        try:
            resultado = self._execute_task(tarefa)
            self.completed_tasks.append({"tarefa": tarefa, "resultado": resultado})
            return resultado
        except Exception as e:
            print(f"[AUTÔNOMO] Erro na tarefa {tarefa['tipo']}: {e}")
            return {"sucesso": False, "erro": str(e)}
    
    def _execute_task(self, tarefa):
        """Executa uma tarefa específica."""
        ctx = self.ctx
        tipo = tarefa['tipo']
        
        if tipo == 'pesquisar_referencias':
            if not ctx.web_research:
                return {"sucesso": False, "erro": "Web Research indisponível"}
            pesquisa = ctx.web_research().research_genre(tarefa['genero'], tarefa['exemplos'])
            if pesquisa:
                docs_dir = ctx.project_path / 'Docs'
                docs_dir.mkdir(parents=True, exist_ok=True)
                fname = f"PESQUISA_{tarefa['genero']}.md"
                (docs_dir / fname).write_text(pesquisa, encoding='utf-8')
                return {"sucesso": True, "arquivo": fname}
            return {"sucesso": False, "erro": "Pesquisa vazia"}
        
        elif tipo == 'gerar_gdd':
            prompt = (
                f"Crie um GDD completo para um jogo de {tarefa['genero']} chamado "
                f"{tarefa['nome']} (motor: {tarefa['engine']}). "
                f"Inclua: visão geral, mecânicas principais, progressão, direção de arte e som. "
                f"Salve com: <kael_save filename='Docs/GDD.md'>conteúdo</kael_save>"
            )
            resultado = ctx.generate(prompt)
            ctx.process_save_commands(resultado['response'], save_dir=ctx.project_path)
            return {"sucesso": True}
        
        elif tipo == 'criar_estrutura':
            if not ctx.game_bridge:
                return {"sucesso": False, "erro": "Game Bridge indisponível"}
            bridge = ctx.game_bridge(str(ctx.project_path))
            info = bridge.create_project_structure(tarefa['nome'], tarefa['genero'], tarefa['engine'])
            if info.get("template_files"):
                from tools.game_bridge import template_save_commands
                return self._save_generated_code(
                    template_save_commands(info["template_files"]),
                    ctx.project_path,
                )
            return {"sucesso": True, "pastas": info['pastas']}
        
        elif tipo == 'gerar_scripts_base':
            if not ctx.game_bridge:
                return {"sucesso": False, "erro": "Game Bridge indisponível"}
            engine = tarefa['engine']
            scripts = self._get_base_scripts(engine, tarefa['nome'], tarefa['genero'])
            save_tags = "".join(
                f"<kael_save filename='Scripts/{nome_script}'>{codigo}</kael_save>"
                for nome_script, codigo in scripts.items()
            )
            result = self._save_generated_code(save_tags, ctx.project_path)
            if result["sucesso"]:
                result["scripts"] = list(scripts.keys())
            return result
        
        elif tipo == 'validar_no_studio':
            if hasattr(ctx, 'plugin_bridge') and ctx.plugin_bridge:
                ctx.plugin_bridge.enqueue({"tipo": "pedir_visao"})
                return {"sucesso": True, "mensagem": "Visão solicitada ao Studio"}
            return {"sucesso": False, "erro": "Plugin não conectado"}

        elif tipo == 'validar_godot':
            from tools.godot_runner import GodotRunner
            runner = GodotRunner(
                ctx.projects_root,
                executable=ctx.config.get("godot_executable"),
            )
            result = runner.validate(ctx.project_path)
            if result["status"] != "success":
                return {"sucesso": False, "erro": result.get("stderr") or result.get("error")}
            return {"sucesso": True, "saida": result.get("stdout", "")[-2000:]}
        
        elif tipo == 'limpar_flutuantes':
            if hasattr(ctx, 'plugin_bridge') and ctx.plugin_bridge:
                ctx.plugin_bridge.enqueue(tarefa)
                return {"sucesso": True, "mensagem": "Limpeza enviada ao Studio"}
            return {"sucesso": False, "erro": "Plugin não conectado"}
        
        elif tipo == 'corrigir_scripts_com_erro':
            erros = tarefa.get('erros', [])
            prompt = (
                f"Analise os seguintes erros do Roblox Studio e gere scripts corrigidos. "
                f"Para cada correção, use: <kael_save filename='Scripts/NOME_fix.lua'>código</kael_save>\n\n"
                f"Erros:\n" + "\n".join([f"- {e.get('erro', '')}" for e in erros])
            )
            resultado = ctx.generate(prompt)
            return self._save_generated_code(
                resultado['response'],
                ctx.project_path,
            )
        
        return {"sucesso": False, "erro": f"Tipo desconhecido: {tipo}"}

    def _save_generated_code(self, response_text, save_dir):
        if "<kael_save" not in response_text:
            return {"sucesso": False, "erro": "A geração não retornou uma proposta de script."}

        result = self.ctx.process_save_commands(response_text, save_dir=save_dir)
        if any(marker in result for marker in (
            "[AGUARDANDO TESTE E APROVAÇÃO:",
            "[ALTERAÇÃO BLOQUEADA:",
            "[ARQUIVO BLOQUEADO:",
        )):
            self.deactivate()
            self.task_queue.clear()
            return {
                "sucesso": False,
                "aguardando_aprovacao": "[AGUARDANDO TESTE E APROVAÇÃO:" in result,
                "erro": result,
            }
        return {"sucesso": True, "resposta": result}
    
    def _get_base_scripts(self, engine, nome, genero):
        """Retorna scripts base para o motor escolhido."""
        if engine == 'roblox':
            return {
                'GameManager.lua': f'''-- {nome} - GameManager (Server)
-- Gênero: {genero}
local Players = game:GetService("Players")

local GameManager = {{}}
GameManager.Jogadores = {{}}

Players.PlayerAdded:Connect(function(player)
    GameManager.Jogadores[player.UserId] = {{
        nome = player.Name,
        pontos = 0,
        nivel = 1
    }}
    print(player.Name .. " entrou no jogo.")
end)

Players.PlayerRemoving:Connect(function(player)
    GameManager.Jogadores[player.UserId] = nil
end)

return GameManager''',
                'CombatSystem.lua': f'''-- {nome} - Sistema de Combate
-- Gênero: {genero}
local CombatSystem = {{}}
CombatSystem.DanoBase = 10
CombatSystem.Alcance = 5

function CombatSystem:Atacar(atacante, alvo)
    local distancia = (atacante.Position - alvo.Position).Magnitude
    if distancia <= self.Alcance then
        alvo.Health = alvo.Health - self.DanoBase
        return true
    end
    return false
end

return CombatSystem''',
                'UIController.lua': f'''-- {nome} - UI Controller (Client)
-- Gênero: {genero}
local Players = game:GetService("Players")
local player = Players.LocalPlayer
local playerGui = player:WaitForChild("PlayerGui")

local UIController = {{}}

function UIController:MostrarMensagem(texto)
    print("[UI] " .. texto)
end

function UIController:AtualizarHUD(pontos, nivel)
    print("[UI] Pontos: " .. pontos .. " | Nível: " .. nivel)
end

return UIController'''
            }
        elif engine == 'godot':
            return {
                'main.gd': f'''extends Node
# {nome} - Main
# Gênero: {genero}

func _ready():
    print("Projeto {nome} iniciado")
    get_tree().change_scene_to_file("res://Cenas/Main.tscn")''',
                'player.gd': f'''extends CharacterBody2D
# {nome} - Player

const VELOCIDADE = 300.0
const PULO = -400.0

func _physics_process(delta):
    var direcao = Input.get_axis("left", "right")
    if direcao:
        velocity.x = direcao * VELOCIDADE
    else:
        velocity.x = move_toward(velocity.x, 0, VELOCIDADE)
    move_and_slide()'''
            }
        else:  # web
            return {
                'js/main.js': f'''// {nome} - Main
// Gênero: {genero}
console.log("Projeto {nome} iniciado");

const game = {{
    player: {{ x: 0, y: 0, vida: 100 }},
    update() {{
        // Loop do jogo
    }},
    render() {{
        // Renderização
    }}
}};

game.update();''',
                'css/style.css': f'''/* {nome} - Estilos */
body {{
    margin: 0;
    background: #1a1a1a;
    color: white;
    font-family: Arial;
}}'''
            }
        return {}
    
    def task_completed(self, resultado):
        """Registra tarefa concluída pelo plugin."""
        self.completed_tasks.append({"origem": "plugin", "resultado": resultado})
        print(f"[AUTÔNOMO] Plugin reportou: {resultado.get('tipo')} sucesso={resultado.get('sucesso')}")
        
        # Se falhou, retenta (máx 2x)
        if not resultado.get('sucesso', False):
            if resultado.get('tentativas', 0) < 2:
                resultado['tentativas'] = resultado.get('tentativas', 0) + 1
                self.task_queue.append(resultado)
    
    def get_status(self):
        """Retorna status do agente."""
        return {
            "ativo": self.active,
            "modo": self.mode,
            "iteracao": self.current_iteration,
            "max_iteracoes": self.max_iterations,
            "tarefas_pendentes": len(self.task_queue),
            "tarefas_concluidas": len(self.completed_tasks),
            "aguardando_permissao": bool(self.pending_task_permission),
            "projeto": self.project_config if self.mode == "criar" else None
        }
    
    def run_cycle(self):
        """Executa um ciclo do agente (chamado periodicamente)."""
        if not self.active:
            return None
        
        tarefa = self.get_next_task()
        if tarefa is None:
            if not self.task_queue:
                print("[AUTÔNOMO] Todas as tarefas concluídas!")
                self.deactivate()
            return None
        
        return tarefa
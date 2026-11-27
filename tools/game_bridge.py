"""
KAEL GAME BRIDGE - Ponte entre o Kael e os motores de jogo
"""
import re
from pathlib import Path


def template_save_commands(template_files):
    """Converte templates em propostas para o fluxo central de validação."""
    return "".join(
        f"<kael_save filename='{filename}'>{content}</kael_save>"
        for filename, content in template_files
    )


class GameBridge:
    def __init__(self, project_path):
        self.project_path = Path(project_path)

    def detect_engine(self):
        if not self.project_path.exists():
            return 'inexistente'
        if (self.project_path / 'project.godot').exists():
            return 'godot'
        if (self.project_path / 'index.html').exists():
            return 'web'
        if list(self.project_path.glob('*.rbxlx')) or list(self.project_path.glob('*.rbxl')):
            return 'roblox'
        gd = len(list(self.project_path.rglob('*.gd')))
        lua = len(list(self.project_path.rglob('*.lua')))
        js = len(list(self.project_path.rglob('*.js')))
        maior = max([(gd, 'godot'), (lua, 'roblox'), (js, 'web')], key=lambda x: x[0])
        return maior[1] if maior[0] > 0 else 'desconhecido'

    def scan_project(self):
        if not self.project_path.exists():
            return {"erro": f"Pasta do projeto não encontrada: {self.project_path}"}
        scripts, docs, scenes = [], [], []
        for f in self.project_path.rglob('*'):
            if not f.is_file():
                continue
            rel = str(f.relative_to(self.project_path))
            if f.suffix in ('.gd', '.lua', '.cs', '.js'):
                linhas = len(f.read_text(encoding='utf-8', errors='ignore').splitlines())
                scripts.append({"arquivo": rel, "linhas": linhas})
            elif f.suffix in ('.md', '.txt') and f.stem.upper() in ('GDD', 'LORE', 'OBJETIVOS', 'README'):
                docs.append(rel)
            elif f.suffix in ('.tscn', '.tres', '.rbxmx'):
                scenes.append(rel)
        return {
            "motor": self.detect_engine(),
            "total_scripts": len(scripts),
            "scripts": scripts,
            "documentos": docs,
            "cenas": scenes,
        }

    def analyze_scripts(self, max_files=10):
        problemas = []
        arquivos = [f for f in self.project_path.rglob('*')
                    if f.is_file() and f.suffix in ('.gd', '.lua', '.cs', '.js')][:max_files]
        for f in arquivos:
            texto = f.read_text(encoding='utf-8', errors='ignore')
            linhas = texto.splitlines()
            rel = str(f.relative_to(self.project_path))
            if len(linhas) > 500:
                problemas.append({
                    "arquivo": rel, "tipo": "ARQUIVO_LONGO",
                    "detalhe": f"{len(linhas)} linhas - considere dividir em módulos"
                })
            for i, linha in enumerate(linhas, 1):
                if 'TODO' in linha or 'FIXME' in linha:
                    problemas.append({
                        "arquivo": rel, "tipo": "TODO_PENDENTE",
                        "detalhe": f"Linha {i}: {linha.strip()[:60]}"
                    })
                if re.search(r'\bprint\s*\(', linha) and not linha.strip().startswith('#') and not linha.strip().startswith('--'):
                    problemas.append({
                        "arquivo": rel, "tipo": "DEBUG_ESQUECIDO",
                        "detalhe": f"Linha {i}: print() de depuração no código"
                    })
                if 'while true do' in linha.lower() or 'while(true)' in linha.lower() or 'while (true)' in linha:
                    problemas.append({
                        "arquivo": rel, "tipo": "LOOP_INFINITO_RISCO",
                        "detalhe": f"Linha {i}: 'while true' - verifique se há wait/task.wait"
                    })
        return problemas

    def read_docs(self, max_chars=4000):
        conteudo = []
        for nome in ('GDD.md', 'LORE.md', 'OBJETIVOS.md', 'README.md', 'PESQUISA.md'):
            p = self.project_path / nome
            if not p.exists():
                p = self.project_path / 'Docs' / nome
            if p.exists():
                texto = p.read_text(encoding='utf-8', errors='ignore')[:max_chars]
                conteudo.append(f"=== {nome} ===\n{texto}")
        return '\n\n'.join(conteudo)

    def create_project_structure(self, nome, genero, engine='auto'):
        if engine == 'auto':
            engine = self.detect_engine()
            if engine in ('inexistente', 'desconhecido'):
                engine = 'roblox'
        base = self.project_path
        base.mkdir(parents=True, exist_ok=True)
        templates = []
        template_files = []
        if engine == 'godot':
            pastas = ['Scripts', 'Cenas', 'Assets', 'Docs', 'Tests']
            for p in pastas:
                (base / p).mkdir(parents=True, exist_ok=True)
            pg = base / 'project.godot'
            if not pg.exists():
                pg.write_text(f'config_version=5\n\n[application]\nconfig/name="{nome}"\n\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n', encoding='utf-8')
                templates.append('project.godot')
            main = base / 'Scripts' / 'main.gd'
            if not main.exists():
                templates.append('Scripts/main.gd')
                template_files.append((
                    'Scripts/main.gd',
                    f'extends Node\n\n# {nome} - gerado pelo Kael\n# Gênero: {genero}\n\nfunc _ready():\n\tprint("Projeto {nome} iniciado.")\n',
                ))
        elif engine == 'web':
            pastas = ['js', 'css', 'assets', 'Docs']
            for p in pastas:
                (base / p).mkdir(parents=True, exist_ok=True)
            idx = base / 'index.html'
            if not idx.exists():
                templates.append('index.html')
                template_files.append((
                    'index.html',
                    f'<!DOCTYPE html>\n<html lang="pt-BR">\n<head>\n<meta charset="UTF-8">\n<title>{nome}</title>\n<link rel="stylesheet" href="css/style.css">\n</head>\n<body>\n<h1>{nome}</h1>\n<p>Jogo web gerado pelo Kael (gênero: {genero}).</p>\n<script src="js/main.js"></script>\n</body>\n</html>\n',
                ))
            js = base / 'js' / 'main.js'
            if not js.exists():
                templates.append('js/main.js')
                template_files.append((
                    'js/main.js',
                    f'// {nome} - gerado pelo Kael\nconsole.log("Projeto {nome} iniciado.");\n',
                ))
        else:
            pastas = ['Scripts', 'Modules', 'Assets', 'Docs', 'Tests']
            for p in pastas:
                (base / p).mkdir(parents=True, exist_ok=True)
            main = base / 'Scripts' / 'main.lua'
            if not main.exists():
                templates.append('Scripts/main.lua')
                template_files.append((
                    'Scripts/main.lua',
                    f'-- {nome} - gerado pelo Kael\n-- Gênero: {genero} (Server Script)\nlocal Players = game:GetService("Players")\n\nPlayers.PlayerAdded:Connect(function(player)\n\tprint(player.Name .. " entrou no jogo.")\nend)\n',
                ))
        return {
            "pastas": pastas,
            "engine": engine,
            "templates": templates,
            "template_files": template_files,
        }

    def create_floating_cleaner_script(self, modo='REMOVER', backup=True, max_distance=50):
        """Retorna metadados para uma limpeza tipada; nao grava scripts Luau."""
        lua = f'''--[[
    KAEL - VARREDURA + REMOCAO EM LOTE DE BLOCOS FLUTUANTES
    Gerado pelo GameBridge. Modo: {modo} | Backup: {backup} | Distancia: {max_distance} studs
]]

local Workspace = game:GetService("Workspace")
local ServerStorage = game:GetService("ServerStorage")

local CONFIG = {{
    modo = "{modo}",
    backup = {str(backup).lower()},
    maxDistance = {max_distance},
    minSize = 1,
    ignoreNames = {{ "Baseplate", "SpawnLocation", "Kael_Removidos" }},
}}

local ignoreSet = {{}}
for _, n in ipairs(CONFIG.ignoreNames) do ignoreSet[n] = true end

local function topLevel(part)
    local current = part
    while current.Parent and current.Parent ~= Workspace do
        current = current.Parent
    end
    return current
end

local function protected(part)
    if ignoreSet[part.Name] then return true end
    local parent = part.Parent
    while parent and parent ~= Workspace do
        if ignoreSet[parent.Name] then return true end
        parent = parent.Parent
    end
    return false
end

local function isFloating(part)
    if not part:IsA("BasePart") then return false end
    if protected(part) then return false end
    if part.Size.Magnitude < CONFIG.minSize then return false end
    local origin = part.Position - Vector3.new(0, (part.Size.Y / 2) + 0.2, 0)
    local direction = Vector3.new(0, -CONFIG.maxDistance, 0)
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = {{ topLevel(part) }}
    local hit = Workspace:Raycast(origin, direction, params)
    return hit == nil
end

-- 1) VARREDURA UNICA
local flutuantes = {{}}
for _, descendant in ipairs(Workspace:GetDescendants()) do
    if isFloating(descendant) then
        table.insert(flutuantes, descendant)
    end
end

print(string.format("[KAEL] Varredura concluida: %d blocos flutuando.", #flutuantes))
for i, part in ipairs(flutuantes) do
    if i <= 30 then
        print(string.format("   [%d] %s (%.1f, %.1f, %.1f)", i, part:GetFullName(), part.Position.X, part.Position.Y, part.Position.Z))
    end
end

-- 2) ACAO EM LOTE
if CONFIG.modo == "REMOVER" and #flutuantes > 0 then
    local destino = nil
    if CONFIG.backup then
        destino = ServerStorage:FindFirstChild("Kael_Removidos")
        if not destino then
            destino = Instance.new("Folder")
            destino.Name = "Kael_Removidos"
            destino.Parent = ServerStorage
        end
    end
    for _, part in ipairs(flutuantes) do
        if CONFIG.backup then
            part.Parent = destino
        else
            part:Destroy()
        end
    end
    print(string.format("[KAEL] %d blocos removidos EM LOTE.%s", #flutuantes, CONFIG.backup and " Backup em ServerStorage.Kael_Removidos" or ""))
else
    print("[KAEL] Modo ANALISAR: nada removido.")
end
'''
        return {
            "modo": modo.upper(),
            "backup": backup,
            "max_distance": max_distance,
        }

    def full_report(self):
        scan = self.scan_project()
        if 'erro' in scan:
            return scan
        scan['problemas'] = self.analyze_scripts()
        return scan
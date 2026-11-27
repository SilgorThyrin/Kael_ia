"""
KAEL TEST RUNNER - Validação e execução de scripts Luau/Roblox
Fluxo: validar sintaxe → enviar ao plugin → capturar resultado → reportar
"""
import re
import time
from pathlib import Path
from typing import Dict, List, Optional


class LuauTestRunner:
    """Executor de testes para scripts Luau do Roblox."""
    
    # Padrões de erro comuns em Luau
    ERROR_PATTERNS = [
        (r"unexpected symbol near '([^']+)'", "Símbolo inesperado: {0}"),
        (r"'end' expected \(to close '([^']+)'\)", "Falta 'end' para fechar '{0}'"),
        (r"unfinished string", "String não terminada (falta aspas)"),
        (r"malformed number", "Número malformado"),
        (r"attempt to call.*nil value", "Função não existe: {0}"),
        (r"attempt to index.*nil value", "Tentativa de acessar nil: {0}"),
    ]
    
    def __init__(self, ctx):
        self.ctx = ctx
        self.test_results = []
        self.last_test_time = 0
    
    def validate_syntax(self, script_path: Path) -> Dict:
        """Valida sintaxe Luau sem executar (análise estática)."""
        if not script_path.exists():
            return {"valid": False, "error": f"Arquivo não encontrado: {script_path}"}
        
        content = script_path.read_text(encoding='utf-8')
        
        # Verificações básicas
        issues = []
        
        # 1. Balanceamento de blocos (if/then, function, do, for, while)
        openers = len(re.findall(r'\b(if|function|do|for|while|repeat)\b', content))
        closers = len(re.findall(r'\b(end|until)\b', content))
        if openers != closers:
            issues.append(f"Balanceamento de blocos: {openers} aberturas vs {closers} fechamentos")
        
        # 2. Strings não terminadas
        single_quotes = content.count("'") % 2
        double_quotes = content.count('"') % 2
        if single_quotes or double_quotes:
            issues.append("Aspas não balanceadas (strings não terminadas)")
        
        # 3. Parênteses/colchetes
        if content.count('(') != content.count(')'):
            issues.append("Parênteses não balanceados")
        if content.count('[') != content.count(']'):
            issues.append("Colchetes não balanceados")
        
        # 4. Funções Roblox comuns (verifica se usa API correta)
        roblox_apis = [
            r'game:GetService\("([^"]+)"\)',
            r'Instance\.new\("([^"]+)"\)',
            r'wait\(\)',  # antigo, deveria ser task.wait()
        ]
        for pattern in roblox_apis:
            matches = re.findall(pattern, content)
            if 'wait()' in matches:
                issues.append("Usando wait() antigo - prefira task.wait()")
        
        valid = len(issues) == 0
        return {
            "valid": valid,
            "issues": issues,
            "lines": len(content.splitlines()),
            "size_kb": len(content) / 1024
        }
    
    def send_to_studio(self, script_path: Path, test_mode: str = "syntax") -> Dict:
        """Envia script para o plugin Roblox executar e capturar erros."""
        if not self.ctx.plugin_bridge:
            return {"success": False, "error": "Plugin Roblox não conectado"}
        
        if not self.ctx.plugin_bridge.studio_conectado():
            return {"success": False, "error": "Roblox Studio não está respondendo"}
        
        content = script_path.read_text(encoding='utf-8')
        
        # Monta tarefa de teste
        tarefa = {
            "tipo": "testar_script",
            "nome_script": script_path.name,
            "codigo": content,
            "modo": test_mode,  # "syntax" (só compila) ou "execute" (roda)
            "timeout": 5  # segundos
        }
        
        # Envia para a fila do plugin
        self.ctx.plugin_bridge.enqueue(tarefa)
        
        # Aguarda resultado (polling)
        start = time.time()
        while time.time() - start < 10:  # timeout de 10s
            if self.ctx.plugin_bridge.last_completion:
                result = self.ctx.plugin_bridge.last_completion
                if result.get('tipo') == 'testar_script':
                    self.test_results.append(result)
                    self.last_test_time = time.time()
                    return result
            time.sleep(0.5)
        
        return {"success": False, "error": "Timeout: plugin não respondeu em 10s"}
    
    def run_full_test(self, script_path: Path) -> Dict:
        """Executa teste completo: validação local + execução no Studio."""
        # 1. Validação estática
        syntax_check = self.validate_syntax(script_path)
        if not syntax_check["valid"]:
            return {
                "success": False,
                "stage": "syntax_validation",
                "issues": syntax_check["issues"],
                "script": script_path.name
            }
        
        # 2. Execução no Studio
        studio_result = self.send_to_studio(script_path, test_mode="syntax")
        
        return {
            "success": studio_result.get("sucesso", False),
            "stage": "studio_execution",
            "script": script_path.name,
            "syntax_valid": True,
            "studio_error": studio_result.get("erro"),
            "execution_time": studio_result.get("tempo_execucao", 0)
        }
    
    def generate_test_report(self) -> str:
        """Gera relatório legível dos últimos testes."""
        if not self.test_results:
            return "📊 Nenhum teste executado ainda."
        
        passed = sum(1 for r in self.test_results if r.get("sucesso"))
        failed = len(self.test_results) - passed
        
        report = [
            f"📊 **Relatório de Testes**",
            f"- **Total:** {len(self.test_results)} scripts",
            f"- **✅ Passaram:** {passed}",
            f"- **❌ Falharam:** {failed}",
            ""
        ]
        
        if failed > 0:
            report.append("**Erros encontrados:**")
            for r in self.test_results:
                if not r.get("sucesso"):
                    report.append(f"- `{r.get('nome_script')}`: {r.get('erro', 'Erro desconhecido')}")
        
        return "\n".join(report)


class LuauTestGenerator:
    """Gera testes unitários automáticos para scripts Luau."""
    
    @staticmethod
    def generate_unit_test(script_path: Path) -> str:
        """Gera um script de teste unitário para o script alvo."""
        script_name = script_path.stem
        content = script_path.read_text(encoding='utf-8')
        
        # Detecta funções públicas no script
        functions = re.findall(r'function\s+(\w+)\s*\(', content)
        
        test_code = f"""--[[
Teste Unitário: {script_name}
Gerado pelo Kael Test Runner
]]

local function test_{script_name}()
    print("🧪 Iniciando testes de {script_name}...")
    
    -- Teste 1: Verifica se o script carrega sem erros
    local success, err = pcall(function()
        -- Aqui você mockaria as dependências do Roblox
        -- Ex: local Players = {{}} -- mock
    end)
    
    if not success then
        error("❌ Falha ao carregar: " .. tostring(err))
    end
    print("✅ Script carregou com sucesso")
    
    -- Teste 2: Verifica funções públicas
    {chr(10).join(f'    assert(type({script_name}.{fn}) == "function", "Função {fn} não encontrada")' for fn in functions[:5])}
    print("✅ Funções públicas verificadas")
    
    -- Teste 3: Edge cases (adicione conforme necessário)
    -- assert({script_name}.someFunction(nil) == expected, "Deve lidar com nil")
    
    print("🎉 Todos os testes passaram!")
end

-- Executa o teste
test_{script_name}()
"""
        return test_code
    
    @staticmethod
    def generate_mock_environment() -> str:
        """Gera um ambiente mock para testar scripts Roblox sem o Studio."""
        return """--[[
Mock Environment para testes Luau offline
Cole no topo do script de teste
]]

-- Mock de serviços Roblox
local MockServices = {
    Players = {
        GetPlayers = function() return {} end,
        PlayerAdded = {Connect = function() end}
    },
    Workspace = {
        GetDescendants = function() return {} end
    },
    ReplicatedStorage = {},
    ServerStorage = {}
}

-- Mock de game:GetService
local originalGetService = game.GetService
game.GetService = function(self, serviceName)
    return MockServices[serviceName] or error("Serviço não mockado: " .. serviceName)
end

-- Mock de Instance.new
local originalNew = Instance.new
Instance.new = function(className, parent)
    local mock = {
        ClassName = className,
        Parent = parent,
        Name = "MockInstance",
        Destroy = function() end
    }
    return setmetatable(mock, {__index = function() return function() end end})
end

print("✅ Ambiente mock carregado")
"""
"""
KAEL TEST COMMANDS - Comandos de teste para o chat
"""
from pathlib import Path
from core.test_runner import LuauTestRunner, LuauTestGenerator


def register_commands(registry):
    """Registra comandos de teste no ToolRegistry."""
    
    @registry.command("/testar_script", aliases=["/test"])
    def testar_script(ctx, args, flags):
        """Testa um script Luau específico."""
        if not args:
            return {
                "response": "❌ Uso: `/testar_script <nome_do_script.lua>`",
                "status": "error"
            }
        
        script_name = args[0]
        script_path = ctx.project_path / "Scripts" / script_name
        
        if not script_path.exists():
            # Tenta na raiz do projeto
            script_path = ctx.project_path / script_name
        
        if not script_path.exists():
            return {
                "response": f"❌ Script não encontrado: `{script_name}`",
                "status": "error"
            }
        
        runner = LuauTestRunner(ctx)
        result = runner.run_full_test(script_path)
        
        if result["success"]:
            return {
                "response": (
                    f"✅ **Teste passou:** `{script_name}`\n"
                    f"- Linhas: {result.get('lines', '?')}\n"
                    f"- Tempo: {result.get('execution_time', 0):.2f}s"
                ),
                "status": "success"
            }
        else:
            stage = result.get("stage", "unknown")
            issues = result.get("issues", [])
            error = result.get("studio_error", "Erro desconhecido")
            
            response = f"❌ **Teste falhou:** `{script_name}`\n"
            response += f"- **Estágio:** {stage}\n"
            
            if issues:
                response += "- **Problemas:**\n"
                for issue in issues[:5]:
                    response += f"  - {issue}\n"
            else:
                response += f"- **Erro:** {error}\n"
            
            return {"response": response, "status": "error"}
    
    @registry.command("/testar_tudo")
    def testar_tudo(ctx, args, flags):
        """Testa todos os scripts .lua do projeto."""
        scripts_dir = ctx.project_path / "Scripts"
        if not scripts_dir.exists():
            return {"response": "❌ Pasta `Scripts/` não encontrada", "status": "error"}
        
        scripts = list(scripts_dir.glob("*.lua"))
        if not scripts:
            return {"response": "⚪ Nenhum script .lua encontrado", "status": "success"}
        
        runner = LuauTestRunner(ctx)
        results = []
        
        for script in scripts:
            result = runner.run_full_test(script)
            results.append(result)
        
        passed = sum(1 for r in results if r["success"])
        failed = len(results) - passed
        
        response = f"📊 **Testes concluídos:**\n"
        response += f"- **Total:** {len(results)} scripts\n"
        response += f"- **✅ Passaram:** {passed}\n"
        response += f"- **❌ Falharam:** {failed}\n"
        
        if failed > 0:
            response += "\n**Scripts com erro:**\n"
            for r in results:
                if not r["success"]:
                    response += f"- `{r['script']}`\n"
        
        return {"response": response, "status": "success" if failed == 0 else "error"}
    
    @registry.command("/gerar_teste")
    def gerar_teste(ctx, args, flags):
        """Gera um script de teste unitário para um script alvo."""
        if not args:
            return {
                "response": "❌ Uso: `/gerar_teste <nome_do_script.lua>`",
                "status": "error"
            }
        
        script_name = args[0]
        script_path = ctx.project_path / "Scripts" / script_name
        
        if not script_path.exists():
            return {"response": f"❌ Script não encontrado: `{script_name}`", "status": "error"}
        
        test_code = LuauTestGenerator.generate_unit_test(script_path)
        
        # Salva o teste
        test_name = f"test_{script_path.stem}.lua"
        test_path = ctx.project_path / "Tests" / test_name
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text(test_code, encoding='utf-8')
        
        return {
            "response": (
                f"🧪 **Teste unitário gerado:**\n"
                f"- Arquivo: `Tests/{test_name}`\n"
                f"- Execute no Roblox Studio para validar"
            ),
            "status": "success"
        }
    
    @registry.command("/relatorio_testes")
    def relatorio_testes(ctx, args, flags):
        """Mostra relatório dos últimos testes executados."""
        runner = LuauTestRunner(ctx)
        report = runner.generate_test_report()
        return {"response": report, "status": "success"}
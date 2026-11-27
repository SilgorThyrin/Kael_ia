"""Comandos de sistema do Kael."""

TOOL_NAME = "system"


def _ok(mod):
    try:
        __import__(mod)
        return "🟢"
    except Exception:
        return "🔴"


def status(ctx, args, flags):
    mem_files = list(ctx.memory_dir.glob('*'))
    return {
        "response": (
            "✅ **Status do Sistema Kael v9.6**\n"
            f"- **Servidor API:** Online (porta 8000)\n"
            f"- **Ollama:** {'🟢 Online' if ctx.ollama_online() else '🔴 Offline'}\n"
            f"- **Memória Vetorial:** {'🟢 Ativa' if ctx.memory else '🟡 Desativada'}\n"
            f"- **Compressor:** {'🟢 Ativo' if ctx.compressor else '🟡 Desativado'}\n"
            f"- **Game Bridge:** {_ok('tools.game_bridge')} | **Web:** {_ok('tools.web_research')} | **Flutuantes:** {_ok('tools.floating_detector')}\n"
            f"- **Tools carregadas:** {', '.join(sorted(ctx.registry.tools.keys()))}\n"
            f"- **Arquivos na Memória:** {len(mem_files)}\n"
            f"- **Projeto Ativo:** `{ctx.project_path.name}`\n"
            f"- **Política de Escrita:** `{ctx.permission_policy.mode}`\n"
            f"- **Modo Autônomo:** {'🟢 ATIVO' if ctx.autonomous['active'] else '⚪ Inativo'}"
        ),
        "thinking": "Comando /status executado pela tool system.",
        "status": "success"
    }


def teste_conexao(ctx, args, flags):
    ok = ctx.ollama_online()
    return {
        "response": (
            "📡 **Teste de Conexão**\n"
            f"- Ollama (8080): {'🟢 Respondendo' if ok else '🔴 Offline'}\n"
            "- API Kael (8000): 🟢 Respondendo\n"
            f"- Tools registradas: {len(ctx.registry.commands)} comandos"
        ),
        "thinking": "Ping executado pela tool system.",
        "status": "success" if ok else "error"
    }


def help_cmd(ctx, args, flags):
    return {
        "response": ctx.registry.help_text(),
        "thinking": "Help auto-gerado pelo Registry.",
        "status": "success"
    }


def gerenciar(ctx, args, flags):
    project = args[0] if args else "Ecos_de_Aethelgard"
    ctx.autonomous["active"] = True
    ctx.autonomous["project"] = project
    return {
        "response": f"🤖 **Modo Autônomo ATIVADO** em `{project}`. Use `/parar_gerenciamento` para parar.",
        "thinking": "Estado global alterado.",
        "status": "success"
    }


def parar(ctx, args, flags):
    ctx.autonomous["active"] = False
    ctx.autonomous["project"] = None
    return {
        "response": "⏹️ **Modo Autônomo DESATIVADO.**",
        "thinking": "Modo autônomo desligado.",
        "status": "success"
    }


COMMANDS = {
    "/status": {"handler": status, "desc": "Saúde real do sistema", "capability": "read"},
    "/teste_conexao": {"handler": teste_conexao, "desc": "Ping no Ollama e módulos", "capability": "read"},
    "/help": {"handler": help_cmd, "desc": "Menu de comandos", "capability": "read"},
    "/ajuda": {"handler": help_cmd, "desc": "Alias de /help", "capability": "read"},
    "/gerenciar_jogo": {"handler": gerenciar, "desc": "Ativa modo autônomo", "capability": "control"},
    "/parar_gerenciamento": {"handler": parar, "desc": "Desativa modo autônomo", "capability": "control"},
}
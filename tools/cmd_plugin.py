"""Gerenciador de plugins estilo Claude Code via chat (/plugin)."""

TOOL_NAME = "plugin"


def _parse_tokens(args) -> list[str]:
    if isinstance(args, str):
        return args.strip().split()
    if isinstance(args, (list, tuple)):
        return [str(a).strip() for a in args if str(a).strip()]
    return []


def cmd_plugin(ctx, args=None, flags=None):
    pm = getattr(ctx, "plugin_manager", None)
    if not pm:
        return {
            "response": "⚠️ Plugin Manager não inicializado no servidor.",
            "thinking": "plugin_manager ausente em ctx.",
            "status": "error",
        }

    tokens = _parse_tokens(args)
    acao = tokens[0].lower() if tokens else "list"
    alvo = tokens[1] if len(tokens) > 1 else ""

    if acao in ("list", "listar"):
        if not pm.plugins:
            return {
                "response": "🔌 Nenhum plugin instalado em `plugins/`. Use `/plugin install <url_git>`.",
                "thinking": "Lista de plugins vazia.",
                "status": "information",
            }
        linhas = ["🔌 **Plugins Instalados:**"]
        for p in pm.plugins.values():
            st = "🟢" if p["enabled"] else "⚪"
            linhas.append(
                f"- {st} **{p['id']}** v{p['version']} — {p['description'] or 'Sem descrição'} "
                f"(tools: {p['tools_count']}, hooks: {p['hooks_count']})"
            )
        linhas.append("\nComandos: `/plugin enable <id>`, `/plugin disable <id>`, `/plugin reload`, `/plugin install <url>`")
        return {"response": "\n".join(linhas), "thinking": "Plugins listados.", "status": "success"}

    if acao in ("enable", "ativar") and alvo:
        if not pm.set_enabled(alvo, True):
            return {"response": f"❌ Plugin `{alvo}` não encontrado.", "thinking": "ID inválido.", "status": "error"}
        pm.discover_and_load(ctx, getattr(ctx, "registry", None))
        return {"response": f"🟢 Plugin `{alvo}` ativado e recarregado.", "thinking": "Plugin ativado.", "status": "success"}

    if acao in ("disable", "desativar") and alvo:
        if not pm.set_enabled(alvo, False):
            return {"response": f"❌ Plugin `{alvo}` não encontrado.", "thinking": "ID inválido.", "status": "error"}
        pm.discover_and_load(ctx, getattr(ctx, "registry", None))
        return {"response": f"⚪ Plugin `{alvo}` desativado.", "thinking": "Plugin desativado.", "status": "success"}

    if acao in ("reload", "recarregar"):
        pm.discover_and_load(ctx, getattr(ctx, "registry", None))
        return {"response": f"🔄 {len(pm.plugins)} plugin(s) recarregado(s).", "thinking": "Reload concluído.", "status": "success"}

    if acao in ("install", "instalar") and alvo:
        try:
            nome = pm.install_from_git(alvo)
            pm.discover_and_load(ctx, getattr(ctx, "registry", None))
            return {"response": f"✅ Plugin `{nome}` instalado e carregado.", "thinking": "Clone concluído.", "status": "success"}
        except Exception as exc:
            return {"response": f"❌ Falha ao instalar plugin: {exc}", "thinking": "Erro no install.", "status": "error"}

    return {
        "response": "Uso: `/plugin [list | enable <id> | disable <id> | reload | install <git_url>]`",
        "thinking": "Ajuda do comando /plugin.",
        "status": "information",
    }


COMMANDS = {
    "/plugin": {
        "handler": cmd_plugin,
        "desc": "Lista, ativa, desativa, recarrega ou instala plugins estilo Claude Code",
        "capability": "read",
    }
}

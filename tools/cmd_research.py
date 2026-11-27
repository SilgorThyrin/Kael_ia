"""Comando de pesquisa web de referência."""

TOOL_NAME = "research"

try:
    from tools.web_research import WebResearch
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


def pesquisar_jogos(ctx, args, flags):
    if not AVAILABLE:
        return {"response": "🔴 WebResearch indisponível.", "thinking": "Módulo ausente.", "status": "error"}
    import re as _re
    genero = args[0] if args else 'aventura'
    pesquisa = WebResearch().research_genre(genero, flags['ref'])
    if not pesquisa:
        return {"response": "⚠️ Nada encontrado na web. Verifique a conexão.",
                "thinking": "Pesquisa vazia.", "status": "error"}

    docs_dir = ctx.project_path / 'Docs'
    if not docs_dir.exists():
        docs_dir = ctx.memory_dir
    slug = _re.sub(r'[^\w\-]', '_', genero)
    fname = f"PESQUISA_{slug}.md"
    try:
        (docs_dir / fname).write_text(pesquisa, encoding='utf-8')
    except Exception as e:
        print(f"[RESEARCH] Erro ao salvar: {e}")

    return {
        "response": (
            f"🌐 **Pesquisa concluída!** Salva em `{docs_dir.name}/{fname}`.\n\n"
            f"**Descobertas:**\n{pesquisa[:1500]}\n\n*(relatório completo no arquivo)*"
        ),
        "thinking": "Pesquisa web real (DuckDuckGo + Wikipedia).",
        "status": "success"
    }


COMMANDS = {
    "/pesquisar_jogos": {"handler": pesquisar_jogos, "desc": "Pesquisa gênero + exemplos na web (--exemplos)", "capability": "network"},
}
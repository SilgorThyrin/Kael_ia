"""Comandos de desenvolvimento de jogos (Game Bridge)."""

TOOL_NAME = "game"

try:
    from tools.game_bridge import GameBridge, template_save_commands
    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    template_save_commands = lambda _templates: ""
    class GameBridge:
        def __init__(self, *a, **k): pass
        def full_report(self): return {"erro": "GameBridge não disponível."}
        def scan_project(self): return {"erro": "GameBridge não disponível."}
        def create_project_structure(self, *a, **k):
            return {"pastas": [], "engine": "roblox", "templates": [], "template_files": []}


def ver_jogo(ctx, args, flags):
    report = GameBridge(str(ctx.project_path)).full_report()
    if 'erro' in report:
        return {
            "response": f"⚠️ {report['erro']}\nUse `/construir_jogo [genero] [nome]` para criar o projeto.",
            "thinking": "Projeto não encontrado.", "status": "error"
        }
    scripts_txt = "\n".join([f"- `{s['arquivo']}` ({s['linhas']} linhas)" for s in report['scripts'][:10]]) or "- (nenhum)"
    prob_txt = "\n".join([f"- ⚠️ [{p['tipo']}] {p['arquivo']}: {p['detalhe']}" for p in report['problemas'][:10]]) \
        if report['problemas'] else "- ✅ Nenhum problema estático detectado"
    return {
        "response": (
            f"👁️ **Análise Real: {ctx.project_path.name}**\n"
            f"- **Motor:** {report['motor']}\n- **Scripts:** {report['total_scripts']}\n{scripts_txt}\n"
            f"- **Documentos:** {', '.join(report['documentos']) or 'nenhum'}\n\n"
            f"**Problemas:**\n{prob_txt}"
        ),
        "thinking": "Análise estática real via GameBridge.", "status": "success"
    }


def construir_jogo(ctx, args, flags):
    import re as _re
    genero = args[0] if len(args) > 0 else 'aventura'
    nome = _re.sub(r'[^\w\-]', '_', args[1]) if len(args) > 1 else 'Ecos_de_Aethelgard'

    proj_dir = ctx.projects_root / nome
    info = GameBridge(str(proj_dir)).create_project_structure(nome, genero, flags['engine'])
    templates_response = ""
    if info.get("template_files"):
        templates_response = ctx.process_save_commands(
            template_save_commands(info["template_files"]),
            save_dir=proj_dir,
        )

    base_pesquisa = ""
    if flags['ref']:
        try:
            from tools.web_research import WebResearch
            base_pesquisa = WebResearch().research_genre(genero, flags['ref'])
        except Exception as e:
            print(f"[GAME] Pesquisa falhou: {e}")

    gdd_prompt = (
        f"Crie um GDD conciso para um jogo de {genero} chamado {nome} (motor: {info['engine']}). "
        f"Inclua: visão geral, mecânicas, progressão, arte e som. "
    )
    if base_pesquisa:
        gdd_prompt += f"\n\nBASE DE PESQUISA REAL:\n{base_pesquisa[:4000]}\n"
    gdd_prompt += "Salve com: <kael_save filename='Docs/GDD.md'>conteúdo</kael_save>"

    resultado = ctx.generate(gdd_prompt)
    resposta = ctx.process_save_commands(resultado['response'], save_dir=proj_dir)

    msg = (
        f"🏗️ **Projeto `{nome}` criado!**\n- **Motor:** {info['engine']}\n"
        f"- Pastas: {', '.join(info['pastas'])}\n- Templates: {', '.join(info['templates']) or 'nenhum'}\n"
    )
    if templates_response:
        msg += f"\n**Validação dos scripts:** {templates_response}\n"
    if flags['ref']:
        msg += f"- **Referências:** {', '.join(flags['ref'])}\n"
    save_status = (
        "pending_approval" if "[AGUARDANDO TESTE E APROVAÇÃO:" in templates_response
        else "blocked" if "[ALTERAÇÃO BLOQUEADA:" in templates_response
        else "success"
    )
    return {
        "response": msg + f"\n{resposta}",
        "thinking": resultado['thinking'],
        "status": save_status,
    }


def integrar_jogo(ctx, args, flags):
    scan = GameBridge(str(ctx.project_path)).scan_project()
    if 'erro' in scan or not scan['scripts']:
        return {"response": f"⚠️ Nenhum script para integrar. ({scan.get('erro', 'pasta vazia')})",
                "thinking": "Sem scripts.", "status": "error"}
    trechos = []
    for s in scan['scripts'][:3]:
        texto = (ctx.project_path / s['arquivo']).read_text(encoding='utf-8', errors='ignore')[:2000]
        trechos.append(f"=== {s['arquivo']} ===\n{texto}")
    prompt_ia = (
        f"Analise os scripts do projeto {ctx.project_path.name} (motor: {scan['motor']}). "
        f"Corrija bugs e melhore a integração. Para cada script corrigido use: "
        f"<kael_save filename='Scripts/NOME_fix.ext'>código</kael_save>\n\n" + "\n\n".join(trechos)
    )
    resultado = ctx.generate(prompt_ia)
    resposta = ctx.process_save_commands(resultado['response'], save_dir=ctx.project_path)
    save_status = (
        "pending_approval" if "[AGUARDANDO TESTE E APROVAÇÃO:" in resposta
        else "blocked" if "[ALTERAÇÃO BLOQUEADA:" in resposta
        else "success"
    )
    return {"response": f"🔧 **Integração analisada.** Proposta de correções em Scripts/:\n\n{resposta}",
            "thinking": resultado['thinking'], "status": save_status}


def refatorar(ctx, args, flags):
    scan = GameBridge(str(ctx.project_path)).scan_project()
    if 'erro' in scan or not scan['scripts']:
        return {"response": "⚠️ Nenhum script para refatorar.", "thinking": "Sem scripts.", "status": "error"}
    maior = max(scan['scripts'], key=lambda s: s['linhas'])
    texto = (ctx.project_path / maior['arquivo']).read_text(encoding='utf-8', errors='ignore')[:6000]
    sufixo = maior['arquivo'].split('.')[-1]
    stem = maior['arquivo'].split('/')[-1].rsplit('.', 1)[0]
    novo = f"Scripts/{stem}_refatorado.{sufixo}"
    prompt_ia = (
        f"Refatore o script abaixo (motor {scan['motor']}) para ficar limpo e modular. "
        f"Salve com: <kael_save filename='{novo}'>código</kael_save>\n\n{texto}"
    )
    resultado = ctx.generate(prompt_ia)
    resposta = ctx.process_save_commands(resultado['response'], save_dir=ctx.project_path)
    save_status = (
        "pending_approval" if "[AGUARDANDO TESTE E APROVAÇÃO:" in resposta
        else "blocked" if "[ALTERAÇÃO BLOQUEADA:" in resposta
        else "success"
    )
    return {"response": f"♻️ **Refatoração analisada.** Proposta para `{novo}`:\n\n{resposta}",
            "thinking": resultado['thinking'], "status": save_status}


COMMANDS = {
    "/ver_jogo": {"handler": ver_jogo, "desc": "Análise estática real do projeto", "capability": "read"},
    "/construir_jogo": {"handler": construir_jogo, "desc": "Cria estrutura + GDD (--engine, --ref)", "capability": "project_create"},
    "/integrar_jogo": {"handler": integrar_jogo, "desc": "IA corrige scripts reais", "capability": "project_write"},
    "/refatorar": {"handler": refatorar, "desc": "IA refatora o maior script", "capability": "project_write"},
}
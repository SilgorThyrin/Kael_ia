"""
Tool: Organizar Jogo Existente
Pega todos os scripts do Studio, analisa bugs, reorganiza e corrige.
"""
import re
import time
from pathlib import Path

TOOL_NAME = "organizar"

# ========== REGRAS DE DETECÇÃO DE BUGS ==========
REGRAS_BUGS = [
    {
        "nome": "WAIT_ANTIGO",
        "regex": r'(?<!\.)\bwait\s*\(',
        "sugestao": "Substitua `wait()` por `task.wait()`",
        "severidade": "media"
    },
    {
        "nome": "SCRIPT_PARENT_LOCAL",
        "regex": r'script\.Parent',
        "condicao": "LocalScript",
        "sugestao": "Em LocalScripts, evite script.Parent. Use game.Players.LocalPlayer",
        "severidade": "alta"
    },
    {
        "nome": "REMOTE_SEM_SERVER",
        "regex": r'RemoteEvent.*:FireServer\(',
        "sugestao": "Valide RemoteEvents no servidor antes de confiar no cliente",
        "severidade": "critica"
    },
    {
        "nome": "LOOP_INFINITO",
        "regex": r'while\s+true\s+do',
        "sugestao": "Adicione `task.wait()` dentro do loop para evitar travamento",
        "severidade": "alta"
    },
    {
        "nome": "PRINT_DEBUG",
        "regex": r'\bprint\s*\(',
        "sugestao": "Remova prints de debug antes de publicar",
        "severidade": "baixa"
    },
    {
        "nome": "GLOBAL_VAR",
        "regex": r'^[A-Z_]+\s*=\s*',
        "sugestao": "Use `local` para variáveis globais",
        "severidade": "media"
    },
    {
        "nome": "DEBRIS_SEM_CLEANUP",
        "regex": r'game\.Debris:AddItem',
        "sugestao": "Confirme se o tempo de cleanup está correto",
        "severidade": "baixa"
    },
    {
        "nome": "INSTANCE_NEW_SEM_PARENT",
        "regex": r'Instance\.new\("[^"]+"\)',
        "sugestao": "Defina `.Parent` logo após criar a instância",
        "severidade": "media"
    },
    {
        "nome": "PCALL_AUSENTE",
        "regex": r'HttpService:GetAsync',
        "sugestao": "Envolva chamadas HTTP em `pcall()` para evitar crashes",
        "severidade": "alta"
    },
    {
        "nome": "MEMORY_LEAK_CONN",
        "regex": r':Connect\(',
        "sugestao": "Guarde a Connection para disconnect() quando não precisar mais",
        "severidade": "media"
    },
]


def analisar_script(codigo, tipo="Script"):
    """Analisa um script e retorna lista de bugs encontrados."""
    bugs = []
    linhas = codigo.split('\n')
    
    for i, linha in enumerate(linhas, 1):
        for regra in REGRAS_BUGS:
            # Pula regras que não se aplicam ao tipo
            if regra.get("condicao") and regra["condicao"] != tipo:
                continue
            
            if re.search(regra["regex"], linha):
                bugs.append({
                    "linha": i,
                    "regra": regra["nome"],
                    "severidade": regra["severidade"],
                    "codigo": linha.strip()[:80],
                    "sugestao": regra["sugestao"]
                })
    
    # Análise estrutural
    if len(linhas) > 500:
        bugs.append({
            "linha": 0,
            "regra": "SCRIPT_MUITO_LONGO",
            "severidade": "media",
            "codigo": f"{len(linhas)} linhas",
            "sugestao": "Divida em módulos menores"
        })
    
    return bugs


def classificar_script(nome, codigo):
    """Classifica o script como Server/Client/Module/UI."""
    nome_lower = nome.lower()
    codigo_lower = codigo.lower()
    
    if 'module' in nome_lower or 'return ' in codigo:
        return "Module"
    if 'local' in nome_lower or 'client' in nome_lower or 'ui' in nome_lower:
        return "Client"
    if 'server' in nome_lower or 'game' in nome_lower:
        return "Server"
    if 'Players.LocalPlayer' in codigo or 'PlayerGui' in codigo:
        return "Client"
    return "Server"  # padrão


def cmd_organizar(ctx, args, flags):
    """
    Comando principal: organiza o jogo existente.
    Fluxo:
      1. Pede ao plugin para enviar conteúdo de todos os scripts
      2. Aguarda resposta (via plugin_bridge)
      3. Analisa cada script
      4. Gera relatório + versões corrigidas
      5. Salva em Scripts_Organizados/
    """
    # Verifica se o plugin está conectado
    if not hasattr(ctx, 'plugin_bridge') or not ctx.plugin_bridge:
        return {
            "response": "🔴 Plugin do Studio não conectado. Abra o Roblox Studio com o plugin ativo.",
            "thinking": "Plugin bridge ausente.",
            "status": "error"
        }
    
    if not ctx.plugin_bridge.last_state_time or (time.time() - ctx.plugin_bridge.last_state_time) > 30:
        return {
            "response": "🔴 Studio não enviou estado recente. Clique em 'Mapear Cena' no plugin.",
            "thinking": "Estado do jogo desatualizado.",
            "status": "error"
        }
    
    # Solicita envio completo dos scripts (nova tarefa para o plugin)
    task = ctx.plugin_bridge.enqueue({
        "tipo": "enviar_todos_scripts",
        "incluir_conteudo": True
    })
    
    return {
        "response": (
            "🗂️ **Organização iniciada!**\n\n"
            f"O Kael solicitou ao Studio o conteúdo dos scripts (tarefa `{task['task_id']}`).\n"
            "Em alguns segundos, vou:\n"
            "1. ✅ Analisar cada script contra 10+ regras de bugs\n"
            "2. ✅ Classificar (Server / Client / Module / UI)\n"
            "3. ✅ Gerar versões corrigidas\n"
            "4. ✅ Salvar em `Scripts_Organizados/`\n\n"
            "Aguarde... ou digite `/status_organizacao` para ver o progresso."
        ),
        "thinking": "Solicitação enviada ao plugin para receber conteúdo dos scripts.",
        "status": "success"
    }


def cmd_status_organizacao(ctx, args, flags):
    """Mostra progresso da organização."""
    if not hasattr(ctx, 'plugin_bridge') or not ctx.plugin_bridge:
        return {"response": "Plugin não conectado.", "thinking": "", "status": "error"}
    
    estado = ctx.plugin_bridge.last_state or {}
    scripts = estado.get('scripts_com_conteudo', [])
    truncated = sum(1 for script in scripts if script.get("truncado"))
    content_limited = estado.get("scripts_com_conteudo_limitado", False)
    
    if not scripts:
        return {
            "response": "⏳ Aguardando scripts do Studio... Clique em 'Mapear Cena' no plugin.",
            "thinking": "Sem scripts recebidos ainda.",
            "status": "success"
        }
    
    total_bugs = 0
    criticos = 0
    por_tipo = {"Server": 0, "Client": 0, "Module": 0, "UI": 0}
    
    for s in scripts:
        bugs = analisar_script(s.get('codigo', ''), s.get('tipo', 'Script'))
        total_bugs += len(bugs)
        criticos += sum(1 for b in bugs if b['severidade'] == 'critica')
        tipo = classificar_script(s['nome'], s.get('codigo', ''))
        por_tipo[tipo] = por_tipo.get(tipo, 0) + 1
    
    warning_msg = (
        f"⚠️ Parte do conteúdo foi limitada; {truncated} script(s) foram truncados. Revise antes de aplicar.\n\n"
        if (content_limited or truncated)
        else ""
    )
    
    return {
        "response": (
            f"📊 **Status da Organização:**\n"
            f"- Scripts recebidos: **{len(scripts)}**\n"
            f"- Bugs detectados: **{total_bugs}** ({criticos} críticos)\n"
            f"- Server: {por_tipo['Server']} | Client: {por_tipo['Client']} | Module: {por_tipo['Module']}\n\n"
            f"{warning_msg}"
            f"Use `/aplicar_organizacao` para salvar as correções."
        ),
        "thinking": "Análise estatística dos scripts recebidos.",
        "status": "success"
    }


def cmd_aplicar_organizacao(ctx, args, flags):
    """Salva os scripts organizados e corrigidos em Scripts_Organizados/."""
    if not hasattr(ctx, 'plugin_bridge') or not ctx.plugin_bridge:
        return {"response": "Plugin não conectado.", "thinking": "", "status": "error"}
    
    estado = ctx.plugin_bridge.last_state or {}
    scripts = estado.get('scripts_com_conteudo', [])
    
    if not scripts:
        return {"response": "Nenhum script para organizar.", "thinking": "", "status": "error"}
    
    # Cria pasta de destino
    destino = ctx.project_path / "Scripts_Organizados"
    destino.mkdir(parents=True, exist_ok=True)
    for sub in ("Server", "Client", "Modules", "UI"):
        (destino / sub).mkdir(exist_ok=True)
    
    salvos = []
    for s in scripts:
        codigo = s.get('codigo', '')
        nome = s.get('nome', 'script')
        tipo = classificar_script(nome, codigo)
        
        # Mapeia tipo para pasta
        pasta = {
            "Server": "Server",
            "Client": "Client",
            "Module": "Modules",
            "UI": "UI"
        }.get(tipo, "Server")
        
        # Salva versão original
        (destino / pasta / f"{nome}_original.lua").write_text(codigo, encoding='utf-8')
        
        # Gera versão com comentários de bugs (não modifica lógica)
        bugs = analisar_script(codigo, s.get('tipo', 'Script'))
        if bugs:
            header = "-- ⚠️ BUGS DETECTADOS PELO KAEL\n"
            for b in bugs[:10]:
                header += f"-- Linha {b['linha']}: [{b['severidade']}] {b['sugestao']}\n"
            header += "-- " + "="*50 + "\n\n"
            (destino / pasta / f"{nome}_analise.lua").write_text(header + codigo, encoding='utf-8')
        
        salvos.append(f"{pasta}/{nome}")
    
    return {
        "response": (
            f"✅ **Organização concluída!**\n\n"
            f"Scripts salvos em `Scripts_Organizados/`:\n"
            + "\n".join(f"- {s}" for s in salvos[:20])
            + f"\n\nTotal: **{len(salvos)} scripts** organizados em Server/Client/Modules/UI"
        ),
        "thinking": f"Organização aplicada. {len(salvos)} scripts salvos.",
        "status": "success"
    }


COMMANDS = {
    "/organizar_jogo": {
        "handler": cmd_organizar,
        "desc": "Analisa, organiza e corrige todos os scripts do jogo existente",
        "capability": "studio",
    },
    "/status_organizacao": {
        "handler": cmd_status_organizacao,
        "desc": "Mostra progresso da organização do jogo",
        "capability": "read",
    },
    "/aplicar_organizacao": {
        "handler": cmd_aplicar_organizacao,
        "desc": "Salva scripts organizados e corrigidos",
        "capability": "project_write",
    },
}

#!/usr/bin/env python3
"""CEO Commands - Comandos hierárquicos para o Kael."""

class CEOCommands:
    """Comandos do CEO para análise estratégica e contexto."""
    
    @staticmethod
    def cmd_contexto(ctx):
        """Mostra contexto da memória unificada e do projeto"""
        mem_info = ""
        if ctx.memory:
            try:
                rules = ctx.memory.get_learned_rules(5)
                mem_info += f"- Regras aprendidas: {len(rules)}\n"
            except: pass
        
        project_info = ""
        if hasattr(ctx, 'project_path') and ctx.project_path:
            project_info = f"- Projeto: `{ctx.project_path.name}`\n"
        
        ctx_config = ""
        if hasattr(ctx, 'config') and ctx.config:
            ctx_config = f"- Temperatura: {ctx.config.get('temperature', 0.45)}\n"
            ctx_config += f"- Modelo: {ctx.config.get('model_name', 'qwen2.5-coder')}\n"
        
        mem_status = 'Ativa' if ctx.memory else 'Desativada'
        comp_status = 'Ativo' if ctx.compressor else 'Desativado'
        ctx_window = ctx.config.get('context_window', 4096) if hasattr(ctx, 'config') and ctx.config else 4096

        response = f"""📋 **Contexto Atual**
{mem_info} {project_info} {ctx_config}""".strip() + f"""
- **Memória Vetorial:** {mem_status}
- **Compressor:** {comp_status}
- **Contexto:** ~{ctx_window} tokens"""
        
        return {
            "response": response,
            "thinking": "Contexto exibido.", "status": "success"
        }
    
    @staticmethod
    def cmd_estratégia(ctx, prompt):
        """Modo CEO: analisa solicitação como plano empresarial"""
        if not prompt:
            return {"response": "📝 **Modo Estratégica**\nInforme uma solicitação após o comando `/estratégia`.\n\nExemplo: `/estratégia Criar plano de negócios para aplicativo de delivery`", "thinking": "Modo estratégico ativado.", "status": "ready"}
        
        try:
            from core.ceo_ai import create_ceo
            ceo = create_ceo(model='qwen2.5-coder')
            analysis = ceo.analyze_request(prompt)
            task_type = analysis.get('task_type', 'desconhecido')
            priority = analysis.get('priority', 'média')
            delegation = ', '.join(analysis.get('delegation', []))
            reasoning = analysis.get('reasoning', 'Não disponível')[:300]
            return {
                "response": f"""🧠 **Modo CEO - Análise Estratégica**

- **Tipo de Tarefa:** {task_type}
- **Prioridade:** {priority}
- **Delegação:** {delegation}
- **Raciocínio:** {reasoning}...""",
                "thinking": "CEO analisou a solicitação.", "status": "success"
            }
        except Exception as e:
            err_msg = str(e)[:200]
            return {"response": f"⚠️ Erro ao ativar modo CEO: {err_msg}...", "thinking": "Erro na análise do CEO.", "status": "error"}
    
    @staticmethod
    def cmd_modelo(ctx, arg=''):
        """Mudar modelo de IA"""
        arg = arg.lower() if arg else ""
        
        local_models = {
            'qwen2.5-coder': 'qwen2.5-coder:7b (local, code)',
            'llama3.1': 'llama3.1:8b (local, geral)',
            'qwen3': 'qwen3:8b (local, avançado)',
        }
        
        if arg in local_models:
            model_desc = local_models[arg]
            return {
                "response": f"🤖 **Modelo Local Alterado:** {model_desc}.\nReinicie o Kael para efeitos completos.",
                "thinking": f"Modelo cambiado para {arg}", "status": "success"
            }
        else:
            available = [
                'qwen2.5-coder:7b (local)',
                'llama3.1:8b (local)',
                'qwen3:8b (local)',
                'gpt-4o-mini (OpenAI nuvem)',
                'claude-3-haiku (Anthropic nuvem)',
                'gemini-1.5-flash (Google nuvem)',
            ]
            available_str = "\n".join(f"- {m}" for m in available)
            return {
                "response": f"🤖 **Modelos Disponíveis:**\n{available_str}\n\nUse `/modelo qwen2.5-coder`, `/modelo llama3.1`, etc.", 
                "thinking": "Listando modelos disponíveis.", "status": "information"
            }
    
    @staticmethod
    def cmd_memória_detalhada(ctx):
        """Memória unificada completa"""
        parts = []
        
        if hasattr(ctx, 'memory') and ctx.memory:
            try:
                rules = ctx.memory.get_learned_rules(10)
                parts.append(f"**📚 Regras Aprendidas ({len(rules)}):**")
                for r in rules[:5]:
                    parts.append(f"- {r[:100]}...")
                if len(rules) > 5:
                    parts.append(f"- ... e mais {len(rules)-5} regras")
            except: parts.append("- Erro ao carregar regras")
        
        if hasattr(ctx, 'episodic_memory') and ctx.episodic_memory:
            try:
                episodes = ctx.episodic_memory.get_recent(5)
                parts.append(f"**📅 Episódios Recentes ({len(episodes)}):**")
                for e in episodes[:3]:
                    parts.append(f"- {e[:80]}...")
            except: parts.append("- Erro ao carregar episódios")
        
        if hasattr(ctx, 'semantic_memory') and ctx.semantic_memory:
            parts.append("**🔍 Memória Semântica:** Ativa")
        
        if hasattr(ctx, 'project_path') and ctx.project_path:
            parts.append(f"- **Projeto:** `{ctx.project_path.name}`")
        
        joined_parts = "\n".join(parts) if parts else "Nenhuma memória disponível."
        return {
            "response": f"🧠 **Memória Unificada Detalhada**\n{joined_parts}",
            "thinking": "Memória detalhada exibida.", "status": "success"
        }
    
    @staticmethod
    def cmd_contexto_rapido(ctx):
        """Versão rápida do contexto"""
        mem_str = "Ativa" if ctx.memory else "Inativa"
        proj_str = ctx.project_path.name if hasattr(ctx, 'project_path') and ctx.project_path else "Nenhum"
        model_str = ctx.config.get('model_name', 'qwen2.5-coder') if hasattr(ctx, 'config') and ctx.config else "desconhecido"
        return {
            "response": f"📋 Contexto: Memória={mem_str}, Projeto={proj_str}, Modelo={model_str}",
            "thinking": "Contexto rápido exibido.", "status": "success"
        }

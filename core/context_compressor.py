"""
Compressor de Contexto Nativo do Kael
Estratégia: Truncamento inteligente + priorização de memórias
Não depende de bibliotecas externas.
"""

class ContextCompressor:
    def __init__(self, max_chars: int = 12000):
        """
        max_chars: limite aproximado de caracteres (~3000 tokens, já que 1 token ≈ 4 chars)
        """
        if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars <= 0:
            raise ValueError("max_chars deve ser um inteiro positivo.")
        self.max_chars = max_chars
    
    def estimate_tokens(self, text: str) -> int:
        """Estima quantidade de tokens (1 token ≈ 4 caracteres em português/inglês)"""
        return len(text) // 4
    
    def truncate_history(self, history: list, max_messages: int = 5) -> list:
        """Mantém apenas as últimas N mensagens do histórico"""
        return history[-max_messages:] if len(history) > max_messages else history
    
    def truncate_memories(self, memories: list, max_memories: int = 3) -> list:
        """Mantém apenas as top N memórias mais relevantes"""
        return memories[:max_memories] if len(memories) > max_memories else memories
    
    def build_context(self, user_message: str, history: list, memories: list, 
                     system_prompt: str = "") -> str:
        """
        Constrói o contexto final respeitando o limite de caracteres.
        Sistema e mensagem atual sao obrigatorios; memorias precedem o historico.
        """
        current = f"=== MENSAGEM ATUAL ===\nUsuário: {user_message}"
        mandatory_parts = []
        if system_prompt:
            mandatory_parts.append(f"=== SISTEMA ===\n{system_prompt}")
        mandatory_parts.append(current)
        full_context = "\n\n".join(mandatory_parts)
        if len(full_context) > self.max_chars:
            raise ValueError(
                "O prompt de sistema e a mensagem atual excedem o limite de contexto."
            )
        
        optional_parts = []
        if memories:
            mem_text = "\n".join([
                f"[{m.get('category', 'geral')}] {m['content']}" 
                for m in memories
            ])
            optional_parts.append(f"=== MEMÓRIAS RELEVANTES ===\n{mem_text}")
        
        if history:
            hist_lines = []
            for msg in history:
                role = "Usuário" if msg.get('role') == 'user' else "Kael"
                hist_lines.append(f"{role}: {msg.get('content', '')}")
            optional_parts.append("=== HISTÓRICO RECENTE ===\n" + "\n".join(hist_lines))

        for section in optional_parts:
            separator = "\n\n"
            available = self.max_chars - len(full_context) - len(separator)
            if len(section) <= available:
                full_context += separator + section
                continue
            if available > 0:
                marker = "\n...[contexto truncado]..."
                if available > len(marker):
                    section = section[:available - len(marker)] + marker
                else:
                    section = section[:available]
                full_context += separator + section
            break
        
        tokens_estimados = self.estimate_tokens(full_context)
        print(f"[COMPRESSOR] Contexto final: ~{tokens_estimados} tokens ({len(full_context)} chars)")
        
        return full_context
    
    def compress(self, text: str) -> str:
        """Compressão simples por truncamento (fallback)"""
        if len(text) <= self.max_chars:
            return text
        marker = "\n...[truncado]..."
        if self.max_chars <= len(marker):
            return marker[:self.max_chars]
        return text[:self.max_chars - len(marker)] + marker


# Teste rápido
if __name__ == "__main__":
    compressor = ContextCompressor(max_chars=12000)
    
    historico = [
        {"role": "user", "content": "Olá"},
        {"role": "assistant", "content": "Oi! Como posso ajudar?"},
    ]
    memorias = [
        {"category": "cronograma", "content": "Cronograma de 3 dias para Ecos de Aethelgard"},
    ]
    
    contexto = compressor.build_context(
        user_message="Crie um novo cronograma",
        history=historico,
        memories=memorias,
        system_prompt="Você é o Kael, agente de desenvolvimento de jogos."
    )
    
    print("\n=== CONTEXTO GERADO ===")
    print(contexto)
    print(f"\nTokens estimados: {compressor.estimate_tokens(contexto)}")
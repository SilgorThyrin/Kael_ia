# -*- coding: utf-8 -*-
"""
kael_anti_hallucination.py - Camada de Defesa contra Alucinação
================================================================
Implementa Reflexion (Memória 20) + Prompt Hardening.
Não consome VRAM extra: reutiliza o mesmo Qwen3 8B em modo crítico.
"""

import re
import json

# ============================================================
# 1. REGRAS ANTI-ALUCINAÇÃO (Prompt Hardening)
# ============================================================
ANTI_HALLUCINATION_RULES = """
REGRAS CRÍTICAS DE HONESTIDADE (SIGA SEMPRE):
1. Se você NÃO SABER algo com CERTEZA ABSOLUTA, responda: "[INCERTEZA] Não tenho informação confiável sobre X."
2. NUNCA invente nomes de funções, classes ou APIs. Se não tiver certeza da sintaxe exata, diga "[VERIFICAR] Preciso consultar a documentação oficial de X."
3. NUNCA invente arquivos, caminhos ou módulos que não foram listados no contexto.
4. Se o usuário pedir algo impossível no Roblox/Godot, diga "[IMPOSSÍVEL] Isso não é suportado porque..." em vez de tentar inventar uma solução.
5. Antes de escrever código, liste mentalmente: "Quais APIs estou usando? Tenho certeza de que existem?"
6. Cite a fonte de cada afirmação técnica (ex: "Segundo a documentação do Roblox...").
"""

# ============================================================
# 2. DETECÇÃO DE PADRÕES DE ALUCINAÇÃO
# ============================================================
HALLUCINATION_PATTERNS = [
    r"\bcomo (um|uma) (modelo|IA|assistente) de linguagem\b",
    r"\bnão (posso|consigo) (acessar|verificar|testar)\b",
    r"\bsegundo (meu|meus) (conhecimento|treinamento)\b",
    r"\bna minha (versão|base de dados)\b",
    r"\bAPI inexistente|função inexistente\b",  # placeholder
    r"\b(?:def|function|class)\s+[A-Z][a-z]+[A-Z]\w*\b",  # camelCase suspeito em APIs Roblox
]

def detectar_alucinacao(texto: str) -> list:
    """Retorna lista de trechos suspeitos encontrados no output."""
    encontrados = []
    for padrao in HALLUCINATION_PATTERNS:
        matches = re.finditer(padrao, texto, re.IGNORECASE)
        for m in matches:
            encontrados.append({
                "padrao": padrao,
                "trecho": m.group(0),
                "posicao": m.start()
            })
    return encontrados

# ============================================================
# 3. REFLEXION: O MODELO REVISA O PRÓPRIO OUTPUT
# ============================================================
REFLEXION_PROMPT_TEMPLATE = """
Você é o CRÍTICO INTERNO do Kael. Sua única função é revisar a resposta abaixo e identificar alucinações.

CONTEXTO ORIGINAL DO USUÁRIO:
{contexto}

RESPOSTA GERADA PELO KAEL:
{resposta}

TAREFA: Analise a resposta e responda APENAS em JSON neste formato:
{{
  "nota_honestidade": <0 a 10>,
  "alucinacoes_detectadas": [
    {{"tipo": "api_inventada|caminho_falso|afirmacao_duvidosa", "trecho": "...", "sugestao": "..."}}
  ],
  "veredito": "APROVADO|REVISAR|REJEITADO",
  "resposta_corrigida": "<versão corrigida se necessário, ou null>"
}}

REGRAS DE AVALIAÇÃO:
- Nota 10: resposta 100% verificável e honesta.
- Nota < 6: contém APIs, funções ou caminhos inventados.
- Se detectar alucinação, sugira a correção ou marque como "[VERIFICAR]".
"""

def executar_reflexion(fn_llm, contexto_usuario: str, resposta_gerada: str, temperatura_critica: float = 0.1):
    """
    Chama o LLM em modo crítico (temperatura baixa) para revisar a resposta.
    Retorna um dict com a análise ou None se falhar.
    """
    prompt = REFLEXION_PROMPT_TEMPLATE.format(
        contexto=contexto_usuario[:1500],
        resposta=resposta_gerada[:3000]
    )
    
    try:
        resposta_critica = fn_llm(prompt, temperatura=temperatura_critica)
        
        # Extrai JSON da resposta (tolerante a markdown)
        match = re.search(r'```(?:json)?\s*\n(.*?)\n```', resposta_critica, re.DOTALL)
        texto_json = match.group(1) if match else resposta_critica
        
        # Tenta encontrar JSON bruto
        inicio = texto_json.find("{")
        fim = texto_json.rfind("}")
        if inicio >= 0 and fim > inicio:
            texto_json = texto_json[inicio:fim+1]
        
        analise = json.loads(texto_json)
        return analise
        
    except Exception as e:
        return {
            "nota_honestidade": 5,
            "alucinacoes_detectadas": [],
            "veredito": "ERRO_NA_ANALISE",
            "erro": str(e)[:200]
        }

# ============================================================
# 4. PIPELINE COMPLETO: GERAR → DETECTAR → REFLEXION → ENTREGAR
# ============================================================
def gerar_com_defesa(fn_llm, prompt_usuario: str, contexto_historico: str = "", 
                     max_tentativas: int = 2, temperatura_base: float = 0.3):
    """
    Pipeline anti-alucinação completo.
    Retorna a resposta final com selo de qualidade.
    """
    prompt_final = ANTI_HALLUCINATION_RULES + "\n\n" + contexto_historico + "\n\n" + prompt_usuario
    
    for tentativa in range(max_tentativas):
        # 1. Gera resposta
        resposta = fn_llm(prompt_final, temperatura=temperatura_base)
        
        # 2. Detecção rápida por regex
        suspeitas_regex = detectar_alucinacao(resposta)
        
        # 3. Reflexion (crítica do próprio modelo)
        analise = executar_reflexion(fn_llm, prompt_usuario, resposta)
        
        nota = analise.get("nota_honestidade", 0)
        veredito = analise.get("veredito", "REVISAR")
        
        # 4. Critério de aprovação: nota >= 8 OU veredito APROVADO
        if nota >= 8 or veredito == "APROVADO":
            return {
                "resposta": resposta,
                "nota_final": nota,
                "tentativas": tentativa + 1,
                "status": "APROVADO",
                "alucinacoes_regex": len(suspeitas_regex)
            }
        
        # 5. Se reprovou e há resposta corrigida pelo crítico, usa ela
        if analise.get("resposta_corrigida"):
            resposta = analise["resposta_corrigida"]
            break
    
    return {
        "resposta": resposta,
        "nota_final": nota,
        "tentativas": max_tentativas,
        "status": "COM_RESSALVAS" if nota >= 6 else "REJEITADO",
        "alucinacoes_regex": len(suspeitas_regex),
        "analise_critica": analise
    }
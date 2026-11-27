"""
KAEL UNIFIED MEMORY v1.0
========================
Unifica a memória legada (JSON) com a memória vetorial moderna.
Fornece:
  - Memória de curto prazo (contexto da conversa)
  - Memória de longo prazo (padrões de sucesso/fracasso)
  - Memória episódica (tarefas autônomas concluídas)
  - Memória semântica (busca vetorial por similaridade)
"""

import json
import os
import time
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from core.memory import KaelMemory
    HAS_VECTOR = True
except ImportError:
    HAS_VECTOR = False


class UnifiedMemory:
    """
    Camada única de memória para o Kael.
    """

    def __init__(self, base_dir: str, memory_dir: str):
        self.base_dir = Path(base_dir)
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        # Arquivos de memória legada
        self.rules_path = self.base_dir / "Conhecimento" / "regras_aprendidas.json"
        self.rules_path.parent.mkdir(parents=True, exist_ok=True)

        # Memória episódica (tarefas concluídas)
        self.episodic_path = self.memory_dir / "episodic.json"
        self._episodic_lock = threading.Lock()

        # Memória semântica (vetorial, se disponível)
        self.vector_memory = None
        if HAS_VECTOR:
            try:
                self.vector_memory = KaelMemory()
            except Exception:
                self.vector_memory = None

        # Cache em RAM para regras aprendidas
        self._learned_rules: List[Dict[str, Any]] = []
        self._load_learned_rules()

    # ======================================================================
    # MEMÓRIA DE REGRAS APRENDIDAS (Legado + Novo)
    # ======================================================================
    def _load_learned_rules(self):
        try:
            if self.rules_path.exists():
                with open(self.rules_path, "r", encoding="utf-8") as f:
                    self._learned_rules = json.load(f)
        except Exception:
            self._learned_rules = []

    def add_learned_rule(self, rule: str, error: str, source: str = "auto"):
        """Registra uma nova regra aprendida com contexto de erro."""
        entry = {
            "regra": rule,
            "erro": error[:200],
            "fonte": source,
            "timestamp": time.time(),
        }
        self._learned_rules.append(entry)
        self._learned_rules = self._learned_rules[-100:]

        try:
            with open(self.rules_path, "w", encoding="utf-8") as f:
                json.dump(self._learned_rules, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        if self.vector_memory:
            try:
                self.vector_memory.add_memory(
                    f"Regra aprendida: {rule}. Contexto do erro: {error}",
                    f"learned_rule:{int(time.time())}",
                )
            except Exception:
                pass

    def get_learned_rules(self, limit: int = 20) -> str:
        """Retorna as regras aprendidas formatadas para prompt."""
        if not self._learned_rules:
            return "Nenhuma regra aprendida ainda."
        recent = self._learned_rules[-limit:]
        linhas = []
        for r in recent:
            linhas.append(f"- {r['regra']} (erro: {r.get('erro', 'N/A')[:100]})")
        return "\n".join(linhas)

    # ======================================================================
    # MEMÓRIA EPISÓDICA (Tarefas autônomas)
    # ======================================================================
    def _load_episodic(self) -> List[Dict[str, Any]]:
        with self._episodic_lock:
            try:
                if self.episodic_path.exists():
                    with open(self.episodic_path, "r", encoding="utf-8") as f:
                        return json.load(f)
            except Exception:
                pass
            return []

    def _save_episodic(self, data: List[Dict[str, Any]]):
        with self._episodic_lock:
            try:
                with open(self.episodic_path, "w", encoding="utf-8") as f:
                    json.dump(data[-200:], f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    def add_episode(self, task_type: str, description: str,
                    resultado: str, sucesso: bool, projeto: str):
        """Registra um episódio de tarefa concluída."""
        episode = {
            "tipo": task_type,
            "descricao": description,
            "resultado": resultado[:500],
            "sucesso": sucesso,
            "projeto": projeto,
            "timestamp": time.time(),
        }
        data = self._load_episodic()
        data.append(episode)
        self._save_episodic(data)

        if self.vector_memory:
            try:
                status = "SUCESSO" if sucesso else "FALHA"
                texto = (
                    f"Episódio {status}: {task_type} - {description}. "
                    f"Resultado: {resultado[:200]}. Projeto: {projeto}"
                )
                self.vector_memory.add_memory(
                    texto, f"episode:{int(time.time())}"
                )
            except Exception:
                pass

    def get_similar_episodes(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Busca episódios similares por texto (fallback simples se não houver vetorial)."""
        data = self._load_episodic()
        if not data:
            return []

        if self.vector_memory:
            try:
                results = self.vector_memory.search_similar(query, limit=limit)
                return [{"tipo": "semantico", "descricao": r.get("content", "")[:200],
                         "sucesso": None} for r in results]
            except Exception:
                pass

        query_lower = query.lower()
        scored = []
        for ep in data:
            texto = f"{ep['tipo']} {ep['descricao']} {ep.get('resultado', '')}".lower()
            score = sum(1 for w in query_lower.split() if w in texto)
            if score > 0:
                scored.append((score, ep))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:limit]]

    # ======================================================================
    # MEMÓRIA SEMÂNTICA (Vetorial)
    # ======================================================================
    def search_semantic(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Busca semântica na memória vetorial."""
        if not self.vector_memory:
            return []
        try:
            return self.vector_memory.search_similar(query, limit=limit)
        except Exception:
            return []

    def add_semantic(self, content: str, metadata: str):
        """Adiciona conteúdo à memória semântica."""
        if self.vector_memory:
            try:
                self.vector_memory.add_memory(content, metadata)
            except Exception:
                pass

    # ======================================================================
    # CONTEXTO COMPLETO PARA PROMPT
    # ======================================================================
    def build_context_for_prompt(self, query: str, projeto: str = "") -> str:
        """
        Constrói um bloco de contexto enriquecido para ser injetado no prompt
        do modelo, combinando regras aprendidas, episódios similares e busca semântica.
        """
        partes = []

        # 1. Regras aprendidas
        regras = self.get_learned_rules(limit=15)
        if regras and regras != "Nenhuma regra aprendida ainda.":
            partes.append("### REGRAS APRENDIDAS (contexto de erros anteriores):\n" + regras)

        # 2. Episódios similares
        episodios = self.get_similar_episodes(query, limit=5)
        if episodios:
            ep_lines = []
            for ep in episodios:
                status = "✅" if ep.get("sucesso") else ("❌" if ep.get("sucesso") is False else "⚪")
                ep_lines.append(f"{status} {ep['tipo']}: {ep['descricao'][:120]}")
            partes.append("### EPISÓDIOS SIMILARES (tarefas anteriores):\n" + "\n".join(ep_lines))

        # 3. Busca semântica
        semantic = self.search_semantic(query, limit=5)
        if semantic:
            sem_lines = []
            for item in semantic:
                conteudo = item.get("content", "")[:200] if isinstance(item, dict) else str(item)[:200]
                sem_lines.append(f"• {conteudo}")
            partes.append("### MEMÓRIA SEMÂNTICA:\n" + "\n".join(sem_lines))

        if not partes:
            return ""
        return "\n\n".join(partes) + "\n\n"


# Instância singleton (será inicializada pelo contexto)
unified_memory: Optional[UnifiedMemory] = None

def init_unified_memory(base_dir: str, memory_dir: str) -> UnifiedMemory:
    global unified_memory
    unified_memory = UnifiedMemory(base_dir, memory_dir)
    return unified_memory

def get_unified_memory() -> Optional[UnifiedMemory]:
    return unified_memory
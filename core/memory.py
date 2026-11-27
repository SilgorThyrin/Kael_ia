import sqlite3
import threading
from pathlib import Path

class KaelMemory:
    MAX_SEARCH_CANDIDATES = 5000

    def __init__(self, db_path: str = "kael_memory.db"):
        self.db_path = Path(__file__).parent.parent / db_path
        self.model = None
        self._model_lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Inicializa o banco de dados com tabela de memórias"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON memories(category)')
            conn.commit()
        finally:
            conn.close()

    def _get_embedding(self, text: str) -> bytes:
        """Converte texto em vetor de embedding"""
        if self.model is None:
            with self._model_lock:
                if self.model is None:
                    from sentence_transformers import SentenceTransformer
                    self.model = SentenceTransformer('all-MiniLM-L6-v2', device="cpu")
        embedding = self.model.encode(text)
        return embedding.tobytes()

    def add_memory(self, content: str, category: str):
        """Adiciona uma nova memória ao banco"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            embedding = self._get_embedding(content)
            cursor.execute(
                'INSERT INTO memories (content, category, embedding) VALUES (?, ?, ?)',
                (content, category, embedding)
            )
            conn.commit()
        finally:
            conn.close()
        print(f"[MEMÓRIA] Adicionada: {category} - {content[:50]}...")

    def search_similar(self, query: str, category: str = None, limit: int = 3) -> list:
        """Busca entre as até 5.000 memórias mais recentes da categoria."""
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("limit deve ser um inteiro.")
        if limit <= 0:
            return []

        import numpy as np
        query_embedding = self._get_embedding(query)
        query_array = np.frombuffer(query_embedding, dtype=np.float32)

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            if category:
                cursor.execute(
                    'SELECT id, content, category, embedding FROM memories '
                    'WHERE category = ? ORDER BY id DESC LIMIT ?',
                    (category, self.MAX_SEARCH_CANDIDATES),
                )
            else:
                cursor.execute(
                    'SELECT id, content, category, embedding FROM memories '
                    'ORDER BY id DESC LIMIT ?',
                    (self.MAX_SEARCH_CANDIDATES,),
                )
            memories = cursor.fetchall()
        finally:
            conn.close()

        # Calcula similaridade com cada memória
        results = []
        for mem_id, content, cat, emb_bytes in memories:
            mem_array = np.frombuffer(emb_bytes, dtype=np.float32)
            # Similaridade cosseno
            similarity = np.dot(query_array, mem_array) / (
                np.linalg.norm(query_array) * np.linalg.norm(mem_array)
            )
            results.append({
                'id': mem_id,
                'content': content,
                'category': cat,
                'similarity': float(similarity)
            })

        # Ordena por similaridade (maior primeiro) e retorna top N
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:min(limit, self.MAX_SEARCH_CANDIDATES)]

    def get_all_memories(self, category: str = None) -> list:
        """Retorna todas as memórias (opcionalmente filtradas por categoria)"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            if category:
                cursor.execute(
                    'SELECT content, category FROM memories WHERE category = ?',
                    (category,),
                )
            else:
                cursor.execute('SELECT content, category FROM memories')
            memories = cursor.fetchall()
        finally:
            conn.close()

        return [{'content': m[0], 'category': m[1]} for m in memories]

# Teste rápido
if __name__ == "__main__":
    memory = KaelMemory()
    memory.add_memory("Cronograma de 3 dias para Ecos de Aethelgard", "cronograma")
    memory.add_memory("Sistema de combate baseado em turnos", "mecanica")

    results = memory.search_similar("planejamento do jogo", limit=2)
    print("\n🔍 Busca por 'planejamento do jogo':")
    for r in results:
        print(f"  [{r['similarity']:.2f}] {r['content']}")
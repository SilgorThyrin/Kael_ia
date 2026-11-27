"""Local documentation index using SQLite FTS5."""
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class DocsRagIndex:
    MAX_DOCUMENT_CHARS = 200000
    CHUNK_CHARS = 1200
    CHUNK_OVERLAP = 160

    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
                    source UNINDEXED,
                    version UNINDEXED,
                    url UNINDEXED,
                    license UNINDEXED,
                    section UNINDEXED,
                    content
                )
                """
            )

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _validate_metadata(value, label, max_length):
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > max_length:
            raise ValueError(f"Informe {label} com até {max_length} caracteres.")
        return value.strip()

    def index_documents(self, source, version, url, license_name, documents):
        source = self._validate_metadata(source, "a fonte", 120)
        version = self._validate_metadata(version, "a versão", 80)
        url = self._validate_metadata(url, "a URL de origem", 500)
        license_name = self._validate_metadata(license_name, "a licença", 120)
        if not isinstance(documents, list) or not documents:
            raise ValueError("Selecione ao menos um documento textual para indexar.")

        rows = []
        for document in documents:
            filename = document["filename"]
            text = document["content"].replace("\r\n", "\n").replace("\r", "\n").strip()
            if not text:
                continue
            if len(text) > self.MAX_DOCUMENT_CHARS:
                raise ValueError(f"O documento {filename} excede o limite de texto.")
            for index, chunk in enumerate(self._chunks(text), start=1):
                rows.append((
                    source,
                    version,
                    url,
                    license_name,
                    f"{filename} · trecho {index}",
                    chunk,
                ))
        if not rows:
            raise ValueError("Os documentos selecionados estão vazios.")

        with self._connect() as conn:
            conn.execute("DELETE FROM docs_fts WHERE source = ?", (source,))
            conn.executemany(
                """
                INSERT INTO docs_fts (source, version, url, license, section, content)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def search(self, query, limit=3):
        tokens = re.findall(r"[\w]+", query, flags=re.UNICODE)[:12]
        if not tokens:
            return []
        match_query = " OR ".join(f'"{token}"' for token in tokens)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT source, version, url, license, section,
                       snippet(docs_fts, 5, '[', ']', ' … ', 18) AS excerpt
                FROM docs_fts
                WHERE docs_fts MATCH ?
                ORDER BY bm25(docs_fts)
                LIMIT ?
                """,
                (match_query, max(1, min(int(limit), 10))),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_sources(self):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT source, version, url, license, COUNT(*) AS chunks
                FROM docs_fts
                GROUP BY source, version, url, license
                ORDER BY source COLLATE NOCASE
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_source(self, source):
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM docs_fts WHERE source = ?", (source,))
            return cursor.rowcount

    @classmethod
    def _chunks(cls, text):
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + cls.CHUNK_CHARS, len(text))
            if end < len(text):
                boundary = text.rfind("\n", start + cls.CHUNK_CHARS // 2, end)
                if boundary > start:
                    end = boundary
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end == len(text):
                break
            start = max(start + 1, end - cls.CHUNK_OVERLAP)
        return chunks

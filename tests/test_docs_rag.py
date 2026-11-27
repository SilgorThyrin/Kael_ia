import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.docs_rag import DocsRagIndex


class DocsRagTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.index = DocsRagIndex(Path(self.temp.name) / "docs.sqlite")

    def tearDown(self):
        self.temp.cleanup()

    def test_indexes_cited_chunks_and_returns_relevant_results(self):
        count = self.index.index_documents(
            "Godot Docs",
            "4.4",
            "https://docs.godotengine.org/",
            "CC-BY-3.0",
            [{
                "filename": "scripting/signals.md",
                "content": "Signals allow nodes to react to events without tight coupling.",
            }],
        )

        results = self.index.search("nodes react to events")

        self.assertEqual(count, 1)
        self.assertEqual(results[0]["source"], "Godot Docs")
        self.assertEqual(results[0]["version"], "4.4")
        self.assertIn("signals.md", results[0]["section"])
        self.assertEqual(results[0]["license"], "CC-BY-3.0")

    def test_reindex_replaces_previous_source_without_duplicates(self):
        metadata = ("Godot Docs", "4.4", "https://docs.godotengine.org/", "CC-BY-3.0")
        self.index.index_documents(*metadata, [{
            "filename": "old.md", "content": "old_unique_token"
        }])
        self.index.index_documents(*metadata, [{
            "filename": "new.md", "content": "new_unique_token"
        }])

        self.assertEqual(self.index.search("old_unique_token"), [])
        self.assertEqual(len(self.index.search("new_unique_token")), 1)
        self.assertEqual(len(self.index.list_sources()), 1)

    def test_empty_queries_and_unknown_sources_are_safe(self):
        self.assertEqual(self.index.search("!!!"), [])
        self.assertEqual(self.index.delete_source("missing"), 0)

    def test_rejects_empty_citations_and_oversized_document(self):
        with self.assertRaisesRegex(ValueError, "a licença"):
            self.index.index_documents("Source", "1", "https://example.test", "", [
                {"filename": "a.md", "content": "text"}
            ])
        with self.assertRaisesRegex(ValueError, "excede o limite"):
            self.index.index_documents("Source", "1", "https://example.test", "MIT", [
                {"filename": "large.md", "content": "x" * (DocsRagIndex.MAX_DOCUMENT_CHARS + 1)}
            ])


if __name__ == "__main__":
    unittest.main()

import sys
import tempfile
import unittest
import math
import struct
import types
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.memory import KaelMemory


class KaelMemoryTests(unittest.TestCase):
    def test_embedding_model_is_lazy_and_cpu_only(self):
        fake_sentence_transformers = types.ModuleType("sentence_transformers")
        model = types.SimpleNamespace(
            encode=lambda _text: types.SimpleNamespace(
                tobytes=lambda: struct.pack("<2f", 1.0, 0.0)
            )
        )
        factory = Mock(return_value=model)
        fake_sentence_transformers.SentenceTransformer = factory

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(
                "sys.modules",
                {"sentence_transformers": fake_sentence_transformers},
            ):
                memory = KaelMemory(db_path=str(Path(temp_dir) / "memory.db"))
                factory.assert_not_called()
                memory._get_embedding("first use")

                factory.assert_called_once_with(
                    "all-MiniLM-L6-v2",
                    device="cpu",
                )

    def test_search_only_scores_the_most_recent_candidate_window(self):
        fake_numpy = types.ModuleType("numpy")
        fake_numpy.float32 = "float32"
        fake_numpy.frombuffer = lambda value, dtype=None: struct.unpack("<2f", value)
        fake_numpy.dot = lambda left, right: sum(a * b for a, b in zip(left, right))
        fake_numpy.linalg = types.SimpleNamespace(
            norm=lambda value: math.sqrt(sum(item * item for item in value))
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            memory = KaelMemory(db_path=str(Path(temp_dir) / "memory.db"))
            memory.MAX_SEARCH_CANDIDATES = 2
            memory._get_embedding = lambda _text: struct.pack("<2f", 1.0, 0.0)
            for content in ("old", "middle", "new"):
                memory.add_memory(content, "project")

            with patch.dict("sys.modules", {"numpy": fake_numpy}):
                results = memory.search_similar("query", limit=2)

        self.assertEqual([item["content"] for item in results], ["new", "middle"])


if __name__ == "__main__":
    unittest.main()

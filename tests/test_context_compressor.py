import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.context_compressor import ContextCompressor


class ContextCompressorTests(unittest.TestCase):
    def test_build_context_stays_within_limit_and_preserves_current_message(self):
        compressor = ContextCompressor(max_chars=120)

        result = compressor.build_context(
            user_message="current request",
            history=[{"role": "user", "content": "old " * 100}],
            memories=[{"category": "project", "content": "memory " * 100}],
            system_prompt="system",
        )

        self.assertLessEqual(len(result), 120)
        self.assertIn("=== SISTEMA ===\nsystem", result)
        self.assertIn("Usuário: current request", result)

    def test_oversized_mandatory_context_fails_explicitly(self):
        compressor = ContextCompressor(max_chars=20)

        with self.assertRaisesRegex(ValueError, "excedem o limite"):
            compressor.build_context("request", [], [], system_prompt="system")

    def test_compress_never_adds_truncation_marker_past_limit(self):
        compressor = ContextCompressor(max_chars=8)

        self.assertEqual(len(compressor.compress("long content")), 8)


if __name__ == "__main__":
    unittest.main()

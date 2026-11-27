import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.attachments import format_attachments, history_prompt, validate_attachments


class AttachmentTests(unittest.TestCase):
    def test_valid_relative_text_file_is_normalized(self):
        attachments = validate_attachments([{
            "filename": r"Scripts\player.py",
            "content": "print('hello')",
        }])

        self.assertEqual(attachments[0]["filename"], "Scripts/player.py")

    def test_rejects_traversal_and_absolute_paths(self):
        for filename in ("../secret.txt", "C:\\private.txt", "/private.txt"):
            with self.subTest(filename=filename):
                with self.assertRaises(ValueError):
                    validate_attachments([{"filename": filename, "content": "data"}])

    def test_rejects_binary_extensions_and_oversized_content(self):
        with self.assertRaisesRegex(ValueError, "não textual"):
            validate_attachments([{"filename": "payload.exe", "content": "x"}])
        with self.assertRaisesRegex(ValueError, "excede 1 MB"):
            validate_attachments([{"filename": "large.txt", "content": "x" * (1024 * 1024 + 1)}])

    def test_history_keeps_names_without_persisting_file_contents(self):
        attachments = [{"filename": "Docs/GDD.md", "content": "private text"}]

        history = history_prompt("Analise", attachments)
        prompt = format_attachments("Analise", attachments)

        self.assertIn("Docs/GDD.md", history)
        self.assertNotIn("private text", history)
        self.assertIn("private text", prompt)
        self.assertIn("dados não confiáveis", prompt)


if __name__ == "__main__":
    unittest.main()

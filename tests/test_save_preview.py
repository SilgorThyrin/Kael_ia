import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.kael_context import KaelContext


class SavePreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        self.context = KaelContext.__new__(KaelContext)
        self.context.memory_dir = self.root
        self.context.permission_policy = SimpleNamespace(
            allows_project_write=lambda path: False
        )
        self.context.memory = None

    def tearDown(self):
        self.temp.cleanup()

    def test_preview_shows_new_file_without_writing_it(self):
        response = "<kael_save filename='Scripts/Main.gd'>print('hello')</kael_save>"

        preview = self.context.preview_save_commands(response, self.root)

        self.assertIn("Criar: Scripts/Main.gd", preview)
        self.assertIn("--- /dev/null", preview)
        self.assertIn("+print('hello')", preview)
        self.assertFalse((self.root / "Scripts" / "Main.gd").exists())

    def test_preview_shows_old_and_proposed_contents_for_overwrite(self):
        target = self.root / "main.gd"
        target.write_text("old value\n", encoding="utf-8")

        preview = self.context.preview_save_commands(
            "<kael_save filename='main.gd'>new value</kael_save>",
            self.root,
        )

        self.assertIn("Alterar: main.gd", preview)
        self.assertIn("-old value", preview)
        self.assertIn("+new value", preview)
        self.assertEqual(target.read_text(encoding="utf-8"), "old value\n")

    def test_preview_rejects_traversal_and_does_not_write(self):
        with self.assertRaisesRegex(ValueError, "inseguro"):
            self.context.preview_save_commands(
                "<kael_save filename='../outside.txt'>no</kael_save>",
                self.root,
            )
        for unsafe in ("main.gd:stream", "CON.txt", "bad?.gd"):
            with self.subTest(filename=unsafe):
                with self.assertRaisesRegex(ValueError, "inseguro"):
                    self.context.preview_save_commands(
                        f"<kael_save filename='{unsafe}'>no</kael_save>",
                        self.root,
                    )
        self.assertFalse((Path(self.temp.name) / "outside.txt").exists())

    def test_preview_changes_when_target_changes_while_waiting(self):
        target = self.root / "main.gd"
        target.write_text("original", encoding="utf-8")
        response = "<kael_save filename='main.gd'>proposed</kael_save>"
        original_preview = self.context.preview_save_commands(response, self.root)

        target.write_text("external change", encoding="utf-8")
        updated_preview = self.context.preview_save_commands(response, self.root)

        self.assertNotEqual(original_preview, updated_preview)

    def test_authorized_overwrite_creates_backup(self):
        target = self.root / "main.gd"
        target.write_text("old value", encoding="utf-8")
        response = "<kael_save filename='main.gd'>new value</kael_save>"

        self.context.process_save_commands(
            response,
            self.root,
            validation_passed=True,
            approval_granted=True,
        )

        backups = list(self.root.glob("main.gd.bak.*"))
        self.assertEqual(target.read_text(encoding="utf-8"), "new value")
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), "old value")


if __name__ == "__main__":
    unittest.main()

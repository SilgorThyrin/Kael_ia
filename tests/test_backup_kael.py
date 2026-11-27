import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.backup_kael import create_backup


class BackupKaelTests(unittest.TestCase):
    def test_backup_contains_source_but_excludes_local_state_and_models(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "kael"
            root.mkdir()
            (root / "core").mkdir()
            (root / "config").mkdir()
            (root / "Modelos_Ollama").mkdir()
            (root / "api").mkdir()
            (root / "core" / "module.py").write_text("print('safe')", encoding="utf-8")
            (root / "api" / "server.py").write_text("pass", encoding="utf-8")
            (root / "game_critic.py").write_text("pass", encoding="utf-8")
            (root / ".gitignore").write_text("*.db", encoding="utf-8")
            (root / "requirements.txt").write_text("flask", encoding="utf-8")
            (root / "config" / "config.template.json").write_text("{}", encoding="utf-8")
            (root / "config" / "config.json").write_text('{"token":"private"}', encoding="utf-8")
            (root / "ultimas_mensagens.json").write_text("[]", encoding="utf-8")
            (root / "kael_memory.db").write_bytes(b"database")
            (root / "Modelos_Ollama" / "model.gguf").write_bytes(b"model")
            (root / ".env").write_text("SECRET=value", encoding="utf-8")

            archive_path, count = create_backup(root)
            with zipfile.ZipFile(archive_path) as archive:
                names = set(archive.namelist())

        self.assertEqual(archive_path.parent, root.parent / "backups")
        self.assertEqual(count, len(names))
        self.assertIn("core/module.py", names)
        self.assertIn("api/server.py", names)
        self.assertIn("game_critic.py", names)
        self.assertIn(".gitignore", names)
        self.assertIn("requirements.txt", names)
        self.assertIn("config/config.template.json", names)
        self.assertFalse(any("config.json" in name for name in names))
        self.assertFalse(any(name.endswith(".db") or name.endswith(".gguf") for name in names))
        self.assertFalse(any(name.endswith(".env") or "historico" in name for name in names))

    def test_backup_rejects_output_directory_inside_source_tree(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "kael"
            root.mkdir()
            (root / "core").mkdir()
            (root / "core" / "module.py").write_text("pass", encoding="utf-8")
            with self.assertRaises(ValueError):
                create_backup(root, root / "core")


if __name__ == "__main__":
    unittest.main()

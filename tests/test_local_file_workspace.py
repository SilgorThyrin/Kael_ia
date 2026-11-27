import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.local_file_workspace import LocalFileWorkspace
from core.permission_policy import PermissionPolicy


class LocalFileWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.folder = self.root / "workspace"
        self.folder.mkdir()
        self.policy = PermissionPolicy(self.root, self.root / "config" / "autonomy.json")
        self.policy.add_trusted_folder(str(self.folder))
        self.workspace = LocalFileWorkspace(self.policy)

    def tearDown(self):
        self.temp.cleanup()

    def test_lists_and_reads_text_only_in_the_authorized_folder(self):
        source = self.folder / "main.py"
        source.write_text("print('hello')", encoding="utf-8")

        listing = self.workspace.list_directory(str(self.folder))
        read = self.workspace.read_file(str(source))

        self.assertEqual(listing["entries"][0]["name"], "main.py")
        self.assertEqual(read["content"], "print('hello')")
        self.assertEqual(read["path"], str(source.resolve()))

    def test_rejects_untrusted_paths_and_sensitive_content(self):
        outside = self.root / "outside.py"
        outside.write_text("print('outside')", encoding="utf-8")
        secret = self.folder / "settings.py"
        secret.write_text('api_key = "abcdefgh123456"', encoding="utf-8")

        with self.assertRaises(PermissionError):
            self.workspace.read_file(str(outside))
        with self.assertRaises(ValueError):
            self.workspace.read_file(str(secret))

    def test_rejects_symlinked_files(self):
        source = self.folder / "source.py"
        source.write_text("print('hello')", encoding="utf-8")
        alias = self.folder / "alias.py"
        try:
            alias.symlink_to(source)
        except (OSError, NotImplementedError):
            self.skipTest("A criação de symlinks não está disponível neste ambiente.")

        with self.assertRaises(PermissionError):
            self.workspace.read_file(str(alias))


if __name__ == "__main__":
    unittest.main()

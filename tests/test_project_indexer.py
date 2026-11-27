import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.project_indexer import ProjectIndexer


class ProjectIndexerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "projects"
        self.project = self.root / "Game"
        self.project.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def test_scans_only_allowed_text_and_excludes_builds_and_sensitive_files(self):
        (self.project / "Scripts").mkdir()
        (self.project / "Scripts" / "Main.gd").write_text(
            "extends Node\n# contact: player@example.com\n", encoding="utf-8"
        )
        (self.project / "Credentials.json").write_text(
            '{"api_key": "do-not-index-this-value"}', encoding="utf-8"
        )
        (self.project / "settings.cfg").write_text(
            'access_token = "sample-token-value"\n', encoding="utf-8"
        )
        (self.project / "build").mkdir()
        (self.project / "build" / "Generated.gd").write_text(
            "generated", encoding="utf-8"
        )
        (self.project / "SecretConfig").mkdir()
        (self.project / "SecretConfig" / "Config.gd").write_text(
            "extends Node", encoding="utf-8"
        )
        (self.project / "image.png").write_bytes(b"\x00binary")

        result = ProjectIndexer(self.project, self.root).scan()

        self.assertEqual([doc["filename"] for doc in result["documents"]], ["Scripts/Main.gd"])
        self.assertNotIn("player@example.com", result["documents"][0]["content"])
        self.assertIn("[email redacted]", result["documents"][0]["content"])
        self.assertEqual(result["skipped"]["emails_redacted"], 1)
        self.assertEqual(result["skipped"]["sensitive"], 1)
        self.assertGreaterEqual(result["skipped"]["excluded"], 2)

    def test_rejects_project_outside_authorized_root(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()

        with self.assertRaisesRegex(ValueError, "autorizada"):
            ProjectIndexer(outside, self.root)

    def test_file_count_limit_is_reported_as_partial(self):
        for index in range(ProjectIndexer.MAX_FILES + 1):
            (self.project / f"script_{index:03}.gd").write_text(
                f"# {index}\n", encoding="utf-8"
            )

        result = ProjectIndexer(self.project, self.root).scan()

        self.assertEqual(result["files_indexed"], ProjectIndexer.MAX_FILES)
        self.assertTrue(result["limit_reached"])


if __name__ == "__main__":
    unittest.main()

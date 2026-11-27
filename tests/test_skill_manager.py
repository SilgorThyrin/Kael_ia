import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.skill_manager import SkillManager


class SkillManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "skills"
        folder = self.root / "it-support"
        folder.mkdir(parents=True)
        (folder / "manifest.json").write_text(json.dumps({
            "id": "it-support",
            "name": "IT Support",
            "description": "Windows and network troubleshooting.",
            "version": "1",
            "keywords": ["windows", "wifi"],
            "capabilities": ["read", "project_write"],
        }), encoding="utf-8")
        (folder / "SKILL.md").write_text("Ask before changing settings.", encoding="utf-8")
        self.settings = Path(self.temp.name) / "config" / "skills.local.json"
        self.manager = SkillManager(self.root, self.settings)

    def tearDown(self):
        self.temp.cleanup()

    def test_skill_is_loaded_only_after_local_enable_and_keyword_match(self):
        self.assertEqual(self.manager.context_for("Windows WiFi issue"), "")

        self.manager.set_enabled("it-support", True)

        self.assertIn("Ask before changing settings", self.manager.context_for("Windows WiFi issue"))
        self.assertEqual(self.manager.context_for("What is the weather?"), "")
        self.assertEqual(SkillManager(self.root, self.settings).list_skills()[0]["enabled"], True)

    def test_skill_manifest_does_not_grant_capabilities(self):
        self.manager.set_enabled("it-support", True)

        context = self.manager.context_for("Windows troubleshooting")

        self.assertIn("não concede permissões", context)
        self.assertEqual(self.manager.list_skills()[0]["capabilities"], ["read", "project_write"])

    def test_unknown_skill_and_non_boolean_state_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "desconhecida"):
            self.manager.set_enabled("../other", True)
        with self.assertRaisesRegex(ValueError, "booleano"):
            self.manager.set_enabled("it-support", "yes")

    def test_invalid_manifest_is_skipped_without_hiding_valid_skills(self):
        broken = self.root / "broken"
        broken.mkdir()
        (broken / "manifest.json").write_text("{invalid", encoding="utf-8")

        manager = SkillManager(self.root, self.settings)

        self.assertEqual([item["id"] for item in manager.list_skills()], ["it-support"])


if __name__ == "__main__":
    unittest.main()

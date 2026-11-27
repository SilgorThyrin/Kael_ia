import tempfile
import unittest
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.change_validation import ChangeValidation
from core.kael_context import KaelContext
from core.permission_policy import PermissionPolicy
from core.tool_registry import ToolRegistry
from tools.game_bridge import GameBridge


class ChangeValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        (self.root / "tests").mkdir()
        (self.root / "tests" / "test_game.py").write_text(
            "import unittest\nfrom game import VALUE\n"
            "class GameTests(unittest.TestCase):\n"
            "    def test_candidate_value(self):\n"
            "        self.assertEqual(VALUE, 2)\n",
            encoding="utf-8",
        )
        (self.root / "game.py").write_text("VALUE = 1\n", encoding="utf-8")
        self.validator = ChangeValidation()

    def tearDown(self):
        self.temp.cleanup()

    def test_candidate_runs_in_temporary_copy_without_modifying_original(self):
        plan = self.validator.test_plan(self.root, ["game.py"])

        result = self.validator.run(
            self.root,
            [("game.py", "VALUE = 2\n")],
            plan,
        )

        self.assertEqual(result["status"], "success")
        self.assertIn("1 teste(s) executado(s)", result["summary"])
        self.assertEqual((self.root / "game.py").read_text(encoding="utf-8"), "VALUE = 1\n")

    def test_missing_compatible_suite_is_not_treated_as_a_pass(self):
        (self.root / "tests" / "test_game.py").unlink()

        self.assertIsNone(self.validator.test_plan(self.root, ["game.py"]))

    def test_web_assets_require_and_use_node_test_suite(self):
        test_file = self.root / "tests" / "game.test.js"
        test_file.write_text("const test = require('node:test');\n", encoding="utf-8")
        filenames = ["index.html", "css/game.css", "assets/terrain.svg", "js/terrain.js"]

        with patch("core.change_validation.shutil.which", return_value="C:\\node.exe"):
            plan = self.validator.test_plan(self.root, filenames)

        self.assertEqual(plan["kind"], "node_test")
        self.assertEqual(plan["test_files"], ["tests/game.test.js"])

        test_file.unlink()
        with patch("core.change_validation.shutil.which", return_value="C:\\node.exe"):
            self.assertIsNone(self.validator.test_plan(self.root, filenames))

    def test_candidate_web_test_is_used_before_it_exists_on_disk(self):
        changes = [
            ("js/terrain.js", "export function height() { return 1; }"),
            ("tests/terrain.test.js", "import 'node:test';"),
        ]

        with patch("core.change_validation.shutil.which", return_value="C:\\node.exe"):
            plan = self.validator.test_plan(
                self.root,
                [filename for filename, _ in changes],
                proposed_files=changes,
            )

        self.assertEqual(plan["kind"], "node_test")
        self.assertEqual(plan["test_files"], ["tests/terrain.test.js"])

    def test_candidate_web_tests_run_against_the_temporary_overlay(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is unavailable.")
        changes = [
            ("js/terrain.js", "module.exports = { height: (seed) => seed % 10 };\n"),
            (
                "tests/terrain.test.js",
                "const test = require('node:test');\n"
                "const assert = require('node:assert/strict');\n"
                "const terrain = require('../js/terrain');\n"
                "test('seed produces a bounded height', () => {\n"
                "  assert.ok(terrain.height(17) >= 0 && terrain.height(17) < 10);\n"
                "});\n",
            ),
        ]
        with patch("core.change_validation.shutil.which", return_value=node):
            plan = self.validator.test_plan(
                self.root,
                [filename for filename, _ in changes],
                proposed_files=changes,
            )
        result = self.validator.run(self.root, changes, plan)

        self.assertEqual(result["status"], "success", result["output"])
        self.assertIn("1 teste(s) executado(s)", result["summary"])

    def test_godot_scene_resources_use_headless_editor_validation(self):
        project_file = self.root / "project.godot"
        executable = self.root.parent / "godot.exe"
        project_file.write_text("config_version=5\n", encoding="utf-8")
        executable.write_bytes(b"")
        validator = ChangeValidation(godot_executable=str(executable))

        plan = validator.test_plan(
            self.root,
            ["Scenes/Terrain.tscn", "Scripts/Terrain.gd"],
        )

        self.assertEqual(plan["kind"], "godot_headless")

    def test_project_templates_are_proposed_without_writing_code(self):
        project = self.root / "new-game"
        result = GameBridge(str(project)).create_project_structure(
            "new-game",
            "aventura",
            "godot",
        )

        self.assertIn("Scripts/main.gd", result["templates"])
        self.assertFalse((project / "Scripts" / "main.gd").exists())
        self.assertTrue(result["template_files"])

    def test_unsupported_luau_save_is_blocked_without_writing(self):
        context = self.make_context()
        response = context.process_save_commands(
            "<kael_save filename='Scripts/Main.lua'>print('not tested')</kael_save>",
            save_dir=self.root,
        )

        self.assertIn("[ALTERAÇÃO BLOQUEADA:", response)
        self.assertIn("runner de testes Roblox/Luau", response)
        self.assertEqual(response.count("[ALTERAÇÃO BLOQUEADA:"), 1)
        self.assertFalse((self.root / "Scripts" / "Main.lua").exists())

    def test_test_failure_does_not_create_apply_approval_or_modify_source(self):
        context = self.make_context()
        response = "<kael_save filename='game.py'>VALUE = 3</kael_save>"
        request = context.request_tested_save_commands(response, save_dir=self.root)
        test_result = context.registry.resolve_approval(request["permission"]["id"], True)

        self.assertEqual(test_result["status"], "error")
        self.assertIn("TESTES FALHARAM", test_result["response"])
        self.assertNotIn("next_permission", test_result)
        self.assertEqual((self.root / "game.py").read_text(encoding="utf-8"), "VALUE = 1\n")

    def test_passing_tests_require_a_second_approval_before_applying(self):
        context = self.make_context()
        response = "<kael_save filename='game.py'>VALUE = 2</kael_save>"
        request = context.request_tested_save_commands(response, save_dir=self.root)

        self.assertEqual(request["status"], "permission_required")
        self.assertEqual((self.root / "game.py").read_text(encoding="utf-8"), "VALUE = 1\n")
        test_result = context.registry.resolve_approval(request["permission"]["id"], True)

        self.assertEqual(test_result["status"], "success")
        self.assertIn("next_permission", test_result)
        self.assertEqual((self.root / "game.py").read_text(encoding="utf-8"), "VALUE = 1\n")

        apply_result = context.registry.resolve_approval(
            test_result["next_permission"]["id"],
            True,
        )

        self.assertEqual(apply_result["status"], "success")
        self.assertEqual((self.root / "game.py").read_text(encoding="utf-8"), "VALUE = 2")

    def make_context(self):
        context = KaelContext.__new__(KaelContext)
        context.config = {}
        context.memory_dir = self.root
        context.projects_root = self.root.parent
        context.project_path = self.root
        context.memory = None
        context.permission_policy = PermissionPolicy(
            self.root.parent,
            self.root.parent / "config" / "autonomy.json",
        )
        context.registry = ToolRegistry(context)
        return context


if __name__ == "__main__":
    unittest.main()

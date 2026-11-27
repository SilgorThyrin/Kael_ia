import subprocess
import tempfile
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.godot_runner import GodotRunner


class GodotRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "projects"
        self.project = self.root / "Game"
        self.project.mkdir(parents=True)
        (self.project / "project.godot").write_text("[application]\n", encoding="utf-8")
        self.executable = Path(self.temp.name) / "godot.exe"
        self.executable.write_text("test stub", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_runs_only_bounded_headless_editor_validation(self):
        calls = []

        def fake_run(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0, "validated", "")

        runner = GodotRunner(self.root, self.executable, process_runner=fake_run)
        result = runner.validate(self.project)

        self.assertEqual(result["status"], "success")
        command, options = calls[0]
        self.assertIn("--headless", command)
        self.assertIn("--editor", command)
        self.assertIn("--quit", command)
        self.assertEqual(options["shell"], False)
        self.assertEqual(options["timeout"], 120)

    def test_rejects_projects_outside_the_authorized_root(self):
        calls = []
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (outside / "project.godot").write_text("[application]\n", encoding="utf-8")
        runner = GodotRunner(self.root, self.executable, process_runner=lambda *a, **k: calls.append(a))

        result = runner.validate(outside)

        self.assertEqual(result["status"], "error")
        self.assertEqual(calls, [])

    def test_timeout_is_reported_as_validation_failure(self):
        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

        runner = GodotRunner(self.root, self.executable, process_runner=timeout)

        result = runner.validate(self.project)

        self.assertEqual(result["status"], "error")
        self.assertIn("120 segundos", result["error"])


if __name__ == "__main__":
    unittest.main()

import json
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.autonomous_engine import AutonomousEngine
from tools.cmd_autonomous import listar_tarefas, retomar_tarefa


class AutonomousEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.memory_dir = Path(self.temp.name) / "memory"
        self.memory_dir.mkdir()
        self.ctx = SimpleNamespace(
            memory_dir=self.memory_dir,
            project_path=Path(self.temp.name) / "projects" / "Game",
            memory=None,
        )
        self.engine = AutonomousEngine(self.ctx)

    def tearDown(self):
        self.temp.cleanup()

    def add_task(self, status, plan, subtask_statuses):
        conn = sqlite3.connect(self.engine.db_path)
        cursor = conn.execute(
            """
            INSERT INTO tasks (
                description, status, plan_json, deadline_at, project_path
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                "Build a game", status,
                json.dumps(plan) if plan is not None else None,
                time.time() + 60,
                str(self.ctx.project_path.resolve()),
            ),
        )
        task_id = cursor.lastrowid
        conn.executemany(
            """
            INSERT INTO subtasks (task_id, description, status, position)
            VALUES (?, ?, ?, ?)
            """,
            [
                (task_id, description, subtask_state, position)
                for position, (description, subtask_state) in enumerate(subtask_statuses)
            ],
        )
        conn.commit()
        conn.close()
        return task_id

    def test_plan_limits_reject_invalid_or_oversized_steps(self):
        with self.assertRaises(ValueError):
            self.engine._validate_plan(["step"] * (self.engine.MAX_SUBTASKS + 1))
        with self.assertRaises(ValueError):
            self.engine._validate_plan(["x" * (self.engine.MAX_SUBTASK_CHARS + 1)])
        with self.assertRaises(ValueError):
            self.engine._validate_plan(["same", "same"])

    def test_autonomous_download_still_requires_approval_in_project_autonomous_mode(self):
        project_path = self.ctx.project_path
        project_path.mkdir(parents=True)
        approvals = []
        self.ctx.permission_policy = SimpleNamespace(
            allows_project_write=lambda path: True,
            is_within_projects_root=lambda path: True,
        )

        class ImmediateApprovalRegistry:
            def create_approval(self, **request):
                approvals.append(request)
                request["callback"]()
                return {"id": "download-approval"}

        self.ctx.registry = ImmediateApprovalRegistry()
        self.engine.running = True
        self.engine.current_task = 1
        downloaded_path = project_path / "Assets" / "asset.bin"

        with patch(
            "tools.file_download.download_file",
            return_value={
                "path": str(downloaded_path),
                "bytes": 12,
                "source": "https://assets.example/asset.bin",
            },
        ) as download_mock:
            result = self.engine._execute_subtask_with_approval(
                1,
                "/baixar_arquivo https://assets.example/asset.bin Assets/asset.bin",
            )

        self.assertEqual(len(approvals), 1)
        self.assertEqual(approvals[0]["title"], "Permissão para download externo")
        self.assertIn("não será executado nem extraído", approvals[0]["details"])
        self.assertIn("Download concluído", result)
        download_mock.assert_called_once()

    def test_restart_marks_running_step_for_review_instead_of_repeating_it(self):
        task_id = self.add_task(
            "running",
            ["Create a scene"],
            [("Create a scene", "running")],
        )

        restarted = AutonomousEngine(self.ctx)
        status = restarted.get_status()

        self.assertEqual(status["task_id"], task_id)
        self.assertEqual(status["status"], "interrupted")
        self.assertEqual(status["subtasks"][0]["status"], "needs_review")

    def test_legacy_task_database_is_migrated_and_interrupted_safely(self):
        legacy_dir = Path(self.temp.name) / "legacy"
        legacy_dir.mkdir()
        legacy_db = legacy_dir / "autonomous_tasks.db"
        conn = sqlite3.connect(legacy_db)
        conn.execute(
            """
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                result TEXT,
                error TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE subtasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                description TEXT,
                status TEXT DEFAULT 'pending',
                result TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
            """
        )
        conn.execute(
            "INSERT INTO tasks (description, status) VALUES ('Old task', 'running')"
        )
        conn.execute(
            "INSERT INTO subtasks (task_id, description, status) VALUES (1, 'Old step', 'running')"
        )
        conn.commit()
        conn.close()
        legacy_ctx = SimpleNamespace(
            memory_dir=legacy_dir,
            project_path=self.ctx.project_path,
        )

        migrated = AutonomousEngine(legacy_ctx)
        status = migrated.get_status()

        self.assertEqual(status["status"], "interrupted")
        self.assertEqual(status["subtasks"][0]["status"], "needs_review")
        self.assertIsNone(status["project_path"])

    def test_resume_requires_explicit_confirmation_to_retry_uncertain_step(self):
        task_id = self.add_task(
            "interrupted",
            ["Create a scene"],
            [("Create a scene", "needs_review")],
        )

        result = self.engine.resume_task(task_id)

        self.assertIn("repetição", result["error"])
        self.assertFalse(self.engine.running)

    def test_resume_rejects_a_different_project(self):
        task_id = self.add_task(
            "paused",
            ["Create a scene"],
            [("Create a scene", "pending")],
        )
        self.ctx.project_path = Path(self.temp.name) / "projects" / "OtherGame"

        result = self.engine.resume_task(task_id)

        self.assertIn("não corresponde", result["error"])
        self.assertFalse(self.engine.running)

    def test_run_loop_skips_completed_checkpoint_and_executes_pending_step(self):
        plan = ["Create a scene", "Add player controls"]
        task_id = self.add_task(
            "running",
            plan,
            [("Create a scene", "completed"), ("Add player controls", "pending")],
        )
        executed = []
        self.engine.running = True
        self.engine.current_task = task_id
        self.engine._execute_subtask_with_approval = (
            lambda current_id, description: executed.append(description) or "ok"
        )
        self.engine._summarize_task = lambda current_id: "2/2 steps done"

        with patch("core.autonomous_engine.time.sleep", return_value=None):
            self.engine._run_loop(task_id, "Build a game")

        self.assertEqual(executed, ["Add player controls"])
        self.assertEqual(self.engine.get_status()["status"], "completed")

    def test_resume_retries_uncertain_step_only_after_explicit_choice(self):
        task_id = self.add_task(
            "paused",
            ["Create a scene"],
            [("Create a scene", "needs_review")],
        )
        finished = threading.Event()

        def fake_run(task, description):
            self.engine.running = False
            finished.set()

        self.engine._run_loop = fake_run
        result = self.engine.resume_task(task_id, retry_uncertain=True)
        self.assertTrue(finished.wait(2))

        conn = sqlite3.connect(self.engine.db_path)
        status = conn.execute(
            "SELECT status, resume_count FROM tasks WHERE id=?", (task_id,)
        ).fetchone()
        subtask_status = conn.execute(
            "SELECT status FROM subtasks WHERE task_id=?", (task_id,)
        ).fetchone()[0]
        conn.close()
        self.assertEqual(result["task_id"], task_id)
        self.assertEqual(status, ("running", 1))
        self.assertEqual(subtask_status, "pending")

    def test_interrupted_planning_can_resume_without_repeating_actions(self):
        task_id = self.add_task("interrupted", None, [])
        finished = threading.Event()

        def fake_run(task, description):
            self.engine.running = False
            finished.set()

        self.engine._run_loop = fake_run
        result = self.engine.resume_task(task_id)

        self.assertTrue(finished.wait(2))
        self.assertEqual(result["task_id"], task_id)

    def test_resume_command_forwards_explicit_uncertain_retry(self):
        calls = []
        ctx = SimpleNamespace(autonomous_engine=SimpleNamespace(
            resume_task=lambda task_id, retry_uncertain=False: (
                calls.append((task_id, retry_uncertain))
                or {"task_id": 12, "message": "Tarefa #12 retomada."}
            )
        ))

        result = retomar_tarefa(
            ctx, ["12", "--repetir-incerta"], {}
        )

        self.assertEqual(calls, [("12", True)])
        self.assertEqual(result["status"], "success")

    def test_task_list_command_shows_saved_task_state(self):
        ctx = SimpleNamespace(autonomous_engine=SimpleNamespace(
            list_tasks=lambda: [{
                "id": 12, "status": "interrupted", "description": "Build a game"
            }]
        ))

        result = listar_tarefas(ctx, [], {})

        self.assertIn("#12 · interrupted", result["response"])


if __name__ == "__main__":
    unittest.main()

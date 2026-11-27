import threading
import time
import unittest
from collections import deque
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.autonomous_agent import AutonomousAgent
from core.autonomous_engine import AutonomousEngine
from core.tool_registry import ToolRegistry


class PermissionFlowTests(unittest.TestCase):
    def setUp(self):
        self.ctx = SimpleNamespace()
        self.registry = ToolRegistry(self.ctx)
        self.ctx.registry = self.registry

    def test_mutating_command_requires_single_use_approval(self):
        executed = []
        self.registry.commands["/construir_jogo"]["handler"] = (
            lambda *args: executed.append(True) or {
                "status": "success",
                "response": "Projeto criado.",
            }
        )

        pending = self.registry.dispatch("/construir_jogo rpg Teste")
        self.assertEqual(pending["status"], "permission_required")
        self.assertEqual(executed, [])

        result = self.registry.resolve_approval(pending["permission"]["id"], True)
        self.assertEqual(result["response"], "Projeto criado.")
        self.assertEqual(executed, [True])
        self.assertEqual(
            self.registry.resolve_approval(pending["permission"]["id"], True)["status"],
            "expired",
        )

    def test_denial_does_not_run_mutating_command(self):
        executed = []
        self.registry.commands["/limpar_flutuantes"]["handler"] = (
            lambda *args: executed.append(True)
        )

        pending = self.registry.dispatch("/limpar_flutuantes")
        result = self.registry.resolve_approval(pending["permission"]["id"], False)

        self.assertEqual(result["status"], "denied")
        self.assertEqual(executed, [])

    def test_expired_request_cannot_be_approved(self):
        executed = []
        permission = self.registry.create_approval(
            "Test",
            "Testar expiracao",
            "Nenhum detalhe",
            lambda: executed.append(True),
        )
        self.registry.pending_approvals[permission["id"]]["expires_at"] = time.time() - 1

        result = self.registry.resolve_approval(permission["id"], True)

        self.assertEqual(result["status"], "expired")
        self.assertEqual(executed, [])

    def test_file_approval_writes_only_the_explicitly_selected_files(self):
        selected = []
        permission = self.registry.create_approval(
            "Revisar arquivos",
            "Escolha arquivos",
            "Diff",
            callback=lambda: self.fail("Selection callback should be used"),
            files=["Scripts/A.gd", "Scripts/B.gd"],
            selection_callback=lambda files: selected.extend(files) or {
                "status": "success",
                "response": "Seleção aplicada.",
            },
        )

        result = self.registry.resolve_approval(
            permission["id"], True, ["Scripts/B.gd"]
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(selected, ["Scripts/B.gd"])

    def test_file_approval_rejects_unlisted_paths_without_consuming_request(self):
        selected = []
        permission = self.registry.create_approval(
            "Revisar arquivos",
            "Escolha arquivos",
            "Diff",
            callback=lambda: None,
            files=["Scripts/A.gd"],
            selection_callback=lambda files: selected.extend(files),
        )

        invalid = self.registry.resolve_approval(
            permission["id"], True, ["../outside.txt"]
        )
        valid = self.registry.resolve_approval(
            permission["id"], True, ["Scripts/A.gd"]
        )

        self.assertEqual(invalid["status"], "error")
        self.assertEqual(valid["status"], "success")
        self.assertEqual(selected, ["Scripts/A.gd"])

    def test_denied_autonomous_agent_step_stops_agent(self):
        agent = AutonomousAgent(self.ctx)
        agent.active = True
        agent.task_queue = deque([{"tipo": "gerar_gdd"}])
        agent._execute_task = lambda task: self.fail("Denied task must not execute")

        pending = agent.get_next_task()
        self.assertTrue(pending["aguardando_permissao"])
        self.registry.resolve_approval(pending["permission"]["id"], False)

        self.assertFalse(agent.active)
        self.assertFalse(agent.pending_task_permission)

    def test_approved_autonomous_agent_step_runs_once(self):
        agent = AutonomousAgent(self.ctx)
        agent.active = True
        agent.task_queue = deque([{"tipo": "gerar_gdd"}])
        executed = []
        agent._execute_task = lambda task: executed.append(task) or {"sucesso": True}

        pending = agent.get_next_task()
        result = self.registry.resolve_approval(pending["permission"]["id"], True)

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(executed), 1)
        self.assertIsNone(agent.pending_task_permission)

    def test_denied_autonomous_engine_subtask_unblocks_without_execution(self):
        self.ctx.project_path = SimpleNamespace(name="Teste")
        engine = AutonomousEngine.__new__(AutonomousEngine)
        engine.ctx = self.ctx
        engine.running = True
        result = []
        worker = threading.Thread(
            target=lambda: result.append(
                engine._execute_subtask_with_approval(1, "Criar um script")
            )
        )
        worker.start()

        pending = []
        for _ in range(100):
            pending = self.registry.list_pending_approvals()
            if pending:
                break
            time.sleep(0.01)
        self.assertTrue(pending, "Autonomous subtask did not request approval")

        self.registry.resolve_approval(pending[0]["id"], False)
        worker.join(timeout=2)

        self.assertFalse(worker.is_alive())
        self.assertFalse(engine.running)
        self.assertIn("negada", result[0].lower())

    def test_stopping_engine_cancels_pending_approval(self):
        engine = AutonomousEngine.__new__(AutonomousEngine)
        engine.ctx = self.ctx
        engine.running = True
        engine.current_task = None
        engine._task_lock = threading.Lock()
        rejected = []
        permission = self.registry.create_approval(
            "Test",
            "Cancelar tarefa",
            "Criar arquivo",
            lambda: self.fail("Stopped task must not execute"),
            on_reject=lambda: rejected.append(True),
        )
        engine.pending_approval_id = permission["id"]

        engine.stop_task()

        self.assertFalse(engine.running)
        self.assertEqual(rejected, [True])
        self.assertEqual(
            self.registry.resolve_approval(permission["id"], True)["status"],
            "expired",
        )


if __name__ == "__main__":
    unittest.main()

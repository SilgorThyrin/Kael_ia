import tempfile
import threading
import time
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.kael_context import KaelContext
from core.autonomous_agent import AutonomousAgent
from core.permission_policy import PermissionPolicy
from core.tool_registry import ToolRegistry


class PermissionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "projects"
        self.root.mkdir()
        self.settings = Path(self.temp.name) / "config" / "autonomy.json"
        self.policy = PermissionPolicy(self.root, self.settings)

    def tearDown(self):
        self.temp.cleanup()

    def test_project_autonomy_is_scoped_and_persisted(self):
        project = self.root / "Game"
        project.mkdir()
        outside = Path(self.temp.name) / "outside"
        self.policy.set_mode(PermissionPolicy.PROJECT_AUTONOMOUS)

        self.assertTrue(self.policy.allows_project_write(project))
        self.assertFalse(self.policy.allows_project_write(self.root))
        self.assertFalse(self.policy.allows_project_write(outside))
        self.assertEqual(
            PermissionPolicy(self.root, self.settings).mode,
            PermissionPolicy.PROJECT_AUTONOMOUS,
        )

    def test_external_capabilities_always_require_approval(self):
        self.policy.set_mode(PermissionPolicy.PROJECT_AUTONOMOUS)

        for capability in ("network", "studio", "system", "overwrite"):
            with self.subTest(capability=capability):
                self.assertTrue(
                    self.policy.requires_approval(capability, self.root / "Game")
                )

    def test_trusted_folder_writes_are_limited_to_the_exact_authorized_folder(self):
        trusted = Path(self.temp.name) / "trusted"
        nested = trusted / "nested"
        nested.mkdir(parents=True)
        self.policy.add_trusted_folder(str(trusted))
        self.policy.set_mode(PermissionPolicy.TRUSTED_FOLDERS)

        self.assertTrue(self.policy.allows_trusted_folder_write(trusted / "new.py"))
        self.assertFalse(self.policy.allows_trusted_folder_write(nested / "new.py"))
        self.assertFalse(self.policy.requires_approval("file_write", trusted / "new.py"))
        self.assertTrue(self.policy.requires_approval("file_write", nested / "new.py"))
        self.assertTrue(
            PermissionPolicy(self.root, self.settings).is_trusted_directory(trusted)
        )

    def test_strict_mode_requires_approval_to_read_and_external_actions_stay_gated(self):
        self.policy.set_mode(PermissionPolicy.STRICT)

        self.assertTrue(self.policy.requires_approval("file_read", self.root / "script.py"))
        self.assertTrue(self.policy.requires_approval("network", self.root / "Game"))

    def test_project_creation_is_automatic_only_for_a_new_project(self):
        self.policy.set_mode(PermissionPolicy.PROJECT_AUTONOMOUS)
        new_project = self.root / "NewGame"
        existing_project = self.root / "ExistingGame"
        existing_project.mkdir()

        self.assertFalse(self.policy.requires_approval("project_create", new_project))
        self.assertTrue(self.policy.requires_approval("project_create", existing_project))

    def test_project_write_command_is_automatic_but_network_still_prompts(self):
        project = self.root / "Game"
        project.mkdir()
        ctx = SimpleNamespace(
            projects_root=self.root,
            project_path=project,
            permission_policy=self.policy,
        )
        self.policy.set_mode(PermissionPolicy.PROJECT_AUTONOMOUS)
        registry = ToolRegistry(ctx)
        registry.commands["/integrar_jogo"]["handler"] = lambda *args: {
            "status": "success",
            "response": "Alteração local concluída.",
        }
        registry.commands["/pesquisar_jogos"]["handler"] = lambda *args: {
            "status": "success",
            "response": "Pesquisa concluída.",
        }

        local_result = registry.dispatch("/integrar_jogo")
        network_result = registry.dispatch("/pesquisar_jogos aventura")

        self.assertEqual(local_result["status"], "success")
        self.assertEqual(network_result["status"], "permission_required")

    def test_project_creation_with_references_still_requires_network_approval(self):
        ctx = SimpleNamespace(
            projects_root=self.root,
            project_path=self.root / "Existing",
            permission_policy=self.policy,
        )
        self.policy.set_mode(PermissionPolicy.PROJECT_AUTONOMOUS)
        registry = ToolRegistry(ctx)
        registry.commands["/construir_jogo"]["handler"] = lambda *args: {
            "status": "success",
            "response": "Projeto criado.",
        }

        result = registry.dispatch("/construir_jogo aventura Novo --ref Exemplo")

        self.assertEqual(result["status"], "permission_required")

    def test_autonomous_game_creation_requires_approval_for_existing_target(self):
        project = self.root / "ExistingGame"
        project.mkdir()
        ctx = SimpleNamespace(
            projects_root=self.root,
            project_path=self.root / "Current",
            permission_policy=self.policy,
        )
        self.policy.set_mode(PermissionPolicy.PROJECT_AUTONOMOUS)
        registry = ToolRegistry(ctx)
        registry.commands["/criar_automaticamente"]["handler"] = lambda *args: {
            "status": "success",
            "response": "Criação iniciada.",
        }

        result = registry.dispatch("/criar_automaticamente rpg ExistingGame")

        self.assertEqual(result["status"], "permission_required")

    def test_new_project_file_is_created_without_extra_approval(self):
        project = self.root / "Game"
        project.mkdir()
        ctx = self.make_context(project)

        result = ctx.process_save_commands(
            "<kael_save filename='Scripts/Notes.txt'>return true</kael_save>",
            project,
        )

        self.assertIn("✅ **Sistema:** Arquivos salvos", result)
        self.assertEqual((project / "Scripts" / "Notes.txt").read_text(encoding="utf-8"), "return true")
        self.assertEqual(ctx.registry.list_pending_approvals(), [])

    def test_trusted_folder_mode_writes_and_backs_up_only_inside_the_authorized_root(self):
        project = Path(self.temp.name) / "trusted"
        project.mkdir()
        target = project / "script.py"
        target.write_text("old", encoding="utf-8")
        self.policy.add_trusted_folder(str(project))
        self.policy.set_mode(PermissionPolicy.TRUSTED_FOLDERS)
        ctx = self.make_context(project)
        ctx.permission_policy = self.policy
        self.policy.set_mode(PermissionPolicy.TRUSTED_FOLDERS)

        result = ctx.process_save_commands(
            "<kael_save filename='script.py'>new</kael_save>",
            project,
            require_trusted_folder=True,
            validation_passed=True,
            approval_granted=True,
        )

        self.assertIn("✅ **Sistema:** Arquivos salvos", result)
        self.assertEqual(target.read_text(encoding="utf-8"), "new")
        backups = list(project.glob("script.py.bak.*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), "old")

    def test_auto_write_is_blocked_if_folder_authorization_was_revoked(self):
        project = Path(self.temp.name) / "trusted"
        project.mkdir()
        self.policy.add_trusted_folder(str(project))
        self.policy.set_mode(PermissionPolicy.TRUSTED_FOLDERS)
        ctx = self.make_context(project)
        ctx.permission_policy = self.policy
        self.policy.set_mode(PermissionPolicy.TRUSTED_FOLDERS)
        self.policy.remove_trusted_folder(str(project))

        result = ctx.process_save_commands(
            "<kael_save filename='script.py'>new</kael_save>",
            project,
            require_trusted_folder=True,
            validation_passed=True,
            approval_granted=True,
        )

        self.assertIn("[ARQUIVO BLOQUEADO", result)
        self.assertFalse((project / "script.py").exists())

    def test_agent_creation_uses_sanitized_project_directory(self):
        ctx = SimpleNamespace(
            projects_root=self.root,
            project_path=self.root / "Existing",
            permission_policy=self.policy,
        )
        agent = AutonomousAgent(ctx)

        agent.set_project("rpg", "../Meu Jogo", "godot", [])

        self.assertEqual(ctx.project_path, self.root / "Meu_Jogo")
        self.assertEqual(agent.project_config["nome"], "Meu_Jogo")

    def test_godot_creation_queues_headless_check_for_approval(self):
        project = self.root / "GodotGame"
        project.mkdir()
        ctx = SimpleNamespace(
            projects_root=self.root,
            project_path=self.root / "Current",
            permission_policy=self.policy,
        )
        self.policy.set_mode(PermissionPolicy.PROJECT_AUTONOMOUS)
        registry = ToolRegistry(ctx)
        ctx.registry = registry
        agent = AutonomousAgent(ctx)
        agent.set_project("rpg", "GodotGame", "godot", [])
        agent.task_queue.clear()
        agent.task_queue.append({"tipo": "validar_godot"})
        agent.active = True
        agent._execute_task = lambda task: self.fail("Godot code must not run before approval")

        pending = agent.get_next_task()

        self.assertTrue(pending["aguardando_permissao"])
        self.assertEqual(pending["permission"]["summary"], "O agente quer executar: validar_godot")
        registry.resolve_approval(pending["permission"]["id"], False)

    def make_context(self, project):
        self.policy.set_mode(PermissionPolicy.PROJECT_AUTONOMOUS)
        ctx = KaelContext.__new__(KaelContext)
        ctx.projects_root = self.root
        ctx.project_path = project
        ctx.memory_dir = Path(self.temp.name) / "memory"
        ctx.memory = None
        ctx.permission_policy = self.policy
        ctx.registry = ToolRegistry(ctx)
        return ctx

    def wait_for_permission(self, registry):
        for _ in range(200):
            pending = registry.list_pending_approvals()
            if pending:
                return pending[0]
            time.sleep(0.01)
        self.fail("A solicitação de sobrescrita não apareceu.")

    def test_autonomous_overwrite_waits_for_approval_and_creates_backup(self):
        project = self.root / "Game"
        project.mkdir()
        target = project / "Scripts" / "Game.txt"
        target.parent.mkdir()
        target.write_text("old", encoding="utf-8")
        ctx = self.make_context(project)
        response = "<kael_save filename='Scripts/Game.txt'>new</kael_save>"
        result = []
        worker = threading.Thread(
            target=lambda: result.append(ctx.process_save_commands(response, project))
        )
        worker.start()

        permission = self.wait_for_permission(ctx.registry)
        self.assertEqual(target.read_text(encoding="utf-8"), "old")
        ctx.registry.resolve_approval(permission["id"], True)
        worker.join(timeout=2)

        self.assertFalse(worker.is_alive())
        self.assertEqual(target.read_text(encoding="utf-8"), "new")
        backups = list(target.parent.glob("Game.txt.bak.*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), "old")

    def test_denied_overwrite_preserves_original_file(self):
        project = self.root / "Game"
        project.mkdir()
        target = project / "save.txt"
        target.write_text("old", encoding="utf-8")
        ctx = self.make_context(project)
        response = "<kael_save filename='save.txt'>new</kael_save>"
        result = []
        worker = threading.Thread(
            target=lambda: result.append(ctx.process_save_commands(response, project))
        )
        worker.start()

        permission = self.wait_for_permission(ctx.registry)
        ctx.registry.resolve_approval(permission["id"], False)
        worker.join(timeout=2)

        self.assertFalse(worker.is_alive())
        self.assertEqual(target.read_text(encoding="utf-8"), "old")
        self.assertIn("[ARQUIVO NAO ALTERADO:", result[0])


if __name__ == "__main__":
    unittest.main()

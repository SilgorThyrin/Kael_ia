import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.tool_registry import ToolRegistry


class FakeGameBridge:
    def __init__(self, path, engine="roblox"):
        self.path = path
        self.engine = engine

    def detect_engine(self):
        return self.engine

    def full_report(self):
        return {
            "motor": self.engine,
            "scripts": [{"arquivo": "Scripts/main.lua", "linhas": 12}],
            "problemas": [],
            "documentos": ["Docs/GDD.md"],
            "cenas": [],
        }

    def read_docs(self, max_chars):
        return "Objetivo: explorar um mundo procedural."


class FakePluginBridge:
    def __init__(self):
        self.last_state_time = time.time()
        self.last_state = {
            "instancias": [],
            "terreno": {
                "range": 64,
                "sample_step": 8,
                "heightmap": [[False]],
                "min_height": None,
                "max_height": None,
                "empty_columns": 1,
            },
        }
        self.tasks = []
        self.task_records = {}

    def studio_conectado(self):
        return True

    def enqueue(self, task):
        self.tasks.append(task)
        task_id = "a" * 32
        self.task_records[task_id] = {
            "task_id": task_id,
            "tipo": task["tipo"],
            "status": "queued",
            "completion": None,
        }
        return {"task_id": task_id, "status": "queued"}

    def get_task(self, task_id):
        return self.task_records.get(task_id)


class GameCreationToolsTests(unittest.TestCase):
    def setUp(self):
        self.project_path = Path(__file__).resolve().parent
        self.plugin_bridge = FakePluginBridge()
        self.prompts = []
        self.save_inputs = []
        self.ctx = SimpleNamespace(
            project_path=self.project_path,
            game_bridge=FakeGameBridge,
            plugin_bridge=self.plugin_bridge,
            generate=self._generate,
            process_save_commands=self._process_save_commands,
            permission_policy=None,
        )
        self.registry = ToolRegistry(self.ctx)

    def _generate(self, prompt):
        self.prompts.append(prompt)
        return {"response": "Avaliacao baseada nas evidencias.", "thinking": ""}

    def _process_save_commands(self, response, save_dir):
        self.save_inputs.append((response, save_dir))
        return "[AGUARDANDO TESTE E APROVAÇÃO: proposta pendente]"

    def _web_generate(self, prompt):
        self.prompts.append(prompt)
        return {
            "response": (
                "<kael_save filename='js/kael_terrain.js'>export function terrain() { return []; }</kael_save>"
                "<kael_save filename='tests/kael_terrain.test.js'>import 'node:test';</kael_save>"
            ),
            "thinking": "",
        }

    def test_terrain_generation_requires_approval_before_queueing(self):
        response = self.registry.dispatch(
            "/criar_terreno colinas --tamanho 384 --seed 17"
        )

        self.assertEqual(response["status"], "permission_required")
        self.assertEqual(self.plugin_bridge.tasks, [])
        approved = self.registry.resolve_approval(response["permission"]["id"], True)

        self.assertEqual(approved["status"], "success")
        self.assertEqual(self.plugin_bridge.tasks, [{
            "tipo": "gerar_terreno",
            "preset": "colinas",
            "size": 384,
            "seed": 17,
        }])

    def test_invalid_numeric_flags_fail_without_requesting_permission(self):
        response = self.registry.dispatch("/criar_terreno colinas --size nope")

        self.assertEqual(response["status"], "error")
        self.assertIn("Valor inválido", response["response"])
        self.assertEqual(self.plugin_bridge.tasks, [])
        self.assertEqual(self.registry.list_pending_approvals(), [])

    def test_out_of_range_asset_count_is_rejected_before_permission(self):
        response = self.registry.dispatch(
            "/criar_assets arvore --quantidade 21"
        )

        self.assertEqual(response["status"], "error")
        self.assertIn("entre 1 e 20", response["response"])
        self.assertEqual(self.registry.list_pending_approvals(), [])

    def test_creation_result_can_be_queried_by_task_id(self):
        task_id = "a" * 32
        self.plugin_bridge.task_records[task_id] = {
            "task_id": task_id,
            "tipo": "gerar_terreno",
            "status": "completed",
            "completion": {
                "tipo": "gerar_terreno",
                "sucesso": True,
                "resultado": {
                    "preset": "ilha",
                    "size": 256,
                    "columns": 256,
                    "seed": 19,
                    "backup_id": "KaelTerrainBackup_0123abcd",
                },
            },
        }

        response = self.registry.dispatch("/resultado_criacao " + task_id)

        self.assertEqual(response["status"], "success")
        self.assertIn("KaelTerrainBackup_0123abcd", response["response"])

    def test_creation_review_uses_project_and_recent_terrain_evidence_only(self):
        response = self.registry.dispatch("/avaliar_criacao")

        self.assertEqual(response["status"], "success")
        self.assertIn("Avaliacao baseada", response["response"])
        self.assertIn("Scripts/main.lua", self.prompts[0])
        self.assertIn("Amostra de terreno", self.prompts[0])
        self.assertNotIn("<kael_save", self.prompts[0])

    def test_web_terrain_change_requires_project_permission_then_validation(self):
        self.ctx.game_bridge = lambda path: FakeGameBridge(path, "web")
        self.ctx.generate = self._web_generate
        response = self.registry.dispatch("/criar_terreno ilha --seed 19")

        self.assertEqual(response["status"], "permission_required")
        self.assertIn("Alterar arquivos no projeto", response["permission"]["summary"])
        self.assertNotIn("Roblox Studio", response["permission"]["summary"])
        self.assertEqual(self.save_inputs, [])

        approved = self.registry.resolve_approval(response["permission"]["id"], True)

        self.assertEqual(approved["status"], "pending_approval")
        self.assertEqual(len(self.save_inputs), 1)
        self.assertIn("node:test", self.prompts[-1])
        self.assertIn("Seed: 19", self.prompts[-1])


if __name__ == "__main__":
    unittest.main()

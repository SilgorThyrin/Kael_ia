import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.plugin_bridge import register_routes


class PluginBridgeTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.root = Path(__file__).resolve().parent
        self.ctx = SimpleNamespace(
            project_path=self.root / "projects" / "Game",
            projects_root=self.root / "projects",
        )
        register_routes(self.app, self.ctx)
        self.client = self.app.test_client()
        self.client_id = "studio-client-01"

    def test_unknown_or_arbitrary_execution_task_is_rejected(self):
        with self.assertRaises(ValueError):
            self.ctx.plugin_bridge.enqueue({
                "tipo": "executar",
                "codigo": "game:Shutdown()",
            })

    def test_task_delivery_and_completion_are_bound_to_the_claiming_client(self):
        task = self.ctx.plugin_bridge.enqueue({"tipo": "ping"})
        response = self.client.get(
            "/proxima_tarefa?protocol_version=1&client_id=" + self.client_id
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["tarefa"]["task_id"], task["task_id"])

        completion = {
            "protocol_version": 1,
            "client_id": "another-client",
            "task_id": task["task_id"],
            "tipo": "ping",
            "sucesso": True,
            "resultado": {},
        }
        rejected = self.client.post("/tarefa_concluida", json=completion)
        self.assertEqual(rejected.status_code, 403)

        completion["client_id"] = self.client_id
        accepted = self.client.post("/tarefa_concluida", json=completion)
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json["status"], "completed")

        duplicate = self.client.post("/tarefa_concluida", json=completion)
        self.assertEqual(duplicate.status_code, 409)

    def test_poll_rejects_incompatible_protocol_and_state_payloads(self):
        incompatible = self.client.get(
            "/proxima_tarefa?protocol_version=2&client_id=" + self.client_id
        )
        self.assertEqual(incompatible.status_code, 426)

        invalid_state = self.client.post(
            "/estado_jogo",
            json={
                "protocol_version": 1,
                "client_id": self.client_id,
                "motor": "RobloxStudio",
                "total_instancias": 1,
                "instancias": [],
            },
        )
        self.assertEqual(invalid_state.status_code, 400)

        valid_state = self.client.post(
            "/estado_jogo",
            json={
                "protocol_version": 1,
                "client_id": self.client_id,
                "motor": "RobloxStudio",
                "total_instancias": 1,
                "instancias": [{
                    "nome": "Baseplate",
                    "classe": "Part",
                    "y": 0,
                    "posicao": "0, 0, 0",
                }],
                "scripts_servidor": [],
                "scripts_com_conteudo": [],
            },
        )
        self.assertEqual(valid_state.status_code, 200)
        self.assertEqual(self.ctx.plugin_bridge.last_state["total_instancias"], 1)

        scripts_state = {
            "protocol_version": 1,
            "client_id": self.client_id,
            "motor": "RobloxStudio",
            "total_instancias": 0,
            "instancias": [],
            "scripts_servidor": ["ServerScriptService.Main"],
            "scripts_com_conteudo": [{
                "nome": "ServerScriptService.Main",
                "tipo": "Script",
                "codigo": "print('ok')",
                "truncado": False,
            }],
            "pedir_analise": True,
        }
        self.assertEqual(
            self.client.post("/estado_jogo", json=scripts_state).status_code, 200
        )
        scripts_state["scripts_servidor"] = []
        scripts_state["scripts_com_conteudo"] = []
        scripts_state["pedir_analise"] = False
        self.assertEqual(
            self.client.post("/estado_jogo", json=scripts_state).status_code, 200
        )
        self.assertEqual(
            self.ctx.plugin_bridge.last_state["scripts_com_conteudo"][0]["codigo"],
            "print('ok')",
        )

    def test_task_payload_is_bounded_and_validated_before_queueing(self):
        with self.assertRaises(ValueError):
            self.ctx.plugin_bridge.enqueue({
                "tipo": "limpar_flutuantes",
                "modo": "REMOVER",
                "backup": True,
                "max_distance": 501,
            })
        with self.assertRaises(ValueError):
            self.ctx.plugin_bridge.enqueue({
                "tipo": "criar_script",
                "nome": "../Unsafe",
                "tipo_script": "Script",
                "codigo": "print('not queued')",
            })
        self.assertEqual(len(self.ctx.plugin_bridge.task_queue), 0)

    def test_script_creation_is_blocked_without_a_luau_test_runner(self):
        with self.assertRaisesRegex(ValueError, "runner de testes compatível"):
            self.ctx.plugin_bridge.enqueue({
                "tipo": "criar_script",
                "nome": "Generated",
                "tipo_script": "Script",
                "codigo": "print('not tested')",
            })

        self.assertEqual(len(self.ctx.plugin_bridge.task_queue), 0)

    def test_terrain_and_asset_tasks_accept_only_bounded_typed_payloads(self):
        terrain = self.ctx.plugin_bridge.enqueue({
            "tipo": "gerar_terreno",
            "preset": "colinas",
            "size": 384,
            "seed": 17,
        })
        asset = self.ctx.plugin_bridge.enqueue({
            "tipo": "criar_assets",
            "asset_type": "arvore",
            "quantity": 20,
            "seed": 23,
        })
        restore = self.ctx.plugin_bridge.enqueue({
            "tipo": "restaurar_terreno",
            "backup_id": "KaelTerrainBackup_0123abcd",
        })
        asset_backup = self.ctx.plugin_bridge.enqueue({"tipo": "backup_assets_kael"})
        asset_restore = self.ctx.plugin_bridge.enqueue({
            "tipo": "restaurar_assets_kael",
            "backup_id": "KaelAssetsBackup_0123abcd",
        })

        self.assertEqual(
            self.ctx.plugin_bridge.tasks[terrain["task_id"]]["envelope"]["size"],
            384,
        )
        self.assertEqual(
            self.ctx.plugin_bridge.tasks[asset["task_id"]]["envelope"]["quantity"],
            20,
        )
        self.assertEqual(
            self.ctx.plugin_bridge.tasks[restore["task_id"]]["envelope"]["backup_id"],
            "KaelTerrainBackup_0123abcd",
        )
        self.assertEqual(
            self.ctx.plugin_bridge.tasks[asset_backup["task_id"]]["envelope"]["tipo"],
            "backup_assets_kael",
        )
        self.assertEqual(
            self.ctx.plugin_bridge.tasks[asset_restore["task_id"]]["envelope"]["backup_id"],
            "KaelAssetsBackup_0123abcd",
        )

    def test_terrain_and_asset_task_invalid_values_are_rejected_before_queueing(self):
        invalid_tasks = [
            {"tipo": "gerar_terreno", "preset": "unknown", "size": 256, "seed": 1},
            {"tipo": "gerar_terreno", "preset": [], "size": 256, "seed": 1},
            {"tipo": "gerar_terreno", "preset": "colinas", "size": True, "seed": 1},
            {"tipo": "gerar_terreno", "preset": "colinas", "size": 1024, "seed": 1},
            {"tipo": "gerar_terreno", "preset": "colinas", "size": 256, "seed": -1},
            {"tipo": "criar_assets", "asset_type": "script", "quantity": 1, "seed": 1},
            {"tipo": "criar_assets", "asset_type": [], "quantity": 1, "seed": 1},
            {"tipo": "criar_assets", "asset_type": "arvore", "quantity": 21, "seed": 1},
            {"tipo": "restaurar_terreno", "backup_id": "../backup"},
            {"tipo": "restaurar_assets_kael", "backup_id": "KaelTerrainBackup_0123abcd"},
        ]
        for task in invalid_tasks:
            with self.subTest(task=task), self.assertRaises(ValueError):
                self.ctx.plugin_bridge.enqueue(task)
        self.assertEqual(len(self.ctx.plugin_bridge.task_queue), 0)

    def test_terrain_snapshot_is_bounded_and_validated(self):
        state = {
            "protocol_version": 1,
            "client_id": self.client_id,
            "motor": "RobloxStudio",
            "total_instancias": 0,
            "instancias": [],
            "scripts_servidor": [],
            "scripts_com_conteudo": [],
            "terreno": {
                "range": 64,
                "sample_step": 8,
                "heightmap": [[False, 4, 8], [False, 12, 16]],
                "has_terrain": True,
                "min_height": 4,
                "max_height": 16,
                "empty_columns": 2,
            },
        }
        accepted = self.client.post("/estado_jogo", json=state)
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(
            self.ctx.plugin_bridge.last_state["terreno"]["max_height"],
            16,
        )

        state["terreno"].update(
            has_terrain=False,
            heightmap=[[False, False], [False, False]],
            min_height=0,
            max_height=0,
            empty_columns=4,
        )
        accepted = self.client.post("/estado_jogo", json=state)
        self.assertEqual(accepted.status_code, 200)

        state["terreno"]["heightmap"] = [[float("inf")]]
        rejected = self.client.post("/estado_jogo", json=state)
        self.assertEqual(rejected.status_code, 400)

    def test_delivered_task_expires_without_being_replayed(self):
        task = self.ctx.plugin_bridge.enqueue({"tipo": "ping"})
        self.ctx.plugin_bridge.claim_next_task(self.client_id)
        record = self.ctx.plugin_bridge.tasks[task["task_id"]]
        record["delivered_at"] -= self.ctx.plugin_bridge.DELIVERY_TIMEOUT_SECONDS + 1

        self.assertIsNone(self.ctx.plugin_bridge.claim_next_task(self.client_id))
        self.assertEqual(
            self.ctx.plugin_bridge.get_task(task["task_id"])["status"],
            "failed",
        )

    def test_active_task_history_is_bounded_even_when_tasks_are_not_completed(self):
        bridge = self.ctx.plugin_bridge
        with patch("builtins.print"):
            for _ in range(bridge.MAX_ACTIVE_TASKS):
                bridge.enqueue({"tipo": "ping"})
                bridge.claim_next_task(self.client_id)

        with self.assertRaises(ValueError):
            with patch("builtins.print"):
                bridge.enqueue({"tipo": "ping"})
        self.assertEqual(len(bridge.tasks), bridge.MAX_ACTIVE_TASKS)


if __name__ == "__main__":
    unittest.main()

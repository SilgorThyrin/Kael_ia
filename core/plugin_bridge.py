"""Versioned, validated local protocol for the Roblox Studio plugin."""
import base64
import binascii
import json
import math
import re
import threading
import time
import uuid
from collections import deque
from pathlib import Path

from flask import Blueprint, jsonify, request


class PluginBridge:
    PROTOCOL_VERSION = 1
    MAX_QUEUE = 100
    MAX_ACTIVE_TASKS = 200
    MAX_TASK_HISTORY = 200
    TASK_TTL_SECONDS = 600
    DELIVERY_TIMEOUT_SECONDS = 120
    MAX_STATE_BYTES = 1_000_000
    MAX_SCRIPT_BYTES = 500_000
    MAX_SCREENSHOT_BYTES = 4 * 1024 * 1024
    CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
    TASK_SCHEMAS = {
        "ping": set(),
        "pedir_visao": set(),
        "pedir_screenshot": set(),
        "enviar_todos_scripts": {"incluir_conteudo"},
        "limpar_flutuantes": {"modo", "backup", "max_distance"},
        "limpar_construcoes_kael": set(),
        "gerar_terreno": {"preset", "size", "seed"},
        "criar_assets": {"asset_type", "quantity", "seed"},
        "restaurar_terreno": {"backup_id"},
        "backup_assets_kael": set(),
        "restaurar_assets_kael": {"backup_id"},
    }

    def __init__(self):
        self.last_state = None
        self.last_state_time = 0
        self.errors = []
        self.task_queue = deque()
        self.tasks = {}
        self.task_order = deque()
        self.last_completion = None
        self.last_test = None
        self.screenshots = []
        self.limpezas = []
        self._lock = threading.Lock()

    @classmethod
    def validate_client_id(cls, client_id):
        if not isinstance(client_id, str) or not cls.CLIENT_ID_RE.fullmatch(client_id):
            raise ValueError("client_id inválido.")
        return client_id

    @classmethod
    def _validate_task(cls, task):
        if not isinstance(task, dict):
            raise ValueError("A tarefa deve ser um objeto JSON.")
        task_type = task.get("tipo")
        if task_type == "criar_localscript":
            task = {**task, "tipo": "criar_script", "tipo_script": "LocalScript"}
            task_type = "criar_script"
        if task_type == "criar_script":
            raise ValueError(
                "A criação de scripts Luau foi bloqueada: não há runner de testes compatível."
            )
        if not isinstance(task_type, str) or task_type not in cls.TASK_SCHEMAS:
            raise ValueError("Tipo de tarefa não suportado pelo protocolo.")
        allowed = {"tipo"} | cls.TASK_SCHEMAS[task_type]
        if set(task) - allowed:
            raise ValueError("A tarefa contém campos não suportados.")

        payload = {key: value for key, value in task.items() if key != "tipo"}
        if task_type == "enviar_todos_scripts":
            if not isinstance(payload.get("incluir_conteudo"), bool):
                raise ValueError("incluir_conteudo deve ser booleano.")
        elif task_type == "limpar_flutuantes":
            mode = payload.get("modo")
            backup = payload.get("backup")
            distance = payload.get("max_distance")
            if not isinstance(mode, str) or mode not in {"ANALISAR", "REMOVER"}:
                raise ValueError("modo deve ser ANALISAR ou REMOVER.")
            if not isinstance(backup, bool):
                raise ValueError("backup deve ser booleano.")
            if (
                isinstance(distance, bool)
                or not isinstance(distance, int)
                or not 1 <= distance <= 500
            ):
                raise ValueError("max_distance deve ser um inteiro entre 1 e 500.")
        elif task_type == "gerar_terreno":
            preset = payload.get("preset")
            size = payload.get("size")
            seed = payload.get("seed")
            if not isinstance(preset, str) or preset not in {
                "planicies", "colinas", "montanhas", "ilha",
            }:
                raise ValueError("preset de terreno nao suportado.")
            if (
                isinstance(size, bool)
                or not isinstance(size, int)
                or size not in {256, 384, 512}
            ):
                raise ValueError("size deve ser 256, 384 ou 512 studs.")
            if (
                isinstance(seed, bool)
                or not isinstance(seed, int)
                or not 0 <= seed <= 2_147_483_647
            ):
                raise ValueError("seed deve ser um inteiro entre 0 e 2147483647.")
        elif task_type == "criar_assets":
            asset_type = payload.get("asset_type")
            quantity = payload.get("quantity")
            seed = payload.get("seed")
            if not isinstance(asset_type, str) or asset_type not in {
                "casa", "torre", "arvore", "rocha",
                "cristal", "acampamento", "bau", "ponte",
            }:
                raise ValueError("tipo de asset nao suportado.")
            if (
                isinstance(quantity, bool)
                or not isinstance(quantity, int)
                or not 1 <= quantity <= 20
            ):
                raise ValueError("quantity deve ser um inteiro entre 1 e 20.")
            if (
                isinstance(seed, bool)
                or not isinstance(seed, int)
                or not 0 <= seed <= 2_147_483_647
            ):
                raise ValueError("seed deve ser um inteiro entre 0 e 2147483647.")
        elif task_type == "restaurar_terreno":
            backup_id = payload.get("backup_id")
            if (
                not isinstance(backup_id, str)
                or not re.fullmatch(r"KaelTerrainBackup_[a-f0-9]{8}", backup_id)
            ):
                raise ValueError("backup_id de terreno invalido.")
        elif task_type == "restaurar_assets_kael":
            backup_id = payload.get("backup_id")
            if (
                not isinstance(backup_id, str)
                or not re.fullmatch(r"KaelAssetsBackup_[a-f0-9]{8}", backup_id)
            ):
                raise ValueError("backup_id de assets invalido.")
        return task_type, payload

    def enqueue(self, task):
        task_type, payload = self._validate_task(task)
        now = time.time()
        task_id = uuid.uuid4().hex
        envelope = {
            "protocol_version": self.PROTOCOL_VERSION,
            "task_id": task_id,
            "tipo": task_type,
            **payload,
        }
        with self._lock:
            self._expire_tasks(now)
            queued_count = sum(
                item["status"] == "queued" for item in self.tasks.values()
            )
            active_count = sum(
                item["status"] in {"queued", "delivered"}
                for item in self.tasks.values()
            )
            if queued_count >= self.MAX_QUEUE:
                raise ValueError("A fila do plugin está cheia.")
            if active_count >= self.MAX_ACTIVE_TASKS:
                raise ValueError("O limite de tarefas ativas do plugin foi atingido.")
            self.tasks[task_id] = {
                "envelope": envelope,
                "status": "queued",
                "created_at": now,
                "delivered_at": None,
                "client_id": None,
                "completion": None,
            }
            self.task_queue.append(task_id)
            self.task_order.append(task_id)
            self._trim_history()
            queue_length = queued_count + 1
        print(f"[PLUGIN] Tarefa enfileirada: {task_type} id={task_id}")
        return {
            "task_id": task_id,
            "status": "queued",
            "queue_length": queue_length,
        }

    def claim_next_task(self, client_id):
        now = time.time()
        with self._lock:
            self._expire_tasks(now)
            while self.task_queue:
                task_id = self.task_queue.popleft()
                record = self.tasks.get(task_id)
                if record is None or record["status"] != "queued":
                    continue
                record["status"] = "delivered"
                record["delivered_at"] = now
                record["client_id"] = client_id
                return dict(record["envelope"])
        return None

    def complete_task(self, data):
        self._validate_envelope(data)
        allowed_fields = {
            "protocol_version", "task_id", "client_id", "tipo",
            "sucesso", "resultado", "erro",
        }
        if set(data) - allowed_fields:
            raise ValueError("A conclusão contém campos não suportados.")
        task_id = data.get("task_id")
        if not isinstance(task_id, str) or not re.fullmatch(r"[a-f0-9]{32}", task_id):
            raise ValueError("task_id inválido.")
        task_type = data.get("tipo")
        success = data.get("sucesso")
        if not isinstance(task_type, str) or not isinstance(success, bool):
            raise ValueError("tipo e sucesso são obrigatórios.")
        if "resultado" in data:
            if not isinstance(data["resultado"], dict):
                raise ValueError("resultado deve ser um objeto JSON.")
            result_size = len(json.dumps(data["resultado"], ensure_ascii=False))
            if result_size > 16000:
                raise ValueError("O resultado da tarefa excede 16.000 caracteres.")
        error = data.get("erro")
        if error is not None and (
            not isinstance(error, str) or len(error) > 2000
        ):
            raise ValueError("erro deve ser texto com até 2.000 caracteres.")

        with self._lock:
            record = self.tasks.get(task_id)
            if record is None:
                raise LookupError("Tarefa desconhecida ou removida.")
            if record["status"] != "delivered":
                raise LookupError("A tarefa não está aguardando conclusão.")
            if record["client_id"] != data["client_id"]:
                raise PermissionError("A tarefa foi entregue a outro cliente.")
            if record["envelope"]["tipo"] != task_type:
                raise ValueError("O tipo de tarefa não corresponde ao pedido.")
            completion = {
                "protocol_version": self.PROTOCOL_VERSION,
                "task_id": task_id,
                "client_id": data["client_id"],
                "tipo": task_type,
                "sucesso": success,
                "resultado": data.get("resultado", {}),
                "erro": error or "",
                "concluido_em": time.time(),
            }
            record["status"] = "completed" if success else "failed"
            record["completion"] = completion
            self.last_completion = completion
            if task_type == "teste_script":
                self.last_test = completion
            if task_type == "limpar_flutuantes" and success:
                self.limpezas.append(completion["resultado"])
                self.limpezas = self.limpezas[-20:]
        print(f"[PLUGIN] Tarefa {task_id} {record['status']}: {task_type}")
        return {"ok": True, "task_id": task_id, "status": record["status"]}

    @classmethod
    def _validate_envelope(cls, data):
        if not isinstance(data, dict):
            raise ValueError("O corpo da solicitação deve ser um objeto JSON.")
        version = data.get("protocol_version")
        if isinstance(version, bool) or not isinstance(version, int) or version != cls.PROTOCOL_VERSION:
            raise ValueError("Versão do protocolo incompatível.")
        cls.validate_client_id(data.get("client_id"))

    def accept_state(self, data):
        self._validate_envelope(data)
        allowed_fields = {
            "protocol_version", "client_id", "motor", "total_instancias",
            "instancias", "scripts_servidor", "scripts_com_conteudo",
            "scripts_com_conteudo_limitado", "pedir_analise", "terreno",
        }
        if set(data) - allowed_fields:
            raise ValueError("O estado contém campos não suportados.")
        motor = data.get("motor")
        total = data.get("total_instancias")
        instances = data.get("instancias", [])
        server_scripts = data.get("scripts_servidor", [])
        if motor != "RobloxStudio":
            raise ValueError("motor inválido.")
        if (
            isinstance(total, bool)
            or not isinstance(total, int)
            or not 0 <= total <= 500
            or not isinstance(instances, list)
            or len(instances) > 500
            or total != len(instances)
        ):
            raise ValueError("total_instancias/instancias inválidos ou acima do limite.")
        if not isinstance(server_scripts, list) or len(server_scripts) > 500:
            raise ValueError("scripts_servidor deve conter no máximo 500 itens.")

        clean_instances = []
        for item in instances:
            if not isinstance(item, dict):
                raise ValueError("Cada instância deve ser um objeto.")
            name, class_name, y = item.get("nome"), item.get("classe"), item.get("y")
            if (
                not isinstance(name, str) or len(name) > 128
                or not isinstance(class_name, str) or len(class_name) > 64
                or isinstance(y, bool) or not isinstance(y, (int, float))
                or not math.isfinite(y)
            ):
                raise ValueError("Uma instância contém campos inválidos.")
            position = item.get("posicao", "")
            if not isinstance(position, str) or len(position) > 128:
                raise ValueError("posicao deve ser texto com até 128 caracteres.")
            clean_instances.append({
                "nome": name,
                "classe": class_name,
                "y": float(y),
                "posicao": position,
            })

        clean_server_scripts = []
        for name in server_scripts:
            if not isinstance(name, str) or not name.strip() or len(name) > 256:
                raise ValueError("Um caminho em scripts_servidor é inválido.")
            clean_server_scripts.append(name)

        scripts_with_content = data.get("scripts_com_conteudo", [])
        if not isinstance(scripts_with_content, list) or len(scripts_with_content) > 100:
            raise ValueError("scripts_com_conteudo deve conter no máximo 100 itens.")
        clean_scripts = []
        scripts_size = 0
        for script in scripts_with_content:
            if not isinstance(script, dict):
                raise ValueError("Cada script deve ser um objeto.")
            name, script_type, code = (
                script.get("nome"), script.get("tipo"), script.get("codigo")
            )
            if (
                not isinstance(name, str) or not name.strip() or len(name) > 256
                or not isinstance(script_type, str) or len(script_type) > 64
                or not isinstance(code, str)
                or not isinstance(script.get("truncado", False), bool)
            ):
                raise ValueError("Um script contém campos inválidos.")
            scripts_size += len(code.encode("utf-8"))
            if len(code) > 50000 or scripts_size > self.MAX_SCRIPT_BYTES:
                raise ValueError("O conteúdo de scripts excede o limite.")
            clean_scripts.append({
                "nome": name,
                "tipo": script_type,
                "codigo": code,
                "truncado": script.get("truncado", False),
            })
        scripts_limited = data.get("scripts_com_conteudo_limitado", False)
        if not isinstance(scripts_limited, bool):
            raise ValueError("scripts_com_conteudo_limitado deve ser booleano.")
        terrain = data.get("terreno")
        clean_terrain = None
        if terrain is not None:
            if not isinstance(terrain, dict):
                raise ValueError("terreno deve ser um objeto.")
            if "error" in terrain:
                if set(terrain) != {"error"} or not isinstance(terrain["error"], str) or len(terrain["error"]) > 160:
                    raise ValueError("O erro de leitura do terreno é inválido.")
                clean_terrain = {"error": terrain["error"]}
            else:
                if set(terrain) != {
                    "range", "sample_step", "heightmap", "has_terrain",
                    "min_height", "max_height", "empty_columns",
                }:
                    raise ValueError("A análise de terreno contém campos não suportados.")
                heightmap = terrain["heightmap"]
                if (
                    terrain["range"] != 64
                    or terrain["sample_step"] != 8
                    or not isinstance(terrain["has_terrain"], bool)
                    or not isinstance(heightmap, list)
                    or not 1 <= len(heightmap) <= 16
                    or not isinstance(heightmap[0], list)
                    or any(
                        not isinstance(row, list)
                        or not 1 <= len(row) <= 16
                        or len(row) != len(heightmap[0])
                        or any(
                            value is not False and (
                                isinstance(value, bool)
                                or not isinstance(value, (int, float))
                                or not math.isfinite(value)
                            )
                            for value in row
                        )
                        for row in heightmap
                    )
                ):
                    raise ValueError("A amostra de terreno é inválida.")
                sampled_heights = [
                    value
                    for row in heightmap
                    for value in row
                    if value is not False
                ]
                has_sampled_terrain = bool(sampled_heights)
                if terrain["has_terrain"] != has_sampled_terrain:
                    raise ValueError("O estado do terreno não corresponde ao mapa de alturas.")
                min_height = terrain["min_height"]
                max_height = terrain["max_height"]
                for height in (min_height, max_height):
                    if (
                        height is None
                        or isinstance(height, bool)
                        or not isinstance(height, (int, float))
                        or not math.isfinite(height)
                    ):
                        raise ValueError("A faixa de altura do terreno é inválida.")
                if min_height is not None and max_height is not None and min_height > max_height:
                    raise ValueError("A faixa de altura do terreno está invertida.")
                if not terrain["has_terrain"] and (min_height != 0 or max_height != 0):
                    raise ValueError("Alturas devem ser zero quando não há terreno na amostra.")
                if terrain["has_terrain"] and (
                    min_height != min(sampled_heights)
                    or max_height != max(sampled_heights)
                ):
                    raise ValueError("A faixa de altura não corresponde ao mapa amostrado.")
                empty_columns = terrain["empty_columns"]
                if (
                    isinstance(empty_columns, bool)
                    or not isinstance(empty_columns, int)
                    or empty_columns != sum(
                        value is False for row in heightmap for value in row
                    )
                ):
                    raise ValueError("empty_columns é inválido.")
                clean_terrain = {
                    "range": 64,
                    "sample_step": 8,
                    "heightmap": heightmap,
                    "has_terrain": terrain["has_terrain"],
                    "min_height": min_height,
                    "max_height": max_height,
                    "empty_columns": empty_columns,
                }
        if data.get("pedir_analise") is not True and self.last_state:
            clean_scripts = self.last_state["scripts_com_conteudo"]
            scripts_limited = self.last_state["scripts_com_conteudo_limitado"]
        if clean_terrain is None and self.last_state:
            clean_terrain = self.last_state.get("terreno")

        clean_state = {
            "protocol_version": self.PROTOCOL_VERSION,
            "client_id": data["client_id"],
            "motor": motor,
            "total_instancias": total,
            "instancias": clean_instances,
            "scripts_servidor": clean_server_scripts,
            "scripts_com_conteudo": clean_scripts,
            "scripts_com_conteudo_limitado": scripts_limited,
            "pedir_analise": data.get("pedir_analise") is True,
            "terreno": clean_terrain,
            "received_at": time.time(),
        }
        if len(json.dumps(clean_state, ensure_ascii=False).encode("utf-8")) > self.MAX_STATE_BYTES:
            raise ValueError("O estado enviado excede 1 MB.")
        self.last_state = clean_state
        self.last_state_time = clean_state["received_at"]
        return clean_state

    def report_error(self, data):
        self._validate_envelope(data)
        if set(data) - {
            "protocol_version", "client_id", "origem", "erro", "task_id",
        }:
            raise ValueError("O relatório contém campos não suportados.")
        origin = data.get("origem", "RobloxStudio")
        error = data.get("erro")
        task_id = data.get("task_id")
        if not isinstance(origin, str) or len(origin) > 100:
            raise ValueError("origem inválida.")
        if not isinstance(error, str) or not error.strip() or len(error) > 2000:
            raise ValueError("erro deve conter até 2.000 caracteres.")
        if task_id is not None and (
            not isinstance(task_id, str) or not re.fullmatch(r"[a-f0-9]{32}", task_id)
        ):
            raise ValueError("task_id inválido.")
        self.errors.append({
            "protocol_version": self.PROTOCOL_VERSION,
            "client_id": data["client_id"],
            "task_id": task_id,
            "origem": origin,
            "erro": error.strip(),
            "received_at": time.time(),
        })
        self.errors = self.errors[-20:]
        return {"ok": True}

    def get_task(self, task_id):
        with self._lock:
            self._expire_tasks(time.time())
            record = self.tasks.get(task_id)
            if record is None:
                return None
            return {
                "task_id": task_id,
                "tipo": record["envelope"]["tipo"],
                "status": record["status"],
                "created_at": record["created_at"],
                "completion": record["completion"],
            }

    def owns_delivered_task(self, task_id, client_id, task_type):
        with self._lock:
            self._expire_tasks(time.time())
            record = self.tasks.get(task_id)
            return bool(
                record
                and record["status"] == "delivered"
                and record["client_id"] == client_id
                and record["envelope"]["tipo"] == task_type
            )

    def _expire_tasks(self, now):
        for task_id, record in self.tasks.items():
            if (
                record["status"] == "queued"
                and now - record["created_at"] > self.TASK_TTL_SECONDS
            ):
                record["status"] = "expired"
            elif (
                record["status"] == "delivered"
                and now - record["delivered_at"] > self.DELIVERY_TIMEOUT_SECONDS
            ):
                record["status"] = "failed"
                record["completion"] = {
                    "status": "failed",
                    "erro": "O plugin não confirmou a tarefa no prazo.",
                }

    def _trim_history(self):
        while len(self.task_order) > self.MAX_TASK_HISTORY:
            removable_id = next(
                (
                    task_id for task_id in self.task_order
                    if self.tasks.get(task_id, {}).get("status")
                    not in {"queued", "delivered"}
                ),
                None,
            )
            if removable_id is None:
                break
            self.task_order.remove(removable_id)
            self.tasks.pop(removable_id, None)

    def studio_conectado(self):
        return (time.time() - self.last_state_time) < 20

    def queue_length(self):
        with self._lock:
            self._expire_tasks(time.time())
            return sum(record["status"] == "queued" for record in self.tasks.values())


def register_routes(app, ctx):
    bridge = PluginBridge()
    ctx.plugin_bridge = bridge
    studio_bp = Blueprint("studio", __name__)

    def json_body(max_bytes):
        body = request.get_data(cache=True)
        if len(body) > max_bytes:
            return None, (jsonify({"error": "Payload acima do limite."}), 413)
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return None, (jsonify({"error": "O corpo deve ser um objeto JSON."}), 400)
        return data, None

    def protocol_error(error):
        if isinstance(error, PermissionError):
            return jsonify({"error": str(error)}), 403
        if isinstance(error, LookupError):
            return jsonify({"error": str(error)}), 409
        return jsonify({"error": str(error)}), 400

    @studio_bp.route("/proxima_tarefa", methods=["GET"])
    def proxima_tarefa():
        version_text = request.args.get("protocol_version")
        if version_text != str(PluginBridge.PROTOCOL_VERSION):
            return jsonify({
                "status": "incompatible",
                "protocol_version": PluginBridge.PROTOCOL_VERSION,
            }), 426
        try:
            client_id = bridge.validate_client_id(request.args.get("client_id"))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        task = bridge.claim_next_task(client_id)
        if task is None:
            return jsonify({
                "protocol_version": PluginBridge.PROTOCOL_VERSION,
                "status": "empty",
            })
        return jsonify({
            "protocol_version": PluginBridge.PROTOCOL_VERSION,
            "status": "ok",
            "tarefa": task,
        })

    @studio_bp.route("/tarefa_concluida", methods=["POST"])
    def tarefa_concluida():
        data, error = json_body(20000)
        if error:
            return error
        try:
            result = bridge.complete_task(data)
        except (ValueError, PermissionError, LookupError) as exc:
            return protocol_error(exc)
        return jsonify(result)

    @studio_bp.route("/estado_jogo", methods=["POST"])
    @studio_bp.route("/visao_jogo", methods=["POST"])
    def estado_jogo():
        data, error = json_body(PluginBridge.MAX_STATE_BYTES)
        if error:
            return error
        try:
            clean_state = bridge.accept_state(data)
        except ValueError as exc:
            return protocol_error(exc)
        print(f"[PLUGIN] Mapa atualizado: {clean_state['total_instancias']} objetos")
        return jsonify({"ok": True, "protocol_version": PluginBridge.PROTOCOL_VERSION})

    @studio_bp.route("/reportar_erro", methods=["POST"])
    def reportar_erro():
        data, error = json_body(10000)
        if error:
            return error
        try:
            result = bridge.report_error(data)
        except ValueError as exc:
            return protocol_error(exc)
        print(f"[PLUGIN] Erro: {data['erro'][:120]}")
        return jsonify(result)

    @studio_bp.route("/resultado_limpeza", methods=["POST"])
    def resultado_limpeza():
        data, error = json_body(20000)
        if error:
            return error
        if data.get("tipo") != "limpar_flutuantes":
            return jsonify({"error": "Resultado de limpeza inválido."}), 400
        try:
            result = bridge.complete_task(data)
        except (ValueError, PermissionError, LookupError) as exc:
            return protocol_error(exc)
        return jsonify(result)

    @studio_bp.route("/screenshot", methods=["POST"])
    def screenshot():
        data, error = json_body(6 * 1024 * 1024)
        if error:
            return error
        try:
            bridge._validate_envelope(data)
            if set(data) - {
                "protocol_version", "client_id", "task_id", "imagem_b64",
            }:
                raise ValueError("O screenshot contém campos não suportados.")
            task_id = data.get("task_id")
            if not isinstance(task_id, str) or not bridge.owns_delivered_task(
                task_id, data["client_id"], "pedir_screenshot"
            ):
                raise LookupError("Não há solicitação de screenshot ativa para esta tarefa.")
            image_b64 = data.get("imagem_b64")
            if not isinstance(image_b64, str) or len(image_b64) > 6 * 1024 * 1024:
                raise ValueError("imagem_b64 inválida ou acima do limite.")
            image = base64.b64decode(image_b64, validate=True)
            if len(image) > PluginBridge.MAX_SCREENSHOT_BYTES or not image.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("A imagem deve ser PNG e ter até 4 MB.")
            project = Path(ctx.project_path).resolve()
            projects_root = Path(ctx.projects_root).resolve()
            if project == projects_root or projects_root not in project.parents:
                raise PermissionError("O projeto atual está fora da pasta autorizada.")
            screenshots = project / "Screenshots"
            screenshots.mkdir(parents=True, exist_ok=True)
            target = (screenshots / f"studio_{task_id}.png").resolve()
            if screenshots.resolve() not in target.parents:
                raise PermissionError("Destino de screenshot fora da pasta autorizada.")
            target.write_bytes(image)
            bridge.screenshots.append(str(target))
            bridge.screenshots = bridge.screenshots[-20:]
        except (ValueError, PermissionError, LookupError, binascii.Error) as exc:
            return protocol_error(exc)
        return jsonify({"ok": True, "path": str(target)})

    @studio_bp.route("/studio_tasks/<task_id>", methods=["GET"])
    def studio_task_status(task_id):
        if not re.fullmatch(r"[a-f0-9]{32}", task_id):
            return jsonify({"error": "task_id inválido."}), 400
        task = bridge.get_task(task_id)
        if task is None:
            return jsonify({"error": "Tarefa não encontrada."}), 404
        return jsonify(task)

    @studio_bp.route("/studio_status", methods=["GET"])
    def studio_status():
        return jsonify({
            "conectado": bridge.studio_conectado(),
            "protocol_version": PluginBridge.PROTOCOL_VERSION,
            "fila": bridge.queue_length(),
            "objetos": (bridge.last_state or {}).get("total_instancias", 0),
            "erros_recentes": bridge.errors[-5:],
            "last_completion": bridge.last_completion,
        })

    app.register_blueprint(studio_bp)
    print("[REG] Plugin Bridge v1 inicializado.")

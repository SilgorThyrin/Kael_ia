"""
============================================================
KAEL AUTONOMOUS ENGINE - Loop de trabalho independente
============================================================
Loop: Planejar → Executar → Observar → Refletir
Integra com: Game Bridge, Memória Vetorial, Floating Detector
============================================================
"""
import json
import shlex
import sqlite3
import threading
import time
from pathlib import Path


class AutonomousEngine:
    MAX_SUBTASKS = 8
    MAX_SUBTASK_CHARS = 500
    MAX_DESCRIPTION_CHARS = 2000
    MAX_TASK_SECONDS = 1800
    MAX_RESUMES = 3

    def __init__(self, ctx):
        self.ctx = ctx
        self.db_path = ctx.memory_dir / "autonomous_tasks.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.running = False
        self.current_task = None
        self.thread = None
        self.pending_approval_id = None
        self._task_lock = threading.Lock()

    def _init_db(self):
        """Create or safely migrate the local task and checkpoint tables."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                result TEXT,
                error TEXT,
                plan_json TEXT,
                deadline_at REAL,
                resume_count INTEGER NOT NULL DEFAULT 0,
                started_at REAL,
                project_path TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS subtasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                description TEXT,
                status TEXT DEFAULT 'pending',
                result TEXT,
                position INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
        ''')
        task_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
        }
        for column, definition in (
            ("plan_json", "TEXT"),
            ("deadline_at", "REAL"),
            ("resume_count", "INTEGER NOT NULL DEFAULT 0"),
            ("started_at", "REAL"),
            ("project_path", "TEXT"),
        ):
            if column not in task_columns:
                conn.execute(f"ALTER TABLE tasks ADD COLUMN {column} {definition}")
        subtask_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(subtasks)").fetchall()
        }
        if "position" not in subtask_columns:
            conn.execute(
                "ALTER TABLE subtasks ADD COLUMN position INTEGER NOT NULL DEFAULT 0"
            )
        conn.commit()
        conn.close()
        self._recover_interrupted_tasks()

    def _recover_interrupted_tasks(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute(
            """
            UPDATE subtasks SET status='needs_review'
            WHERE status='running' AND task_id IN (
                SELECT id FROM tasks WHERE status IN ('running', 'planning')
            )
            """
        )
        conn.execute(
            """
            UPDATE tasks
            SET status='interrupted',
                error='Servidor reiniciado; revise a etapa interrompida antes de retomar.',
                updated_at=CURRENT_TIMESTAMP
            WHERE status IN ('running', 'planning')
            """
        )
        conn.commit()
        conn.close()

    def start_task(self, description):
        """Inicia uma tarefa autônoma em thread separada."""
        if not isinstance(description, str) or not description.strip():
            return {"error": "Informe uma descrição de tarefa."}
        description = description.strip()
        if len(description) > self.MAX_DESCRIPTION_CHARS:
            return {
                "error": f"A descrição excede {self.MAX_DESCRIPTION_CHARS} caracteres."
            }
        project_path = Path(self.ctx.project_path).resolve()
        policy = getattr(self.ctx, "permission_policy", None)
        if policy is not None and not policy.is_within_projects_root(project_path):
            return {"error": "O projeto da tarefa está fora da pasta de projetos autorizada."}

        with self._task_lock:
            if self.running or (self.thread is not None and self.thread.is_alive()):
                return {"error": "Já existe uma tarefa rodando. Use /parar_tarefa primeiro."}

            deadline = time.time() + self.MAX_TASK_SECONDS
            conn = sqlite3.connect(self.db_path, timeout=10)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO tasks (
                    description, status, deadline_at, started_at, project_path
                ) VALUES (?, 'planning', ?, ?, ?)
                """,
                (description, deadline, time.time(), str(project_path)),
            )
            task_id = cursor.lastrowid
            conn.commit()
            conn.close()

            self.running = True
            self.current_task = task_id
            self.thread = threading.Thread(
                target=self._run_loop,
                args=(task_id, description),
                daemon=True,
            )
            self.thread.start()

            return {
                "task_id": task_id,
                "message": f"🤖 Tarefa #{task_id} iniciada: '{description[:50]}...'",
            }

    def stop_task(self):
        """Pause the task and preserve uncertain work for explicit review."""
        with self._task_lock:
            if not self.running:
                return {"message": "Nenhuma tarefa rodando."}
            task_id = self.current_task
            self.running = False
            pending_approval_id = self.pending_approval_id

        if pending_approval_id:
            registry = getattr(self.ctx, "registry", None)
            if registry:
                registry.resolve_approval(pending_approval_id, False)
        if task_id:
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.execute(
                """
                UPDATE tasks SET status='paused', updated_at=CURRENT_TIMESTAMP
                WHERE id=? AND status IN ('planning', 'running')
                """,
                (task_id,),
            )
            conn.execute(
                "UPDATE subtasks SET status='needs_review' WHERE task_id=? AND status='running'",
                (task_id,),
            )
            conn.commit()
            conn.close()
        return {"message": "⏸️ Tarefa pausada. Revise etapas incertas antes de retomá-la."}

    def get_status(self):
        """Returns the active task or, when idle, the most recent task."""
        task_id = self.current_task
        conn = sqlite3.connect(self.db_path, timeout=10)
        cursor = conn.cursor()
        if task_id is None:
            cursor.execute("SELECT id FROM tasks ORDER BY id DESC LIMIT 1")
            latest = cursor.fetchone()
            if latest:
                task_id = latest[0]
        if task_id is None:
            conn.close()
            return {"status": "idle"}
        cursor.execute(
            "SELECT description, status, result, error, plan_json, project_path FROM tasks WHERE id=?",
            (task_id,)
        )
        row = cursor.fetchone()
        cursor.execute(
            "SELECT description, status, result FROM subtasks WHERE task_id=? ORDER BY position, id",
            (task_id,)
        )
        subtasks = cursor.fetchall()
        conn.close()

        if not row:
            return {"status": "not_found"}

        return {
            "task_id": task_id,
            "description": row[0],
            "status": row[1],
            "result": row[2],
            "error": row[3],
            "plan": json.loads(row[4]) if row[4] else [],
            "project_path": row[5],
            "subtasks": [
                {"description": s[0], "status": s[1], "result": s[2]}
                for s in subtasks
            ]
        }

    def list_tasks(self, limit=10):
        limit = max(1, min(int(limit), 50))
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, description, status, created_at, updated_at, error, resume_count
            FROM tasks ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def resume_task(self, task_id, retry_uncertain=False):
        if not isinstance(retry_uncertain, bool):
            return {"error": "retry_uncertain deve ser booleano."}
        with self._task_lock:
            if self.running or (self.thread is not None and self.thread.is_alive()):
                return {"error": "Já existe uma tarefa rodando."}
            if isinstance(task_id, bool) or not isinstance(task_id, (int, str)):
                return {"error": "ID de tarefa inválido."}
            if isinstance(task_id, str) and not task_id.strip().isdigit():
                return {"error": "ID de tarefa inválido."}
            task_id = int(task_id)

            conn = sqlite3.connect(self.db_path, timeout=10)
            row = conn.execute(
                "SELECT description, status, plan_json, resume_count, project_path FROM tasks WHERE id=?",
                (task_id,),
            ).fetchone()
            if row is None:
                conn.close()
                return {"error": "Tarefa não encontrada."}
            description, status, plan_json, resume_count, task_project = row
            if status not in {"paused", "interrupted", "failed"}:
                conn.close()
                return {"error": f"Tarefa no estado '{status}' não pode ser retomada."}
            try:
                current_project = Path(self.ctx.project_path).resolve()
                saved_project = Path(task_project).resolve() if task_project else None
            except (OSError, RuntimeError, TypeError, ValueError):
                conn.close()
                return {"error": "O caminho do projeto salvo não é válido."}
            if saved_project is None or saved_project != current_project:
                conn.close()
                return {
                    "error": "O projeto atual não corresponde ao projeto salvo na tarefa."
                }
            policy = getattr(self.ctx, "permission_policy", None)
            if policy is not None and not policy.is_within_projects_root(current_project):
                conn.close()
                return {"error": "O projeto da tarefa está fora da pasta autorizada."}
            if not plan_json:
                subtask_count = conn.execute(
                    "SELECT COUNT(*) FROM subtasks WHERE task_id=?", (task_id,)
                ).fetchone()[0]
                if subtask_count:
                    conn.close()
                    return {
                        "error": "A tarefa sem plano possui etapas antigas; inicie uma nova tarefa."
                    }
            if resume_count >= self.MAX_RESUMES:
                conn.close()
                return {"error": f"Limite de {self.MAX_RESUMES} retomadas atingido."}

            uncertain = conn.execute(
                "SELECT COUNT(*) FROM subtasks WHERE task_id=? AND status='needs_review'",
                (task_id,),
            ).fetchone()[0]
            if uncertain and not retry_uncertain:
                conn.close()
                return {
                    "error": (
                        f"{uncertain} etapa(s) têm resultado incerto. Revise o projeto e "
                        "confirme a repetição com --repetir-incerta."
                    )
                }
            if uncertain:
                conn.execute(
                    """
                    UPDATE subtasks SET status='pending', result=NULL
                    WHERE task_id=? AND status='needs_review'
                    """,
                    (task_id,),
                )
            conn.execute(
                """
                UPDATE tasks
                SET status='running', error=NULL, deadline_at=?, started_at=?,
                    resume_count=resume_count + 1, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (time.time() + self.MAX_TASK_SECONDS, time.time(), task_id),
            )
            conn.commit()
            conn.close()

            self.running = True
            self.current_task = task_id
            self.thread = threading.Thread(
                target=self._run_loop,
                args=(task_id, description),
                daemon=True,
            )
            self.thread.start()
        return {"task_id": task_id, "message": f"Tarefa #{task_id} retomada."}

    def _run_loop(self, task_id, description):
        """Run persisted plan steps and checkpoint every terminal step."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            row = conn.execute(
                "SELECT plan_json, deadline_at, project_path FROM tasks WHERE id=?",
                (task_id,),
            ).fetchone()
            conn.close()
            if row is None:
                return

            plan_json, deadline_at, task_project = row
            if not task_project or Path(task_project).resolve() != Path(self.ctx.project_path).resolve():
                self._finish_task(
                    task_id,
                    status="paused",
                    error="O projeto atual não corresponde ao projeto salvo na tarefa.",
                )
                return
            if plan_json:
                plan = self._validate_plan(json.loads(plan_json))
            else:
                plan = self._plan_task(description)
                if not plan:
                    self._finish_task(
                        task_id, status="failed", error="Falha ao criar um plano válido."
                    )
                    return
                self._persist_plan(task_id, plan)

            conn = sqlite3.connect(self.db_path, timeout=10)
            subtasks = conn.execute(
                """
                SELECT id, description, status FROM subtasks
                WHERE task_id=? ORDER BY position, id
                """,
                (task_id,),
            ).fetchall()
            conn.close()

            for subtask_id, subtask, status in subtasks:
                if status == "completed":
                    continue
                if status == "needs_review":
                    self._finish_task(
                        task_id,
                        status="paused",
                        error="Revise a etapa incerta antes de retomá-la.",
                    )
                    return
                if status not in {"pending", "failed"}:
                    continue
                if not self._is_current_running(task_id):
                    break
                if deadline_at is not None and time.time() >= deadline_at:
                    self._finish_task(
                        task_id,
                        status="paused",
                        error=(
                            f"Limite de {self.MAX_TASK_SECONDS // 60} minutos atingido; "
                            "nenhuma nova etapa foi iniciada."
                        ),
                    )
                    return

                self._set_subtask_status(task_id, subtask_id, "running")
                print(f"[AUTONOMO] Executando subtarefa: {subtask}")
                result = self._execute_subtask_with_approval(task_id, subtask)
                observation = self._observe_result(result)
                print(f"[AUTONOMO] Observação: {observation}")

                if self._result_failed(result):
                    self._set_subtask_status(task_id, subtask_id, "needs_review", result)
                    self._finish_task(
                        task_id,
                        status="paused",
                        error=f"A etapa '{subtask}' falhou ou foi interrompida; revise antes de repetir.",
                    )
                    return
                if "erro" in observation.lower() or "falha" in observation.lower():
                    lesson = self._reflect_on_error(subtask, result)
                    self._record_lesson(lesson, result)
                    print(f"[AUTONOMO] Lição aprendida: {lesson}")
                self._set_subtask_status(task_id, subtask_id, "completed", result)
                if not self._is_current_running(task_id):
                    self._finish_task(
                        task_id,
                        status="paused",
                        error="Tarefa pausada pelo usuário.",
                    )
                    return
                time.sleep(2)

            if not self._is_current_running(task_id):
                self._finish_task(
                    task_id,
                    status="paused",
                    error="Execução interrompida; as etapas pendentes foram preservadas.",
                )
                return

            conn = sqlite3.connect(self.db_path, timeout=10)
            pending_count = conn.execute(
                "SELECT COUNT(*) FROM subtasks WHERE task_id=? AND status!='completed'",
                (task_id,),
            ).fetchone()[0]
            conn.close()
            if pending_count:
                self._finish_task(
                    task_id, status="paused", error="Há etapas que precisam ser revisadas."
                )
                return

            final_result = self._summarize_task(task_id)
            self._record_task_outcome(task_id, description, "completed", result=final_result)
            self._finish_task(task_id, status="completed", result=final_result)

        except Exception as e:
            print(f"[AUTONOMO] Erro no loop: {e}")
            self._set_running_steps_for_review(task_id)
            self._finish_task(task_id, status="paused", error=str(e))

    @classmethod
    def _validate_plan(cls, plan):
        if not isinstance(plan, list) or not 1 <= len(plan) <= cls.MAX_SUBTASKS:
            raise ValueError(f"O plano deve conter entre 1 e {cls.MAX_SUBTASKS} etapas.")
        cleaned = []
        for item in plan:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("Cada etapa do plano deve ser texto não vazio.")
            item = item.strip()
            if len(item) > cls.MAX_SUBTASK_CHARS:
                raise ValueError(
                    f"Cada etapa deve ter no máximo {cls.MAX_SUBTASK_CHARS} caracteres."
                )
            cleaned.append(item)
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("O plano contém etapas duplicadas.")
        return cleaned

    def _persist_plan(self, task_id, plan):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute(
            "UPDATE tasks SET plan_json=?, status='running', updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (json.dumps(plan, ensure_ascii=False), task_id),
        )
        conn.executemany(
            """
            INSERT INTO subtasks (task_id, description, status, position)
            VALUES (?, ?, 'pending', ?)
            """,
            [(task_id, description, position) for position, description in enumerate(plan)],
        )
        conn.commit()
        conn.close()

    def _set_subtask_status(self, task_id, subtask_id, status, result=None):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute(
            "UPDATE subtasks SET status=?, result=? WHERE id=? AND task_id=?",
            (status, str(result or "")[:2000], subtask_id, task_id),
        )
        conn.commit()
        conn.close()

    def _set_running_steps_for_review(self, task_id):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute(
            "UPDATE subtasks SET status='needs_review' WHERE task_id=? AND status='running'",
            (task_id,),
        )
        conn.commit()
        conn.close()

    @staticmethod
    def _result_failed(result):
        normalized = str(result or "").casefold()
        return not normalized.strip() or any(marker in normalized for marker in (
            "falha", "erro ao", "erro:", "negada", "expirou",
            "não foi executada", "nao foi executada", "bloqueada",
            "arquivo bloqueado", "arquivo nao alterado",
        ))

    def _is_current_running(self, task_id):
        return (
            self.running
            and getattr(self, "current_task", task_id) == task_id
        )

    def _execute_subtask_with_approval(self, task_id, subtask):
        """Pausa o agente até a pessoa aprovar ou negar cada subtarefa."""
        registry = getattr(self.ctx, "registry", None)
        if registry is None:
            if getattr(self, "current_task", task_id) == task_id:
                self.running = False
            return "Execução bloqueada: serviço de permissões indisponível."

        try:
            download_request = self._parse_download_subtask(subtask)
            if download_request:
                from tools.file_download import validate_download_request

                policy = getattr(self.ctx, "permission_policy", None)
                if policy is not None and not policy.is_within_projects_root(
                    self.ctx.project_path
                ):
                    return "Download bloqueado: o projeto está fora da pasta de projetos autorizada."
                validate_download_request(
                    download_request[0],
                    download_request[1],
                    self.ctx.project_path,
                    resolve_host=False,
                )
        except (OSError, ValueError) as exc:
            return f"Download bloqueado: {exc}"

        policy = getattr(self.ctx, "permission_policy", None)
        project_path = (
            Path(self.ctx.project_path).resolve()
            if download_request
            else self.ctx.project_path
        )
        if (
            not download_request
            and policy is not None
            and policy.allows_project_write(self.ctx.project_path)
        ):
            if not self._is_current_running(task_id):
                return "Tarefa interrompida; subtarefa não executada."
            try:
                return self._execute_subtask(task_id, subtask)
            except Exception as exc:
                return f"Falha na subtarefa: {exc}"

        decision = threading.Event()
        outcome = {"result": None}

        def execute():
            if not self._is_current_running(task_id):
                outcome["result"] = "Tarefa interrompida; subtarefa não executada."
                decision.set()
                return {"status": "denied", "response": outcome["result"]}
            try:
                if download_request and Path(self.ctx.project_path).resolve() != project_path:
                    outcome["result"] = (
                        "Download cancelado: o projeto ativo mudou desde a aprovação."
                    )
                    return {"status": "error", "response": outcome["result"]}
                outcome["result"] = self._execute_subtask(task_id, subtask)
                return {
                    "status": "success",
                    "response": f"Subtarefa concluída: {subtask}",
                }
            except Exception as e:
                outcome["result"] = f"Falha na subtarefa: {e}"
                return {"status": "error", "response": outcome["result"]}
            finally:
                decision.set()

        def reject():
            outcome["result"] = "Subtarefa negada; execução autônoma interrompida."
            if getattr(self, "current_task", task_id) == task_id:
                self.running = False
            decision.set()

        permission = registry.create_approval(
            title=(
                "Permissão para download externo"
                if download_request
                else "Permissão para subtarefa autônoma"
            ),
            summary=(
                f"O Kael quer baixar um arquivo para o projeto {project_path.name}."
                if download_request
                else f"O Kael quer executar esta etapa no projeto {project_path.name}."
            ),
            details=(
                f"{subtask}\n\nSomente HTTPS público; limite de 50 MiB. "
                "O arquivo não será executado nem extraído."
                if download_request
                else subtask
            ),
            callback=execute,
            on_reject=reject,
        )
        self.pending_approval_id = permission["id"]

        try:
            if not decision.wait(600):
                if getattr(self, "current_task", task_id) == task_id:
                    self.running = False
                return "Permissão expirou; nenhuma ação foi executada."
            return outcome["result"] or "Ação cancelada."
        finally:
            self.pending_approval_id = None

    def _plan_task(self, description):
        """Usa a IA para decompor a tarefa em subtarefas."""
        prompt = (
            f"Você é o Kael em MODO AUTÔNOMO. Sua tarefa: '{description}'.\n"
            f"Projeto atual: {self.ctx.project_path.name}\n\n"
            f"Decomponha em 3-5 etapas concretas (no máximo {self.MAX_SUBTASKS}), "
            f"cada uma com até {self.MAX_SUBTASK_CHARS} caracteres. "
            "Cada etapa deve ser uma ação específica; não repita etapas. "
            "Se precisar obter um arquivo, escreva uma etapa exatamente como "
            "\"/baixar_arquivo https://host-publico/arquivo.ext Assets/arquivo.ext\"; "
            "essa etapa sempre aguardará aprovação. Não use HTTP, não instale, "
            "não extraia e não execute o arquivo baixado.\n\n"
            "Responda APENAS com um JSON array de strings, sem markdown:\n"
            '[\"Subtarefa 1\", \"Subtarefa 2\", \"Subtarefa 3\"]'
        )
        resultado = self.ctx.generate(prompt)
        response = resultado['response'].strip()

        # Tenta parsear como JSON
        try:
            if response.startswith('```json'):
                response = response.replace('```json', '').replace('```', '').strip()
            plan = json.loads(response)
        except json.JSONDecodeError:
            print(f"[AUTONOMO] Falha ao parsear plano: {response[:200]}")
            return None
        try:
            return self._validate_plan(plan)
        except ValueError as exc:
            print(f"[AUTONOMO] Plano rejeitado: {exc}")
            return None

    def _execute_subtask(self, task_id, subtask):
        """Executa uma subtarefa usando as tools disponíveis."""
        # Roteia para a tool apropriada
        result = None
        download_request = self._parse_download_subtask(subtask)
        if download_request:
            from tools.file_download import download_file

            download = download_file(
                download_request[0],
                download_request[1],
                self.ctx.project_path,
            )
            relative_path = Path(download["path"]).resolve().relative_to(
                Path(self.ctx.project_path).resolve()
            )
            return (
                f"Download concluído: {relative_path.as_posix()} "
                f"({download['bytes']} bytes); arquivo não executado nem extraído."
            )
        if "criar" in subtask.lower() or "gerar" in subtask.lower():
            # Usa Game Bridge para criar estrutura
            prompt = f"{subtask}\nUse <kael_save filename='...'> para salvar o código."
            res = self.ctx.generate(prompt)
            result = self.ctx.process_save_commands(res['response'], save_dir=self.ctx.project_path)
        
        elif "testar" in subtask.lower() or "verificar" in subtask.lower():
            # Usa Floating Detector ou Game Bridge
            from tools.game_bridge import GameBridge
            bridge = GameBridge(str(self.ctx.project_path))
            report = bridge.full_report()
            result = json.dumps(report, indent=2, ensure_ascii=False)

        elif "corrigir" in subtask.lower() or "fixar" in subtask.lower():
            # Usa IA para corrigir scripts
            prompt = f"{subtask}\nAnalise os scripts e corrija problemas. Salve com <kael_save>."
            res = self.ctx.generate(prompt)
            result = self.ctx.process_save_commands(res['response'], save_dir=self.ctx.project_path)

        else:
            # Tarefa genérica: usa IA
            prompt = f"Execute esta subtarefa: {subtask}\nContexto: {self.ctx.project_path.name}"
            res = self.ctx.generate(prompt)
            result = res['response']

        return result

    @staticmethod
    def _parse_download_subtask(subtask):
        try:
            parts = shlex.split(subtask)
        except ValueError as exc:
            raise ValueError("A etapa de download tem aspas inválidas.") from exc
        if not parts or parts[0].casefold() != "/baixar_arquivo":
            return None
        if len(parts) != 3:
            raise ValueError(
                "Use /baixar_arquivo <URL_HTTPS> <destino-relativo-no-projeto>."
            )
        return parts[1], parts[2]

    def _observe_result(self, result):
        """Analisa o resultado de uma subtarefa."""
        if not result:
            return "Sem resultado."
        
        result_lower = result.lower()
        if "erro" in result_lower or "falha" in result_lower:
            return "Erro detectado no resultado."
        if "sucesso" in result_lower or "concluído" in result_lower:
            return "Subtarefa concluída com sucesso."
        return "Resultado processado."

    def _reflect_on_error(self, subtask, result):
        """Gera uma lição aprendida com o erro."""
        prompt = (
            f"Subtarefa falhou: '{subtask}'\nResultado: {result[:200]}\n\n"
            "Em 1 frase, qual lição aprender para não repetir este erro?"
        )
        res = self.ctx.generate(prompt)
        return res['response'].strip()[:200]

    def _summarize_task(self, task_id):
        """Gera resumo final da tarefa."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT description, status FROM subtasks WHERE task_id=?",
            (task_id,)
        )
        subtasks = cursor.fetchall()
        conn.close()

        completed = sum(1 for s in subtasks if s[1] == 'completed')
        total = len(subtasks)
        return f"Tarefa concluída: {completed}/{total} subtarefas executadas."


    def _record_lesson(self, lesson: str, error_context: str = ""):
        clean = " ".join((lesson or "").strip().split())
        if not clean:
            return
        last = getattr(self, "_last_lesson", "")
        if clean.lower() == last.lower():
            return
        self._last_lesson = clean
        if getattr(self.ctx, "memory", None):
            try:
                self.ctx.memory.add_memory(clean[:240], "autonomous_lesson")
            except Exception:
                pass
        try:
            import kael_engine
            if hasattr(kael_engine, "salvar_regra_aprendizado"):
                kael_engine.salvar_regra_aprendizado(clean[:200], (error_context or "")[:200])
        except Exception:
            pass

    def _record_task_outcome(self, task_id: int, description: str, status: str, result: str = "", error: str = ""):
        if status != "completed" or not getattr(self.ctx, "memory", None):
            return
        desc_short = " ".join((description or "").strip().split())[:100]
        res_short = " ".join((result or "").strip().split())[:140]
        summary = f"Tarefa #{task_id} ({desc_short}): {res_short or 'concluída'}."
        try:
            self.ctx.memory.add_memory(summary[:260], "task_outcome")
        except Exception:
            pass

    def _finish_task(self, task_id, status, result=None, error=None):
        """Finaliza a tarefa no banco."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE tasks SET status=?, result=?, error=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, result, error, task_id)
        )
        conn.commit()
        conn.close()
        if getattr(self, "current_task", task_id) == task_id:
            self.running = False
            self.current_task = None
        print(f"[AUTONOMO] Tarefa #{task_id} finalizada: {status}")
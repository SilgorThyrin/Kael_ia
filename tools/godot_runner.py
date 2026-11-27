"""Runs a bounded Godot headless editor validation for an authorized local project."""
import os
from pathlib import Path
import shutil
import subprocess


class GodotRunner:
    def __init__(self, projects_root, executable=None, timeout_seconds=120, process_runner=None):
        self.projects_root = Path(projects_root).resolve()
        configured = executable or os.environ.get("GODOT_EXECUTABLE")
        if configured:
            candidate = Path(configured).expanduser().resolve()
            self.executable = str(candidate) if candidate.is_file() else None
        else:
            self.executable = shutil.which("godot") or shutil.which("godot4")
        self.timeout_seconds = max(10, min(int(timeout_seconds), 300))
        self.process_runner = process_runner or subprocess.run

    def validate(self, project_path):
        if not self.executable:
            return {"status": "error", "error": "Godot não foi encontrado. Configure godot_executable ou o PATH."}

        try:
            project = Path(project_path).resolve()
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return {"status": "error", "error": f"Caminho do projeto inválido: {exc}"}
        if self.projects_root not in project.parents:
            return {"status": "error", "error": "O projeto está fora da pasta de projetos autorizada."}
        if not project.is_dir() or not (project / "project.godot").is_file():
            return {"status": "error", "error": f"Projeto Godot não encontrado em {project}."}

        command = [
            self.executable,
            "--headless",
            "--editor",
            "--path",
            str(project),
            "--quit",
        ]
        try:
            result = self.process_runner(
                command,
                cwd=str(project),
                shell=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "error": f"A validação Godot excedeu {self.timeout_seconds} segundos.",
                "command": command,
            }
        except OSError as exc:
            return {"status": "error", "error": f"Não foi possível iniciar Godot: {exc}"}

        stdout = (result.stdout or "")[-8000:]
        stderr = (result.stderr or "")[-8000:]
        return {
            "status": "success" if result.returncode == 0 else "error",
            "exit_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "command": command,
        }

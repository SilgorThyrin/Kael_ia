"""Runs bounded pre-apply checks against a temporary project copy."""
import ast
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from core.project_indexer import ProjectIndexer


class ChangeValidation:
    MAX_FILES = 4000
    MAX_COPY_BYTES = 100 * 1024 * 1024
    TIMEOUT_SECONDS = 90
    EXCLUDED_DIRECTORIES = {
        ".git", ".godot", ".mypy_cache", ".pytest_cache", ".venv",
        "__pycache__", "build", "dist", "node_modules", "target", "venv",
    }

    def __init__(self, godot_executable=None):
        self.godot_executable = godot_executable

    def test_plan(self, project_path, filenames, proposed_files=()):
        project = Path(project_path).resolve()
        extensions = {Path(name).suffix.casefold() for name in filenames}
        proposed_names = [
            Path(name.replace("\\", "/")).as_posix()
            for name, _ in proposed_files
        ]
        if extensions == {".py"}:
            test_dir = project / "tests"
            has_existing_tests = test_dir.is_dir() and any(
                path.is_file()
                and not path.is_symlink()
                and path.name.startswith("test_")
                and path.suffix.casefold() == ".py"
                for path in test_dir.rglob("test_*.py")
            )
            has_proposed_tests = any(
                Path(name).parts[0].casefold() == "tests"
                and Path(name).name.startswith("test_")
                and Path(name).suffix.casefold() == ".py"
                for name in proposed_names
            )
            if has_existing_tests or has_proposed_tests:
                return {
                    "kind": "python_unittest",
                    "description": "python -m unittest discover -s tests -v",
                }
        if extensions and extensions.issubset({".js", ".html", ".css", ".svg"}):
            node = shutil.which("node")
            test_files = sorted(
                {
                    path.relative_to(project).as_posix()
                    for test_dir in (project / "tests", project / "test")
                    if test_dir.is_dir()
                    for path in test_dir.rglob("*")
                    if path.is_file()
                    and not path.is_symlink()
                    and (path.name.endswith(".test.js") or path.name.endswith(".spec.js"))
                }
                | {
                    name for name in proposed_names
                    if (Path(name).name.endswith(".test.js") or Path(name).name.endswith(".spec.js"))
                    and Path(name).parts[0].casefold() in {"test", "tests"}
                }
            )
            if node and test_files:
                return {
                    "kind": "node_test",
                    "description": f"node --test ({len(test_files)} teste(s) do projeto)",
                    "executable": node,
                    "test_files": test_files,
                }
        if (
            extensions
            and extensions.issubset({".gd", ".tscn", ".tres"})
            and (project / "project.godot").is_file()
        ):
            from tools.godot_runner import GodotRunner

            runner = GodotRunner(
                project.parent,
                executable=self.godot_executable,
                timeout_seconds=self.TIMEOUT_SECONDS,
            )
            if runner.executable:
                return {
                    "kind": "godot_headless",
                    "description": "Godot --headless --editor --path <cópia temporária> --quit",
                }
        return None

    def run(self, project_path, changes, plan):
        project = Path(project_path).resolve()
        with tempfile.TemporaryDirectory(prefix="kael-preapply-") as temp_dir:
            staged_project = Path(temp_dir) / "candidate"
            try:
                self._copy_project(project, staged_project)
                self._overlay_changes(staged_project, changes)
                if plan["kind"] == "python_unittest":
                    return self._run_python_tests(staged_project)
                if plan["kind"] == "node_test":
                    return self._run_node_tests(staged_project, plan)
                if plan["kind"] == "godot_headless":
                    return self._run_godot_validation(staged_project)
                return {
                    "status": "error",
                    "summary": "O validador selecionado não está disponível.",
                }
            except (OSError, RuntimeError, ValueError) as exc:
                return {
                    "status": "error",
                    "summary": f"Não foi possível preparar a cópia temporária: {exc}",
                }

    def _copy_project(self, source_root, destination_root):
        source_root = source_root.resolve(strict=True)
        if not source_root.is_dir():
            raise ValueError("A pasta de testes não existe.")
        destination_root.mkdir(parents=True)
        copied_files = 0
        copied_bytes = 0

        for current, directories, filenames in os.walk(source_root, followlinks=False):
            current_path = Path(current)
            relative = current_path.relative_to(source_root)
            directories[:] = [
                name for name in directories
                if name.casefold() not in self.EXCLUDED_DIRECTORIES
                and not (current_path / name).is_symlink()
            ]
            target_dir = destination_root / relative
            target_dir.mkdir(parents=True, exist_ok=True)

            for name in filenames:
                source_file = current_path / name
                if (
                    source_file.is_symlink()
                    or ProjectIndexer.SENSITIVE_NAME.search(source_file.name)
                ):
                    continue
                size = source_file.stat().st_size
                copied_files += 1
                copied_bytes += size
                if copied_files > self.MAX_FILES:
                    raise ValueError(f"O projeto excede o limite de {self.MAX_FILES} arquivos.")
                if copied_bytes > self.MAX_COPY_BYTES:
                    raise ValueError(
                        f"A cópia de teste excede o limite de {self.MAX_COPY_BYTES // (1024 * 1024)} MB."
                    )
                shutil.copyfile(source_file, target_dir / name)

    @staticmethod
    def _overlay_changes(staged_project, changes):
        for filename, content in changes:
            relative = Path(filename.replace("\\", "/"))
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"Caminho de alteração inválido: {filename}")
            target = (staged_project / relative).resolve()
            if target == staged_project or staged_project not in target.parents:
                raise ValueError(f"Caminho saiu da cópia temporária: {filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            if target.suffix.casefold() == ".py":
                ast.parse(content, filename=str(target))

    def _run_python_tests(self, staged_project):
        command = [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-v",
        ]
        result = self._run_process(command, staged_project)
        output = f"{result['stdout']}\n{result['stderr']}".strip()
        match = re.search(r"Ran\s+(\d+)\s+tests?", output)
        test_count = int(match.group(1)) if match else 0
        passed = result["returncode"] == 0 and test_count > 0
        if result["returncode"] == 0 and not test_count:
            output = f"{output}\nA suíte não informou nenhum teste executado.".strip()
        return {
            "status": "success" if passed else "error",
            "summary": (
                f"Suíte Python: {test_count} teste(s) executado(s); "
                f"código de saída {result['returncode']}."
            ),
            "output": output[-12000:],
        }

    def _run_node_tests(self, staged_project, plan):
        test_paths = [
            str(staged_project / Path(filename))
            for filename in plan["test_files"]
        ]
        result = self._run_process(
            [plan["executable"], "--test", *test_paths],
            staged_project,
        )
        output = f"{result['stdout']}\n{result['stderr']}".strip()
        count_match = re.search(r"(?:ℹ|#)\s*tests\s+(\d+)", output)
        test_count = int(count_match.group(1)) if count_match else 0
        passed = result["returncode"] == 0 and test_count > 0
        if result["returncode"] == 0 and not test_count:
            output = f"{output}\nO runner não informou nenhum teste executado.".strip()
        return {
            "status": "success" if passed else "error",
            "summary": (
                f"Suíte Node: {test_count} teste(s) executado(s); "
                f"código de saída {result['returncode']}."
            ),
            "output": output[-12000:],
        }

    def _run_godot_validation(self, staged_project):
        from tools.godot_runner import GodotRunner

        runner = GodotRunner(
            staged_project.parent,
            executable=self.godot_executable,
            timeout_seconds=self.TIMEOUT_SECONDS,
        )
        result = runner.validate(staged_project)
        passed = result.get("status") == "success"
        output = "\n".join(filter(None, (result.get("stdout"), result.get("stderr"), result.get("error"))))
        return {
            "status": "success" if passed else "error",
            "summary": "Validação headless do projeto Godot concluída." if passed
                else "A validação headless do projeto Godot falhou.",
            "output": output[-12000:],
        }

    def _run_process(self, command, working_directory):
        try:
            result = subprocess.run(
                command,
                cwd=str(working_directory),
                shell=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout
            stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr
            return {
                "returncode": -1,
                "stdout": stdout or "",
                "stderr": f"{stderr or ''}\nOs testes excederam {self.TIMEOUT_SECONDS} segundos.".strip(),
            }
        except OSError as exc:
            return {"returncode": -1, "stdout": "", "stderr": f"Não foi possível executar os testes: {exc}"}
        return {
            "returncode": result.returncode,
            "stdout": result.stdout or "",
            "stderr": result.stderr or "",
        }

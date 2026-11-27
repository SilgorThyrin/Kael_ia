"""Local policy for project-scoped autonomous actions."""
import json
import os
from pathlib import Path
import secrets
import threading


class PermissionPolicy:
    STRICT = "strict"
    SUPERVISED = "supervised"
    PROJECT_AUTONOMOUS = "project_autonomous"
    TRUSTED_FOLDERS = "trusted_folders"
    MODES = {STRICT, SUPERVISED, PROJECT_AUTONOMOUS, TRUSTED_FOLDERS}

    def __init__(self, projects_root, settings_path):
        self.projects_root = Path(projects_root).resolve()
        self.settings_path = Path(settings_path)
        self.mode = self.SUPERVISED
        self.trusted_folders = set()
        self._lock = threading.RLock()
        self._load()

    def _load(self):
        if not self.settings_path.exists():
            return
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("A configuração da política deve ser um objeto JSON.")
            mode = data.get("mode")
            if not isinstance(mode, str) or mode not in self.MODES:
                raise ValueError(f"Modo de autonomia inválido: {mode!r}")
            folders = data.get("trusted_folders", [])
            if not isinstance(folders, list):
                raise ValueError("trusted_folders deve ser uma lista.")
            trusted_folders = set()
            for folder in folders:
                try:
                    resolved = self._normalize_directory(folder)
                except ValueError as exc:
                    print(f"[AVISO] Pasta autorizada ignorada: {exc}")
                    continue
                trusted_folders.add(resolved)
            self.mode = mode
            self.trusted_folders = trusted_folders
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"[AVISO] Política de autonomia inválida; usando modo supervisionado: {exc}")

    def set_mode(self, mode):
        if not isinstance(mode, str) or mode not in self.MODES:
            raise ValueError("Nível de autorização inválido.")

        with self._lock:
            previous = self.mode
            self.mode = mode
            try:
                self._persist()
            except OSError:
                self.mode = previous
                raise

    def _persist(self):
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.settings_path.with_name(
            f".{self.settings_path.name}.{secrets.token_hex(4)}.tmp"
        )
        try:
            temp_path.write_text(
                json.dumps({
                    "mode": self.mode,
                    "trusted_folders": sorted(
                        (str(path) for path in self.trusted_folders),
                        key=str.casefold,
                    ),
                }, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(str(temp_path), str(self.settings_path))
        finally:
            if temp_path.exists():
                temp_path.unlink()

    @staticmethod
    def _normalize_directory(path):
        if not isinstance(path, str) or not path.strip() or len(path) > 2048:
            raise ValueError("Informe o caminho completo de uma pasta existente.")
        try:
            resolved = Path(path).expanduser().resolve(strict=True)
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValueError(f"Não foi possível acessar a pasta: {exc}") from exc
        if not resolved.is_dir():
            raise ValueError("O caminho informado não é uma pasta.")
        if resolved == Path(resolved.anchor):
            raise ValueError("Autorize uma pasta específica, não a raiz inteira do disco.")
        return resolved

    def add_trusted_folder(self, path):
        resolved = self._normalize_directory(path)
        with self._lock:
            if resolved in self.trusted_folders:
                return str(resolved)
            self.trusted_folders.add(resolved)
            try:
                self._persist()
            except OSError:
                self.trusted_folders.remove(resolved)
                raise
        return str(resolved)

    def validate_trusted_folder(self, path):
        return str(self._normalize_directory(path))

    def remove_trusted_folder(self, path):
        try:
            resolved = Path(path).expanduser().resolve(strict=False)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("Caminho da pasta inválido.") from exc
        with self._lock:
            if resolved not in self.trusted_folders:
                return False
            self.trusted_folders.remove(resolved)
            try:
                self._persist()
            except OSError:
                self.trusted_folders.add(resolved)
                raise
        return True

    def is_trusted_directory(self, resource_path):
        try:
            candidate = Path(resource_path).resolve(strict=True)
            return candidate.is_dir() and candidate in self.trusted_folders
        except (OSError, RuntimeError, TypeError, ValueError):
            return False

    def is_trusted_file(self, resource_path):
        try:
            candidate = Path(resource_path).resolve(strict=True)
            return candidate.is_file() and candidate.parent in self.trusted_folders
        except (OSError, RuntimeError, TypeError, ValueError):
            return False

    def _is_protected_path(self, resource_path):
        try:
            candidate = Path(resource_path).resolve(strict=False)
        except (OSError, RuntimeError, TypeError, ValueError):
            return True
        protected = [
            os.environ.get("SystemRoot"),
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("ProgramData"),
        ]
        for value in protected:
            if not value:
                continue
            try:
                root = Path(value).resolve(strict=False)
            except (OSError, RuntimeError, ValueError):
                continue
            if candidate == root or root in candidate.parents:
                return True
        return False

    def allows_trusted_folder_write(self, resource_path):
        if self.mode != self.TRUSTED_FOLDERS or self._is_protected_path(resource_path):
            return False
        try:
            candidate = Path(resource_path).resolve(strict=False)
            directory = candidate if candidate.is_dir() else candidate.parent
            return directory in self.trusted_folders and directory.is_dir()
        except (OSError, RuntimeError, TypeError, ValueError):
            return False

    def is_within_projects_root(self, resource_path):
        if resource_path is None:
            return False
        try:
            candidate = Path(resource_path).resolve()
            return candidate != self.projects_root and self.projects_root in candidate.parents
        except (OSError, RuntimeError, TypeError, ValueError):
            return False

    def allows_project_write(self, resource_path):
        return (
            self.mode == self.PROJECT_AUTONOMOUS
            and self.is_within_projects_root(resource_path)
        )

    def requires_approval(self, capability, resource_path=None):
        if capability == "read":
            return self.mode == self.STRICT
        if capability == "control":
            return self.mode == self.STRICT
        if capability == "project_write":
            return not (
                self.allows_project_write(resource_path)
                or self.allows_trusted_folder_write(resource_path)
            )
        if capability == "project_create":
            if self.mode == self.PROJECT_AUTONOMOUS:
                return not (
                    self.allows_project_write(resource_path)
                    and not Path(resource_path).exists()
                )
            return True
        if capability == "file_read":
            return self.mode == self.STRICT
        if capability == "file_write":
            return not self.allows_trusted_folder_write(resource_path)
        return True

    def public_state(self):
        labels = {
            self.STRICT: "Sempre pedir",
            self.SUPERVISED: "Supervisionado",
            self.PROJECT_AUTONOMOUS: "Autonomia no projeto",
            self.TRUSTED_FOLDERS: "Pastas autorizadas",
        }
        return {
            "mode": self.mode,
            "label": labels[self.mode],
            "projects_root": str(self.projects_root),
            "autonomous_project_writes": self.mode == self.PROJECT_AUTONOMOUS,
            "trusted_folders": sorted(
                (str(path) for path in self.trusted_folders),
                key=str.casefold,
            ),
        }

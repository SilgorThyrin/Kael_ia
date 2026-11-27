"""Bounded file listing and text reads inside individually approved folders."""
from pathlib import Path

from core.attachments import SUPPORTED_EXTENSIONS
from core.project_indexer import ProjectIndexer


class LocalFileWorkspace:
    MAX_ENTRIES = 300
    MAX_FILE_BYTES = 1024 * 1024
    EXCLUDED_DIRECTORIES = {
        ".git", "__pycache__", "node_modules", "venv", ".venv",
    }

    def __init__(self, permission_policy):
        self.permission_policy = permission_policy

    @staticmethod
    def _absolute_path(value):
        if not isinstance(value, str) or not value.strip() or len(value) > 2048:
            raise ValueError("Informe um caminho completo válido.")
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise ValueError("O caminho deve ser absoluto.")
        if path.is_symlink():
            raise PermissionError("O acesso a links simbólicos não é permitido.")
        try:
            return path.resolve(strict=True)
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValueError(f"O caminho não existe ou não pode ser acessado: {exc}") from exc

    def list_directory(self, value):
        directory = self._absolute_path(value)
        if not self.permission_policy.is_trusted_directory(directory):
            raise PermissionError("Esta pasta ainda não foi autorizada.")
        entries = []
        limit_reached = False
        try:
            for child in directory.iterdir():
                if child.is_symlink():
                    continue
                if len(entries) >= self.MAX_ENTRIES:
                    limit_reached = True
                    break
                if child.is_dir():
                    if child.name.casefold() in self.EXCLUDED_DIRECTORIES:
                        continue
                    entries.append({
                        "name": child.name,
                        "kind": "directory",
                        "path": str(child.resolve()),
                    })
                elif child.is_file():
                    entries.append({
                        "name": child.name,
                        "kind": "file",
                        "path": str(child.resolve()),
                        "readable": self._is_readable_name(child.name),
                        "size": child.stat().st_size,
                    })
        except OSError as exc:
            raise ValueError(f"Não foi possível listar a pasta: {exc}") from exc
        entries.sort(key=lambda item: (item["kind"] != "directory", item["name"].casefold()))
        return {
            "path": str(directory),
            "entries": entries,
            "limit_reached": limit_reached,
        }

    @staticmethod
    def _is_readable_name(filename):
        if ProjectIndexer.SENSITIVE_NAME.search(filename):
            return False
        suffix = Path(filename).suffix.casefold()
        basename = filename.casefold()
        return suffix[1:] in SUPPORTED_EXTENSIONS or basename in {
            "dockerfile", "makefile", ".gitignore",
        }

    def read_file(self, value):
        path = self._absolute_path(value)
        if not self.permission_policy.is_trusted_file(path):
            raise PermissionError("O arquivo não está em uma pasta autorizada.")
        if not self._is_readable_name(path.name):
            raise ValueError("Este arquivo não é um tipo de texto permitido ou parece conter dados sensíveis.")
        try:
            size = path.stat().st_size
            if size > self.MAX_FILE_BYTES:
                raise ValueError("O arquivo excede o limite de 1 MB.")
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("O arquivo não contém texto UTF-8 válido.") from exc
        except OSError as exc:
            raise ValueError(f"Não foi possível ler o arquivo: {exc}") from exc
        if "\x00" in content:
            raise ValueError("O arquivo contém dados binários e não pode ser lido como texto.")
        if ProjectIndexer.SENSITIVE_VALUE.search(content):
            raise ValueError("O arquivo parece conter segredos; leitura bloqueada.")
        return {
            "filename": path.name,
            "path": str(path),
            "content": content,
            "size": size,
        }

"""Safely collects text source files from one explicitly selected local project."""
import os
from pathlib import Path
import re


class ProjectIndexer:
    MAX_FILES = 200
    MAX_FILE_BYTES = 180 * 1024
    MAX_TOTAL_BYTES = 5 * 1024 * 1024
    MAX_TOTAL_CHARS = 1_000_000
    EXTENSIONS = {
        ".gd", ".gdshader", ".tscn", ".tres", ".lua", ".luau", ".json",
        ".toml", ".cfg", ".ini", ".md", ".txt", ".xml", ".yaml", ".yml",
        ".cs", ".py", ".ts", ".js",
    }
    EXCLUDED_DIRS = {
        ".git", ".godot", ".idea", ".vscode", "__pycache__", ".pytest_cache",
        ".mypy_cache", "node_modules", "vendor", "build", "dist", "target",
        "bin", "obj", "library", "logs", "temp", "tmp", ".venv", "venv",
        "userdata", "user_data", "profiles", "accounts", "savegames",
        "personal_data", "sensitive",
    }
    SENSITIVE_NAME = re.compile(
        r"(^\.env(?:\.|$)|secret|credential|password|token|private|"
        r"(^|[._-])id_rsa($|[._-])|(^|[._-])id_ed25519($|[._-])|"
        r"(^|[._-])(?:user[_-]?data|profile[_-]?data|account[_-]?data|"
        r"savegame|personal[_-]?data)(?:[._-]|$)|"
        r"\.(?:pem|key|p12|pfx)$)",
        re.IGNORECASE,
    )
    EMAIL_ADDRESS = re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    )
    SENSITIVE_VALUE = re.compile(
        r"""(?im)^\s*(?:[\w.-]*(?:api[_-]?key|secret|password|token|access[_-]?key))"""
        r"""\s*[:=]\s*(['"])(?!\s*(?:\$\{|%|\{\{|os\.getenv|process\.env|env\())[^'"\r\n]{8,}\1"""
    )

    def __init__(self, project_path, projects_root):
        self.projects_root = Path(projects_root).resolve()
        self.project_path = Path(project_path).resolve()
        if (
            self.project_path == self.projects_root
            or self.projects_root not in self.project_path.parents
        ):
            raise ValueError("O projeto deve estar dentro da pasta de projetos autorizada.")
        if not self.project_path.is_dir():
            raise ValueError("A pasta do projeto não existe ou não é um diretório.")

    def scan(self):
        documents = []
        skipped = {
            "excluded": 0, "oversized": 0, "sensitive": 0, "invalid_text": 0,
            "emails_redacted": 0,
        }
        total_bytes = 0
        total_chars = 0
        capped = False

        for current, dirs, filenames in os.walk(self.project_path, topdown=True, followlinks=False):
            current_path = Path(current)
            dirs[:] = sorted(
                directory for directory in dirs
                if directory.casefold() not in self.EXCLUDED_DIRS
                and not self.SENSITIVE_NAME.search(directory)
                and not (current_path / directory).is_symlink()
            )
            for filename in sorted(filenames):
                path = current_path / filename
                if (
                    path.suffix.casefold() not in self.EXTENSIONS
                    or any(
                        self.SENSITIVE_NAME.search(part)
                        for part in path.relative_to(self.project_path).parts
                    )
                    or path.is_symlink()
                ):
                    skipped["excluded"] += 1
                    continue
                if len(documents) >= self.MAX_FILES:
                    capped = True
                    break
                try:
                    size = path.stat().st_size
                    if size > self.MAX_FILE_BYTES or total_bytes + size > self.MAX_TOTAL_BYTES:
                        skipped["oversized"] += 1
                        continue
                    content = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    skipped["invalid_text"] += 1
                    continue
                if "\x00" in content:
                    skipped["invalid_text"] += 1
                    continue
                if self.SENSITIVE_VALUE.search(content):
                    skipped["sensitive"] += 1
                    continue

                content, email_count = self.EMAIL_ADDRESS.subn("[email redacted]", content)
                skipped["emails_redacted"] += email_count
                if total_chars + len(content) > self.MAX_TOTAL_CHARS:
                    skipped["oversized"] += 1
                    continue

                relative = path.relative_to(self.project_path).as_posix()
                documents.append({"filename": relative, "content": content})
                total_bytes += size
                total_chars += len(content)
            if capped:
                break

        return {
            "documents": documents,
            "files_indexed": len(documents),
            "bytes_indexed": total_bytes,
            "skipped": skipped,
            "limit_reached": capped,
        }

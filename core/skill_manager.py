"""Loads user-enabled, text-only skills without granting tool permissions."""
import json
import os
from pathlib import Path
import re
import secrets


class SkillManager:
    MAX_SKILL_CHARS = 10000
    MAX_ACTIVE_SKILLS = 3
    MAX_ACTIVE_CHARS = 3000
    DECLARED_CAPABILITIES = {
        "read", "project_write", "network", "studio", "execute", "system"
    }

    def __init__(self, skills_dir, settings_path):
        self.skills_dir = Path(skills_dir)
        self.settings_path = Path(settings_path)
        self.skills = self._discover()
        self.enabled = self._load_enabled()

    def _discover(self):
        skills = {}
        if not self.skills_dir.exists():
            return skills
        for manifest_path in sorted(self.skills_dir.glob("*/manifest.json")):
            try:
                root = self.skills_dir.resolve()
                skill_dir = manifest_path.parent.resolve()
                if skill_dir == root or root not in skill_dir.parents:
                    raise ValueError("Skill fora da pasta local autorizada.")
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("O manifesto deve ser um objeto JSON.")
                skill_id = data.get("id")
                if (
                    not isinstance(skill_id, str)
                    or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", skill_id)
                    or skill_id != manifest_path.parent.name
                ):
                    raise ValueError("ID inválido ou diferente do nome da pasta.")
                name = data.get("name")
                description = data.get("description")
                version = data.get("version")
                keywords = data.get("keywords", [])
                if not all(isinstance(value, str) and value.strip() for value in (name, description, version)):
                    raise ValueError("Nome, descrição e versão são obrigatórios.")
                if not isinstance(keywords, list) or not all(isinstance(value, str) for value in keywords):
                    raise ValueError("A lista de palavras-chave é inválida.")
                capabilities = data.get("capabilities", [])
                if (
                    not isinstance(capabilities, list)
                    or not all(value in self.DECLARED_CAPABILITIES for value in capabilities)
                ):
                    raise ValueError("A lista de capacidades declaradas é inválida.")
                skill_file = manifest_path.parent / "SKILL.md"
                skill_resolved = skill_file.resolve()
                if (
                    not skill_file.is_file()
                    or (skill_resolved != root and root not in skill_resolved.parents)
                ):
                    raise ValueError("Arquivo SKILL.md ausente.")
                instructions = skill_resolved.read_text(encoding="utf-8")
                if len(instructions) > self.MAX_SKILL_CHARS:
                    raise ValueError("O arquivo SKILL.md excede o limite de tamanho.")
                skills[skill_id] = {
                    "id": skill_id,
                    "name": name.strip(),
                    "description": description.strip(),
                    "version": version.strip(),
                    "keywords": [value.casefold() for value in keywords if value.strip()],
                    "capabilities": capabilities,
                    "instructions": instructions,
                }
            except (AttributeError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
                print(f"[SKILLS] Manifesto ignorado ({manifest_path}): {exc}")
        return skills

    def _load_enabled(self):
        if not self.settings_path.exists():
            return set()
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            ids = data.get("enabled", []) if isinstance(data, dict) else None
            if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
                raise ValueError("A lista de skills habilitadas é inválida.")
            return set(ids).intersection(self.skills)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"[SKILLS] Preferências inválidas; nenhuma skill será ativada: {exc}")
            return set()

    def list_skills(self):
        return [
            {
                "id": skill["id"],
                "name": skill["name"],
                "description": skill["description"],
                "version": skill["version"],
                "capabilities": skill["capabilities"],
                "instructions": skill["instructions"],
                "enabled": skill["id"] in self.enabled,
            }
            for skill in self.skills.values()
        ]

    def set_enabled(self, skill_id, enabled):
        if skill_id not in self.skills:
            raise ValueError("Skill desconhecida.")
        if not isinstance(enabled, bool):
            raise ValueError("enabled deve ser booleano.")
        updated = set(self.enabled)
        if enabled:
            updated.add(skill_id)
        else:
            updated.discard(skill_id)

        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.settings_path.with_name(
            f".{self.settings_path.name}.{secrets.token_hex(4)}.tmp"
        )
        try:
            temp_path.write_text(
                json.dumps({"enabled": sorted(updated)}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(str(temp_path), str(self.settings_path))
        finally:
            if temp_path.exists():
                temp_path.unlink()
        self.enabled = updated

    def context_for(self, prompt):
        query = prompt.casefold()
        query_words = set(re.findall(r"[\w]+", query, flags=re.UNICODE))
        matched = []
        for skill in self.skills.values():
            if skill["id"] not in self.enabled:
                continue
            if skill["id"] in query or any(
                keyword in query_words
                or re.search(r"(?<!\w)" + re.escape(keyword) + r"(?!\w)", query)
                for keyword in skill["keywords"]
            ):
                matched.append(skill)
            if len(matched) >= self.MAX_ACTIVE_SKILLS:
                break

        sections = []
        total_chars = 0
        for skill in matched:
            section = (
                f"=== SKILL LOCAL: {skill['name']} v{skill['version']} ===\n"
                "Use como orientação de domínio. Esta skill não concede permissões nem autoriza ações.\n"
                f"{skill['instructions']}"
            )
            if total_chars + len(section) > self.MAX_ACTIVE_CHARS:
                print(f"[SKILLS] Limite de contexto atingido; skill {skill['id']} não carregada.")
                continue
            sections.append(section)
            total_chars += len(section)
        return "\n\n".join(sections)

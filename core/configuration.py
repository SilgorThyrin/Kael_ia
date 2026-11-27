"""Portable configuration loading and validation for the local Kael runtime."""
import json
import math
import os
import re
from pathlib import Path
from urllib.parse import urlparse


APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = APP_DIR / "config" / "config.json"


def _resolve_path(value, base_dir):
    if not isinstance(value, (str, os.PathLike)) or not str(value).strip():
        raise ValueError("Os caminhos da configuração devem ser textos não vazios.")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def _read_integer(value, name, minimum, maximum):
    if isinstance(value, bool) or not (
        isinstance(value, int)
        or isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip())
    ):
        raise ValueError(f"{name} deve ser um inteiro entre {minimum} e {maximum}.")
    parsed = int(value)
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} deve estar entre {minimum} e {maximum}.")
    return parsed


def load_config(environ=None, base_dir=None):
    env = os.environ if environ is None else environ
    root = Path(base_dir).resolve() if base_dir else APP_DIR
    config_path_value = env.get("KAEL_CONFIG_PATH")
    config_path = _resolve_path(
        config_path_value if config_path_value else root / "config" / "config.json",
        root,
    )
    config = {}
    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as file:
                config = json.load(file)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Não foi possível ler a configuração {config_path}: {exc}") from exc
        if not isinstance(config, dict):
            raise ValueError(f"A configuração {config_path} deve conter um objeto JSON.")

    def value(env_name, key, default):
        return env.get(env_name, config.get(key, default))

    projects_default = root.parent / "arquivos-de-inteligencia" / "Projetos"
    projects_root = _resolve_path(
        value("KAEL_PROJECTS_ROOT", "projects_root", projects_default),
        root,
    )
    project_path = _resolve_path(
        value(
            "KAEL_PROJECT_PATH",
            "project_path",
            projects_root / "Ecos_de_Aethelgard",
        ),
        root,
    )
    legacy_memory = root.parent / "arquivos-de-inteligencia" / "conhecimento"
    memory_default = legacy_memory if legacy_memory.exists() else root / "kael_knowledge"
    memory_dir = _resolve_path(
        value("KAEL_MEMORY_DIR", "memory_dir", memory_default),
        root,
    )

    ollama_url = str(value(
        "KAEL_OLLAMA_URL",
        "ollama_url",
        "http://127.0.0.1:8080",
    )).strip().rstrip("/")
    parsed_ollama_url = urlparse(ollama_url)
    if parsed_ollama_url.scheme not in {"http", "https"} or not parsed_ollama_url.netloc:
        raise ValueError("ollama_url deve ser uma URL HTTP ou HTTPS válida.")

    model_name = value("KAEL_MODEL", "model_name", "qwen3:8b")
    if not isinstance(model_name, str) or not model_name.strip():
        raise ValueError("model_name deve ser um texto não vazio.")

    temperature_value = value("KAEL_TEMPERATURE", "temperature", 0.7)
    if isinstance(temperature_value, bool):
        raise ValueError("temperature deve ser um número entre 0 e 2.")
    try:
        temperature = float(temperature_value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("temperature deve ser um número entre 0 e 2.") from exc
    if not math.isfinite(temperature) or not 0 <= temperature <= 2:
        raise ValueError("temperature deve estar entre 0 e 2.")

    max_tokens = _read_integer(
        value("KAEL_MAX_TOKENS", "max_tokens", 2048),
        "max_tokens",
        64,
        8192,
    )

    think = value("KAEL_THINK", "think", True)
    if isinstance(think, str):
        lowered = think.strip().lower()
        if lowered not in {"true", "false", "1", "0", "yes", "no"}:
            raise ValueError("KAEL_THINK deve ser true ou false.")
        think = lowered in {"true", "1", "yes"}
    if not isinstance(think, bool):
        raise ValueError("think deve ser booleano.")

    api_host = value("KAEL_API_HOST", "api_host", "127.0.0.1")
    if not isinstance(api_host, str) or api_host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("api_host deve permanecer em loopback por segurança.")
    api_port = _read_integer(
        value("KAEL_API_PORT", "api_port", 8000),
        "api_port",
        1,
        65535,
    )

    system_prompt = value("KAEL_SYSTEM_PROMPT", "system_prompt", "")
    if not isinstance(system_prompt, str):
        raise ValueError("system_prompt deve ser um texto.")

    return {
        **config,
        "config_path": str(config_path),
        "ollama_url": ollama_url,
        "model_name": model_name.strip(),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "think": think,
        "projects_root": str(projects_root),
        "project_path": str(project_path),
        "memory_dir": str(memory_dir),
        "api_host": api_host,
        "api_port": api_port,
        "system_prompt": system_prompt,
    }


def validate_generation_settings(settings, available_models=None):
    if not isinstance(settings, dict):
        raise ValueError("As configurações de geração devem ser um objeto.")
    allowed = {"model", "temperature", "max_tokens", "think"}
    if set(settings) - allowed:
        raise ValueError("A configuração contém campos não suportados.")

    model = settings.get("model")
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise ValueError("Selecione um modelo local válido.")
    if available_models is not None and model not in available_models:
        raise ValueError("O modelo selecionado não está instalado no Ollama.")

    temperature = settings.get("temperature")
    if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
        raise ValueError("temperature deve ser um número entre 0 e 2.")
    try:
        temperature = float(temperature)
    except OverflowError as exc:
        raise ValueError("temperature deve estar entre 0 e 2.") from exc
    if not math.isfinite(temperature) or not 0 <= temperature <= 2:
        raise ValueError("temperature deve estar entre 0 e 2.")

    max_tokens = settings.get("max_tokens")
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int):
        raise ValueError("max_tokens deve ser um inteiro entre 64 e 8192.")
    if not 64 <= max_tokens <= 8192:
        raise ValueError("max_tokens deve estar entre 64 e 8192.")

    think = settings.get("think")
    if not isinstance(think, bool):
        raise ValueError("think deve ser booleano.")
    return {
        "model": model.strip(),
        "temperature": float(temperature),
        "max_tokens": max_tokens,
        "think": think,
    }

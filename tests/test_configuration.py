import json
import tempfile
import unittest
from pathlib import Path

from core.configuration import load_config, validate_generation_settings


class ConfigurationTests(unittest.TestCase):
    def test_environment_overrides_are_resolved_relative_to_app_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings_file = root / "local.json"
            settings_file.write_text(
                json.dumps({"model_name": "model-from-file", "api_port": 9000}),
                encoding="utf-8",
            )
            config = load_config(
                environ={
                    "KAEL_CONFIG_PATH": "local.json",
                    "KAEL_PROJECTS_ROOT": "Projects",
                    "KAEL_API_PORT": "9001",
                    "KAEL_THINK": "false",
                },
                base_dir=root,
            )

        self.assertEqual(config["config_path"], str(settings_file.resolve()))
        self.assertEqual(config["projects_root"], str((root / "Projects").resolve()))
        self.assertEqual(config["api_port"], 9001)
        self.assertFalse(config["think"])
        self.assertEqual(config["model_name"], "model-from-file")

    def test_invalid_config_and_non_loopback_api_host_are_reported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "config.json").write_text("{invalid", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(environ={}, base_dir=root)

            (config_dir / "config.json").write_text(
                json.dumps({"api_host": "0.0.0.0"}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_config(environ={}, base_dir=root)

    def test_generation_settings_validate_model_and_ranges(self):
        valid = {
            "model": "qwen3:8b",
            "temperature": 0.7,
            "max_tokens": 1024,
            "think": True,
        }
        self.assertEqual(
            validate_generation_settings(valid, ["qwen3:8b"])["max_tokens"],
            1024,
        )
        for invalid in (
            {**valid, "model": "missing"},
            {**valid, "temperature": 2.1},
            {**valid, "max_tokens": True},
            {**valid, "think": "yes"},
            {**valid, "temperature": 10 ** 400},
        ):
            with self.assertRaises(ValueError):
                validate_generation_settings(invalid, ["qwen3:8b"])

    def test_integer_settings_reject_fractional_values_instead_of_truncating(self):
        for environ in (
            {"KAEL_MAX_TOKENS": "512.5"},
            {"KAEL_API_PORT": "8000.5"},
        ):
            with self.subTest(environ=environ), self.assertRaises(ValueError):
                load_config(environ=environ)


if __name__ == "__main__":
    unittest.main()

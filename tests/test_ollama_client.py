import unittest
from unittest.mock import Mock, patch

from ai import ollama_client


class OllamaClientTests(unittest.TestCase):
    @patch("ai.ollama_client.check_ollama_status")
    @patch("ai.ollama_client.requests.post")
    @patch("ai.ollama_client.load_config")
    def test_selected_generation_settings_are_sent_to_ollama(
        self, load_config, post, check_status
    ):
        load_config.return_value = {
            "ollama_url": "http://127.0.0.1:8080",
            "model_name": "old-model",
            "temperature": 0.7,
            "max_tokens": 2048,
            "think": True,
            "system_prompt": "",
        }
        response = Mock()
        response.iter_lines.return_value = [
            b'{"response":"Hello"}',
            b'{"done":true}',
        ]
        post.return_value = response
        response.raise_for_status.return_value = None

        result = ollama_client.generate_response(
            "Prompt",
            settings={
                "model": "qwen3:8b",
                "temperature": 0.4,
                "max_tokens": 512,
                "think": False,
            },
        )

        self.assertEqual(result["response"], "Hello")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "qwen3:8b")
        self.assertEqual(payload["options"], {
            "temperature": 0.4,
            "num_predict": 512,
            "think": False,
        })
        post.assert_called_once()
        check_status.assert_not_called()


if __name__ == "__main__":
    unittest.main()

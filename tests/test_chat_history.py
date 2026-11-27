import unittest

from core.chat_history import validate_chat_history


class ChatHistoryTests(unittest.TestCase):
    def test_history_is_normalized_to_roles_and_content_only(self):
        history = validate_chat_history([{
            "role": "user",
            "content": "Olá",
            "attachments": [{"filename": "private.txt"}],
            "thinking": "ignored",
        }])
        self.assertEqual(history, [{"role": "user", "content": "Olá"}])

    def test_history_limits_and_invalid_roles_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_chat_history([{"role": [], "content": "invalid"}])
        with self.assertRaises(ValueError):
            validate_chat_history([
                {"role": "user", "content": "x" * 12001},
            ])
        with self.assertRaises(ValueError):
            validate_chat_history([
                {"role": "user", "content": "x" * 10000},
                {"role": "assistant", "content": "x" * 10000},
                {"role": "user", "content": "x" * 10000},
                {"role": "assistant", "content": "x" * 10000},
                {"role": "user", "content": "x"},
            ])


if __name__ == "__main__":
    unittest.main()

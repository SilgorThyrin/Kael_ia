"""Validation helpers for browser-provided, conversation-scoped chat context."""


def validate_chat_history(history):
    if not isinstance(history, list) or len(history) > 40:
        raise ValueError("O histórico deve conter até 40 mensagens.")
    clean_history = []
    total_chars = 0
    for message in history:
        if not isinstance(message, dict):
            raise ValueError("Cada mensagem do histórico deve ser um objeto.")
        role = message.get("role")
        content = message.get("content")
        if not isinstance(role, str) or role not in {"user", "ai", "assistant"}:
            raise ValueError("O histórico contém um papel de mensagem inválido.")
        if not isinstance(content, str) or len(content) > 12000:
            raise ValueError("Cada mensagem do histórico deve ter até 12.000 caracteres.")
        total_chars += len(content)
        if total_chars > 40000:
            raise ValueError("O histórico excede 40.000 caracteres.")
        clean_history.append({"role": role, "content": content})
    return clean_history

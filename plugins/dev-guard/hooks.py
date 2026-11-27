import re


def pre_cloud(payload: dict) -> dict:
    """Mascara CPFs antes de qualquer envio do Chefe para o Gerente Gemini."""
    texto = payload.get("texto", "")
    if texto:
        payload["texto"] = re.sub(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", "[CPF_PROTEGIDO]", texto)
    return payload

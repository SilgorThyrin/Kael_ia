# -*- coding: utf-8 -*-
import requests
import json

OLLAMA_URL = "http://127.0.0.1:8080/api/generate"
MODELO_VISAO = "qwen2-vl:2b"

def analisar_screenshot(imagem_b64, pergunta="Descreva a imagem e aponte problemas visuais."):
    try:
        # O Qwen2-VL pode ficar na VRAM junto com o Granite se a quantização for baixa,
        # mas por segurança, vamos usar o payload correto.
        payload = {
            "model": MODELO_VISAO,
            "prompt": pergunta,
            "images": [imagem_b64],
            "stream": False,
            "options": {"temperature": 0.2, "num_ctx": 4096}
        }
        
        resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
        
        if resp.status_code == 200:
            return resp.json().get("response", "").strip()
        else:
            return f"Erro Vision API: {resp.status_code}"
    except Exception as e:
        return f"Erro na Visao: {str(e)}"
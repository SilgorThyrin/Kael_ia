# -*- coding: utf-8 -*-
import os
import json
import time
import re

BASE_TEMPLATES = "Templates"
INDEX_PATH = os.path.join(BASE_TEMPLATES, "index.json")

def _garantir_pasta():
    if not os.path.exists(BASE_TEMPLATES):
        os.makedirs(os.path.join(BASE_TEMPLATES, "roblox_lua"))
        os.makedirs(os.path.join(BASE_TEMPLATES, "godot_gdscript"))
        os.makedirs(os.path.join(BASE_TEMPLATES, "python_pygame"))
    if not os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump({"funcionalidades": {}}, f, indent=2)

def buscar_template(termo_busca, plataforma="roblox_lua"):
    """
    Busca um template no index.json baseado em palavras-chave.
    """
    _garantir_pasta()
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            index = json.load(f)
    except Exception:
        return None

    termo = termo_busca.lower()
    melhores_matchs = []

    for func_nome, dados in index.get("funcionalidades", {}).items():
        descricao = dados.get("descricao", "").lower()
        # Verifica se o termo de busca bate com o nome ou a descrição
        if termo in func_nome or termo in descricao:
            impls = dados.get("implementacoes", {})
            if plataforma in impls:
                caminho_arquivo = os.path.join(BASE_TEMPLATES, impls[plataforma]["arquivo"])
                if os.path.exists(caminho_arquivo):
                    with open(caminho_arquivo, "r", encoding="utf-8") as f:
                        codigo = f.read()
                    melhores_matchs.append({
                        "funcionalidade": func_nome,
                        "codigo": codigo,
                        "status": impls[plataforma].get("status", "desconhecido")
                    })

    if melhores_matchs:
        # Retorna o primeiro que encontrou
        return melhores_matchs[0]
    return None

def salvar_template(nome_func, codigo, plataforma, descricao, tags):
    """
    Salva um novo template na pasta e atualiza o index.
    """
    _garantir_pasta()
    
    # Cria um nome de arquivo seguro
    nome_arquivo = re.sub(r'[^a-zA-Z0-9_]', '', nome_func.lower()) + "_" + str(int(time.time())) + ".lua"
    caminho_relativo = f"{plataforma}/{nome_arquivo}"
    caminho_completo = os.path.join(BASE_TEMPLATES, caminho_relativo)

    # Salva o arquivo .lua
    with open(caminho_completo, "w", encoding="utf-8") as f:
        f.write(codigo)

    # Atualiza o index.json
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            index = json.load(f)
    except Exception:
        index = {"funcionalidades": {}}

    if "funcionalidades" not in index:
        index["funcionalidades"] = {}

    chave = nome_func.lower().replace(" ", "_")
    if chave not in index["funcionalidades"]:
        index["funcionalidades"][chave] = {
            "descricao": descricao,
            "tags": tags,
            "implementacoes": {}
        }

    index["funcionalidades"][chave]["implementacoes"][plataforma] = {
        "arquivo": caminho_relativo,
        "status": "testado" # Como estamos salvando, assumimos que passou no teste
    }

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print(f"[LIBRARY] Novo template salvo: {caminho_relativo}")
    return caminho_relativo
# -*- coding: utf-8 -*-
import os
import json

def obter_resumo_mapa(base_dir, projeto):
    """
    Le o game_estado.json e retorna um resumo textual do que existe no mapa.
    """
    projeto_dir = os.path.join(base_dir, "Projetos", projeto)
    path = os.path.join(projeto_dir, "game_estado.json")
    
    if not os.path.exists(path):
        return "O mapa está vazio (sem game_estado.json)."

    try:
        with open(path, "r", encoding="utf-8") as f:
            estado = json.load(f)
    except Exception:
        return "Erro ao ler o mapa."

    objetos = estado.get("objetos", []) or estado.get("instancias", [])
    total = estado.get("total_instancias", len(objetos))
    
    if total == 0:
        return "O mapa está vazio."

    # Contadores
    models = 0
    parts = 0
    scripts = 0
    spawns = 0
    huds = 0
    moedas = 0
    flutuantes = 0
    
    nomes_encontrados = set()

    for obj in objetos:
        if isinstance(obj, dict):
            classe = str(obj.get("classe", "") or obj.get("className", "")).lower()
            nome = str(obj.get("nome", "") or obj.get("name", "")).lower()
            y = float(obj.get("posicao", {}).get("Y", 0) or obj.get("y", 0))
            
            nomes_encontrados.add(nome)
            
            if "model" in classe: models += 1
            elif "part" in classe or "basepart" in classe: parts += 1
            elif "script" in classe: scripts += 1
            
            if "spawnlocation" in classe or "spawn" in nome: spawns += 1
            if "screengui" in classe or "gui" in nome: huds += 1
            if "moeda" in nome or "coin" in nome or "gold" in nome: moedas += 1
            if y > 60 and ("part" in classe or "basepart" in classe): flutuantes += 1

    resumo = [
        f"- Total de instâncias: {total}",
        f"- Models (estruturas): {models}",
        f"- Parts soltas: {parts}",
        f"- Scripts: {scripts}",
        f"- SpawnLocations: {spawns}",
        f"- HUDs (ScreenGui): {huds}",
        f"- Objetos flutuantes (Y>60): {flutuantes}"
    ]

    # Adiciona alguns nomes de estruturas para o LLM ter contexto
    amostra_nomes = [n for n in nomes_encontrados if len(n) > 3][:10]
    if amostra_nomes:
        resumo.append(f"- Exemplos de nomes no mapa: {', '.join(amostra_nomes)}")

    return "\n".join(resumo)
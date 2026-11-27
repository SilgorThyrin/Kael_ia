"""
KAEL CREATIVITY ENGINE v1.0
============================
Motor de criatividade para tornar o Kael mais inovador e criativo.
"""

import json
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class CreativityEngine:
    """
    Motor que injeta criatividade controlada nas respostas do Kael.
    """

    TEMPERATURE_MAP = {
        "tecnico": 0.15,
        "equilibrado": 0.45,
        "criativo": 0.75,
        "exploratorio": 0.9,
        "refinamento": 0.3,
    }

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.ideas_path = self.base_dir / "kael_knowledge" / "ideias_criativas.json"
        self.ideas_path.parent.mkdir(parents=True, exist_ok=True)
        self._ideas_cache: List[Dict[str, Any]] = []
        self._load_ideas()

    def get_temperature(self, task_type: str) -> float:
        return self.TEMPERATURE_MAP.get(task_type, 0.45)

    def get_temperature_range(self, task_type: str) -> Tuple[float, float]:
        base = self.get_temperature(task_type)
        if task_type == "criativo":
            return (0.6, 0.9)
        elif task_type == "exploratorio":
            return (0.75, 1.1)
        elif task_type == "tecnico":
            return (0.1, 0.25)
        else:
            return (max(0.1, base - 0.15), min(1.1, base + 0.15))

    def _load_ideas(self):
        try:
            if self.ideas_path.exists():
                with open(self.ideas_path, "r", encoding="utf-8") as f:
                    self._ideas_cache = json.load(f)
        except Exception:
            self._ideas_cache = []

    def _save_ideas(self):
        try:
            with open(self.ideas_path, "w", encoding="utf-8") as f:
                json.dump(self._ideas_cache[-200:], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add_idea(self, genero: str, ideia: str, fonte: str, sucesso: Optional[bool] = None):
        entry = {
            "genero": genero,
            "ideia": ideia,
            "fonte": fonte,
            "sucesso": sucesso,
            "timestamp": time.time(),
        }
        self._ideas_cache.append(entry)
        self._save_ideas()

    def get_ideas_for_genre(self, genero: str, limit: int = 10) -> List[Dict[str, Any]]:
        return [i for i in self._ideas_cache if i.get("genero") == genero][-limit:]

    def synthesize_ideas(self, genero_principal: str,
                         generos_referencia: List[str],
                         num_ideias: int = 3) -> List[str]:
        ideias_principais = self.get_ideas_for_genre(genero_principal, limit=20)
        ideias_ref = []
        for g in generos_referencia:
            ideias_ref.extend(self.get_ideas_for_genre(g, limit=10))

        if not ideias_principais and not ideias_ref:
            return []

        sintese = []
        for _ in range(num_ideias):
            if ideias_principais and ideias_ref:
                base = random.choice(ideias_principais)["ideia"]
                ref = random.choice(ideias_ref)["ideia"]
                sintese.append(
                    f"Fusão [{genero_principal} + {random.choice(generos_referencia)}]: "
                    f"{base} combinado com {ref}"
                )
            elif ideias_principais:
                sintese.append(random.choice(ideias_principais)["ideia"])

        return sintese

    def generate_terrain_variations(self, preset: str, count: int = 3) -> List[Dict[str, Any]]:
        variacoes = []
        biomas = {
            "planicies": ["grama", "flores", "rios rasos", "árvores esparsas"],
            "colinas": ["terra", "pedras", "árvores médias", "cavernas pequenas"],
            "montanhas": ["rocha", "neve", "cavernas grandes", "mina de minério"],
            "ilha": ["areia", "palmeiras", "água rasa", "recifes"],
        }
        elementos = biomas.get(preset, ["grama", "árvores"])

        for i in range(count):
            seed = random.randint(0, 2_147_483_647)
            variacao = {
                "preset": preset,
                "seed": seed,
                "tamanho": random.choice([256, 384, 512]),
                "elementos_destaque": random.sample(elementos, min(3, len(elementos))),
                "descricao": f"{preset.title()} com ênfase em {', '.join(random.sample(elementos, 2))}",
            }
            variacoes.append(variacao)

        return variacoes

    def generate_asset_variations(self, asset_type: str, count: int = 3) -> List[Dict[str, Any]]:
        estilos = ["realista", "estilizado", "low_poly", "voxel", "pirata", "steampunk"]
        variacoes = []

        for i in range(count):
            estilo = random.choice(estilos)
            seed = random.randint(0, 2_147_483_647)
            variacao = {
                "tipo": asset_type,
                "estilo": estilo,
                "seed": seed,
                "quantidade": random.randint(1, 5),
                "descricao": f"{asset_type.title()} no estilo {estilo}",
            }
            variacoes.append(variacao)

        return variacoes

    def creative_generate(self, fn_llm, prompt_base: str,
                          task_type: str = "criativo",
                          max_attempts: int = 3) -> Dict[str, Any]:
        temp_range = self.get_temperature_range(task_type)
        tentativas = []

        for i in range(max_attempts):
            temp = temp_range[0] + (temp_range[1] - temp_range[0]) * (i / max(1, max_attempts - 1))
            try:
                resposta = fn_llm(prompt_base, temperatura=round(temp, 2))
                tentativas.append({
                    "tentativa": i + 1,
                    "temperatura": round(temp, 2),
                    "resposta": resposta,
                    "tamanho": len(resposta),
                })
            except Exception as e:
                tentativas.append({
                    "tentativa": i + 1,
                    "temperatura": round(temp, 2),
                    "erro": str(e),
                })

        validas = [t for t in tentativas if "resposta" in t and not t.get("erro")]
        if validas:
            melhor = max(validas, key=lambda t: t["tamanho"])
        else:
            melhor = tentativas[0] if tentativas else {}

        return {
            "melhor": melhor,
            "todas_tentativas": tentativas,
            "task_type": task_type,
        }

    def get_creativity_prompt_section(self, genero: str = "") -> str:
        ideias = self.synthesize_ideas(genero, ["aventura", "rpg", "simulador"], num_ideias=2)
        ideias_texto = "\n".join(f"• {i}" for i in ideias) if ideias else "• (sem ideias prévias registradas)"

        return f"""
=== INJEÇÃO DE CRIATIVIDADE ===
O Kael deve pensar além do óbvio. Considere:
- Mesclar mecânicas de gêneros diferentes (ex: RPG + FPS, Simulador + Terror)
- Criar sistemas de progressão não lineares
- Propor ambientes com identidade visual forte e memorável
- Incluir surpresas para o jogador (eventos aleatórios, segredos escondidos)

IDEIAS SUGERIDAS PARA SÍNTESE ({genero}):
{ideias_texto}

Não se contente com o genérico. Seja ousado, mas mantenha a viabilidade técnica.
"""


creativity_engine: Optional[CreativityEngine] = None


def init_creativity_engine(base_dir: str) -> CreativityEngine:
    global creativity_engine
    creativity_engine = CreativityEngine(base_dir)
    return creativity_engine


def get_creativity_engine() -> Optional[CreativityEngine]:
    return creativity_engine
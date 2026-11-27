# -*- coding: utf-8 -*-
"""
game_critic.py - Auto-avaliador do Kael (v5 — Focus + Runtime Errors)
======================================================================
Novidades v5:
  - Parametro focus_area: forca o Critic a reportar a categoria focada
    como prioridade (mesmo que outra esteja pior).
  - Parametro erros_runtime: injeta erros de execucao reais do Roblox
    no prompt do LLM, para que a correcao seja guiada por falhas reais.
  - Cache invalida quando focus_area muda ou quando ha erros de runtime novos.

Heranca:
  - Boletim de 10 categorias (0 a 10)
  - Visao sob demanda (Qwen2-VL) para mapa/polish baixos
  - Score 0-100 global
"""
import os
import re
import json
import time
from datetime import datetime
import kael_vision

CACHE_TTL_S = 120
SCORE_SAUDAVEL = 80
SCORE_REGRESSAO = 15


class GameCritic:
    def __init__(self, projeto, base_dir, fn_llm,
                 fn_estado_jogo=None, fn_msg=None):
        self.projeto = str(projeto)
        self.base_dir = base_dir
        self.fn_llm = fn_llm
        self.fn_estado_jogo = fn_estado_jogo
        self.fn_msg = fn_msg

        self.dir = os.path.join(base_dir, "Projetos", self._slug(projeto))
        os.makedirs(self.dir, exist_ok=True)

        self.arquivo_ultima = os.path.join(self.dir, "critic_ultima_avaliacao.json")
        self.arquivo_hist = os.path.join(self.dir, "critic_historico_score.json")

        self._cache = {"ts": 0, "score": -1, "resultado": None, "focus_area": None}
        self._ultimo_score = None

    def _slug(self, s):
        s = re.sub(r"[^a-zA-Z0-9_\- ]", "", str(s))
        return s.strip().replace(" ", "_")[:60] or "Jogo"

    def _log(self, m):
        print("[CRITIC] " + str(m))
        if self.fn_msg:
            try:
                self.fn_msg("Sistema", "[Critic] " + str(m))
            except Exception:
                pass

    # ==========================================================
    # 1. SINAIS OBJETIVOS (sem LLM)
    # ==========================================================
    def _sinais_objetivos(self):
        sinais = {
            "tem_spawn": False,
            "tem_terreno": False,
            "objetos_flutuando": 0,
            "objetos_no_chao": 0,
            "total_objetos": 0,
            "scripts_ok": 0,
            "scripts_falhos": 0,
            "scripts_pendentes": 0,
            "blueprint_total": 0,
            "projeto_vazio": True,
        }

        est_path = os.path.join(self.dir, "game_estado.json")
        if os.path.exists(est_path):
            try:
                with open(est_path, "r", encoding="utf-8") as f:
                    ge = json.load(f)
                etapas = ge.get("etapas", [])
                for et in etapas:
                    st = et.get("status", "pendente")
                    if st == "concluida": sinais["scripts_ok"] += 1
                    elif st == "bloqueada": sinais["scripts_falhos"] += 1
                    else: sinais["scripts_pendentes"] += 1
                if etapas: sinais["projeto_vazio"] = False
            except Exception: pass

        bp_path = os.path.join(self.dir, "blueprint.json")
        if os.path.exists(bp_path):
            try:
                with open(bp_path, "r", encoding="utf-8") as f:
                    bp = json.load(f)
                sinais["blueprint_total"] = int(bp.get("total_tarefas", 0))
                if sinais["blueprint_total"] > 0: sinais["projeto_vazio"] = False
            except Exception: pass

        if self.fn_estado_jogo:
            try:
                ej = self.fn_estado_jogo() or {}
                instancias = ej.get("instancias") or ej.get("objetos") or []
                for ob in instancias:
                    if not isinstance(ob, dict): continue
                    sinais["total_objetos"] += 1
                    classe = str(ob.get("classe") or ob.get("class", "")).lower()
                    nome = str(ob.get("nome") or ob.get("name", "")).lower()
                    y = ob.get("y", 0)

                    if "spawn" in classe or "spawn" in nome: sinais["tem_spawn"] = True
                    if "terrain" in classe or "baseplate" in nome or "ground" in nome: sinais["tem_terreno"] = True

                    if isinstance(y, (int, float)):
                        if y > 60: sinais["objetos_flutuando"] += 1
                        else: sinais["objetos_no_chao"] += 1

                if sinais["total_objetos"] > 0: sinais["projeto_vazio"] = False
            except Exception: pass

        return sinais

    # ==========================================================
    # 2. BOLETIM DE NOTAS 0-10 POR CATEGORIA
    # ==========================================================
    def _calcular_notas_categoria(self, sinais, screenshot_b64=None):
        notas = {
            "mapa": 5, "personagem": 5, "economia": 0, "combate": 0,
            "hud": 0, "interacao": 0, "progressao": 0, "polish": 5,
            "performance": 5, "bugs": 5
        }

        # Mapa e Mundo
        if sinais["projeto_vazio"]:
            notas["mapa"] = 0
        else:
            if sinais["tem_spawn"]: notas["mapa"] += 2
            if sinais["tem_terreno"]: notas["mapa"] += 2
            if sinais["total_objetos"] > 50: notas["mapa"] += 1

            if sinais["objetos_flutuando"] > 0:
                notas["mapa"] -= 3
                notas["polish"] -= 2

        # Bugs
        if sinais["scripts_falhos"] > 0:
            notas["bugs"] = 2
        elif sinais["scripts_ok"] > 0:
            notas["bugs"] = 8

        # Performance
        if sinais["scripts_falhos"] > 5:
            notas["performance"] = 3

        # ======================================================
        # VISAO SOB DEMANDA (Qwen2-VL)
        # ======================================================
        if screenshot_b64:
            if notas["mapa"] < 6 or notas["polish"] < 6:
                self._log("Chamando Visao (Qwen2-VL) para avaliar o mapa...")
                pergunta = (
                    "Olhe este screenshot de um jogo Roblox. "
                    "Responda em uma frase: O terreno parece plano? Os objetos (casas, torres) "
                    "parecem estar no chao ou estao flutuando? Ha alguma parte com buraco ou falha visual?"
                )
                analise = kael_vision.analisar_screenshot(screenshot_b64, pergunta)
                self._log("Visao diz: " + analise)

                al = analise.lower()
                if "flutuando" in al or "floating" in al or "buraco" in al or "hole" in al:
                    notas["polish"] = max(0, notas["polish"] - 3)
                    notas["mapa"] = max(0, notas["mapa"] - 2)
                else:
                    notas["polish"] = min(10, notas["polish"] + 2)

        for k in notas:
            notas[k] = max(0, min(10, notas[k]))

        return notas

    # ==========================================================
    # 3. SCORE 0-100 GLOBAL
    # ==========================================================
    def _calcular_score(self, sinais, notas):
        score = sum(notas.values()) * 1.0

        if sinais["tem_spawn"] and sinais["tem_terreno"]:
            score += 5
        if sinais["blueprint_total"] > 0 and sinais["scripts_ok"] > 0:
            proporcao_ok = sinais["scripts_ok"] / sinais["blueprint_total"]
            score += int(10 * proporcao_ok)

        return max(0, min(100, int(score)))

    # ==========================================================
    # 4. COLETA DE CONTEXTO PARA O LLM
    # ==========================================================
    def _coletar_contexto_pra_llm(self, sinais):
        linhas = []
        est_path = os.path.join(self.dir, "game_estado.json")
        if os.path.exists(est_path):
            try:
                with open(est_path, "r", encoding="utf-8") as f:
                    ge = json.load(f)
                bloqueadas = [et for et in ge.get("etapas", []) if et.get("status") == "bloqueada"][:5]
                if bloqueadas:
                    linhas.append("Scripts bloqueados (falharam):")
                    for b in bloqueadas:
                        linhas.append("  - " + str(b.get("titulo", "?"))[:80] + " | erro: " + str(b.get("ultimo_erro", ""))[:100])
                pendentes = [et for et in ge.get("etapas", []) if et.get("status") == "pendente"][:5]
                if pendentes:
                    linhas.append("Scripts pendentes:")
                    for p in pendentes:
                        linhas.append("  - " + str(p.get("titulo", "?"))[:80])
            except Exception: pass

        if self.fn_estado_jogo:
            try:
                ej = self.fn_estado_jogo() or {}
                instancias = ej.get("instancias") or ej.get("objetos") or []
                flut = [(ob.get("nome") or ob.get("name", "?"), ob.get("y", 0)) for ob in instancias if isinstance(ob, dict) and isinstance(ob.get("y"), (int, float)) and ob.get("y", 0) > 60]
                flut.sort(key=lambda x: x[1], reverse=True)
                if flut:
                    linhas.append("Objetos flutuando (top 5):")
                    for nome, y in flut[:5]:
                        linhas.append("  - " + str(nome) + " em Y=" + str(round(y, 1)))
            except Exception: pass

        return "\n".join(linhas) if linhas else "(sem detalhes adicionais)"

    # ==========================================================
    # 5. DIAGNOSTICO LLM (com foco + runtime errors)
    # ==========================================================
    def _diagnostico_llm(self, sinais, notas, score, descricao_usuario,
                          focus_area=None, erros_runtime=None):
        detalhes = self._coletar_contexto_pra_llm(sinais)
        erros_runtime = list(erros_runtime) if erros_runtime else []

        # Categoria alvo: foco forcado tem prioridade
        if focus_area and focus_area in notas:
            pior_cat = focus_area
            nota_pior = notas[focus_area]
            foco_str = (
                f"FOCO ATIVO: o usuario pediu para focar em '{focus_area}' "
                f"(nota atual {nota_pior}/10, meta 8/10).\n"
                f"Proponha acoes que MELHOREM ESSA CATEGORIA. "
                f"Ignore outras categorias por enquanto.\n\n"
            )
        else:
            pior_cat = min(notas, key=notas.get)
            nota_pior = notas[pior_cat]
            foco_str = ""

        # Bloco de erros de runtime
        erros_block = ""
        if erros_runtime:
            erros_block = "\nERROS DE EXECUCAO RECENTES (falhas reais no Roblox):\n"
            for e in erros_runtime[-5:]:
                nome = str(e.get("nome_script", "?"))[:60]
                erro = str(e.get("erro", ""))[:200]
                erros_block += "  - [" + nome + "] " + erro + "\n"
            erros_block += (
                "\nIMPORTANTE: se um script existente esta falhando, "
                "sugira CORRIGIR esse script especifico. Nao repita o mesmo erro.\n\n"
            )

        if sinais["projeto_vazio"]:
            prompt = (
                "Voce e o CRITICO do KAEL, arquiteto autonomo de jogos Roblox.\n\n"
                "ESTADO: o projeto '" + self.projeto + "' esta VAZIO (nada construido).\n"
                "DESCRICAO DO JOGO: " + (descricao_usuario or "(nao informada)") + "\n\n"
                + foco_str +
                "TAREFA: Qual o PRIMEIRO passo concreto para comecar este jogo?\n"
                "Responda APENAS em JSON:\n"
                "{\n"
                '  "problemas": [\n'
                '    {"prioridade": 1, "problema": "projeto vazio, nada construido",\n'
                '     "acao": "construir estrutura basica do jogo",\n'
                '     "onde": "pipeline_completo", "impacto": "alto"}\n'
                "  ],\n"
                '  "resumo": "projeto comecando do zero"\n'
                "}\n"
            )
        else:
            prompt = (
                "Voce e o CRITICO do KAEL, engenheiro de jogos Roblox.\n"
                "Sua funcao e OLHAR o estado atual e dizer o QUE FALTA.\n\n"
                "DESCRICAO DO JOGO: " + (descricao_usuario or "(nao informada)") + "\n\n"
                + foco_str +
                "NOTAS DO BOLETIM (0 a 10):\n" + json.dumps(notas, indent=2, ensure_ascii=False) + "\n\n"
                "A PIOR CATEGORIA AGORA E: '" + pior_cat + "' com nota " + str(nota_pior) + "/10.\n"
                "SINAIS OBJETIVOS:\n" + json.dumps(sinais, indent=2, ensure_ascii=False) + "\n\n"
                "DETALHES:\n" + detalhes + "\n"
                + erros_block +
                "TAREFA:\n"
                "Liste NO MAXIMO 3 problemas concretos para MELHORAR A CATEGORIA '" + pior_cat + "'.\n"
                "Cada problema deve ter uma ACAO DIRETA (verbo no imperativo).\n"
                "Se um problema for 'script quebrado', sugira CORRIGIR o script especifico.\n\n"
                "Responda APENAS em JSON:\n"
                "{\n"
                '  "problemas": [\n'
                '    {"prioridade": 1, "problema": "descricao curta",\n'
                '     "acao": "verbo + o que fazer", "onde": "ServerScriptService",\n'
                '     "impacto": "alto|medio|baixo"}\n'
                "  ],\n"
                '  "resumo": "1 frase sobre o estado geral"\n'
                "}\n"
                "Responda em portugues."
            )

        try:
            resp = str(self.fn_llm(prompt, temperatura=0.3))
        except Exception as e:
            self._log("erro LLM diagnostico: " + str(e)[:150])
            return {"problemas": [], "resumo": "LLM falhou"}

        m = re.search(r"\{[\s\S]*\}", resp)
        if not m:
            return {"problemas": [], "resumo": "resposta sem JSON"}

        try:
            dados = json.loads(m.group(0))
        except Exception:
            return {"problemas": [], "resumo": "JSON invalido"}

        validos = []
        for p in dados.get("problemas", [])[:3]:
            if not isinstance(p, dict): continue
            acao = str(p.get("acao", "")).strip()
            problema = str(p.get("problema", "")).strip()
            if acao and problema:
                validos.append({
                    "prioridade": int(p.get("prioridade", 99)),
                    "problema": problema[:200],
                    "acao": acao[:200],
                    "onde": str(p.get("onde", "ServerScriptService"))[:100],
                    "impacto": str(p.get("impacto", "medio"))[:20],
                })

        validos.sort(key=lambda x: x["prioridade"])
        return {
            "problemas": validos,
            "resumo": str(dados.get("resumo", ""))[:200],
        }

    # ==========================================================
    # 6. PERSISTENCIA
    # ==========================================================
    def _salvar_historico(self, score):
        try:
            hist = []
            if os.path.exists(self.arquivo_hist):
                with open(self.arquivo_hist, "r", encoding="utf-8") as f:
                    hist = json.load(f)
                if not isinstance(hist, list): hist = []
            hist.append({"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "score": score})
            with open(self.arquivo_hist, "w", encoding="utf-8") as f:
                json.dump(hist[-100:], f, ensure_ascii=False, indent=2)
        except Exception: pass

    def _salvar_ultima(self, resultado):
        try:
            with open(self.arquivo_ultima, "w", encoding="utf-8") as f:
                json.dump(resultado, f, ensure_ascii=False, indent=2)
        except Exception: pass

    # ==========================================================
    # 7. API PUBLICA
    # ==========================================================
    def avaliar(self, descricao_usuario="", force=False, screenshot_b64=None,
                focus_area=None, erros_runtime=None):
        agora = time.time()
        sinais = self._sinais_objetivos()

        notas = self._calcular_notas_categoria(sinais, screenshot_b64)
        score = self._calcular_score(sinais, notas)

        erros_runtime = list(erros_runtime) if erros_runtime else []

        # Cache: invalida se focus_area mudou OU se ha erros de runtime novos
        cache_valido = (
            not force
            and not erros_runtime
            and self._cache["resultado"]
            and self._cache["score"] == score
            and self._cache.get("focus_area") == focus_area
            and (agora - self._cache["ts"]) < CACHE_TTL_S
        )
        if cache_valido:
            return self._cache["resultado"]

        diag = self._diagnostico_llm(
            sinais, notas, score, descricao_usuario,
            focus_area=focus_area,
            erros_runtime=erros_runtime,
        )

        resultado = {
            "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "score": score,
            "score_anterior": self._ultimo_score,
            "notas": notas,
            "sinais": sinais,
            "problemas": diag.get("problemas", []),
            "resumo": diag.get("resumo", ""),
            "focus_area": focus_area,
            "foco_nota": notas.get(focus_area) if focus_area else None,
            "erros_runtime_count": len(erros_runtime),
        }

        self._ultimo_score = score
        self._cache = {
            "ts": agora, "score": score,
            "focus_area": focus_area, "resultado": resultado,
        }
        self._salvar_historico(score)
        self._salvar_ultima(resultado)

        delta_str = ""
        if resultado["score_anterior"] is not None:
            d = score - resultado["score_anterior"]
            delta_str = " (" + ("+" if d >= 0 else "") + str(d) + ")"

        self._log("score: " + str(score) + "/100" + delta_str + " — " + str(resultado["resumo"]))

        if focus_area:
            self._log("  [FOCO] " + focus_area + " = " + str(notas.get(focus_area, 0)) + "/10 (meta 8)")

        for cat, val in notas.items():
            self._log("  [" + cat.upper() + "] " + str(val) + "/10")

        if erros_runtime:
            self._log("  [!] " + str(len(erros_runtime)) + " erro(s) de runtime considerados na analise")

        for p in resultado["problemas"]:
            self._log("  -> [" + p.get("impacto", "?") + "] " + p.get("acao", "?")[:80])

        return resultado
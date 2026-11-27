# -*- coding: utf-8 -*-
"""
game_manager.py - Kael Game Manager v4 (Dual: Correcao + Expansao)
====================================================================
Loop:
  1. Critic avalia -> score + problemas
  2. Se projeto vazio     -> bootstrap (pipeline completo)
  3. Se score < 80        -> FASE CORRECAO (corrige problema #1)
  4. Se score >= 80       -> FASE EXPANSAO (DiretorCriativo propoe ideias)
  5. Volta ao passo 1

Alterna automaticamente. Nao tem checklist. Nao le .md.
"""
import os
import re
import time
import threading
import concurrent.futures

from game_critic import GameCritic
from kael_creative import DiretorCriativo

TIMEOUT_CONSTRUCAO_PADRAO = 1800
SCORE_SAUDAVEL = 80
INTERVALO_SAUDAVEL = 60
INTERVALO_APOS_ACAO = 10
INTERVALO_APOS_EXPANSAO = 15
MAX_CICLOS_SAUDAVEIS = 5


class GameManager:
    def __init__(self, projeto, base_dir, fn_construir, fn_integrar, fn_msg,
                 fn_llm=None, fn_estado_jogo=None, fn_corrigir=None,
                 fn_criar_asset=None,
                 descricao="", genero_hint="",
                 timeout_construcao=TIMEOUT_CONSTRUCAO_PADRAO):
        self.projeto = projeto
        self.base_dir = base_dir
        self.fn_construir = fn_construir
        self.fn_integrar = fn_integrar
        self.fn_msg = fn_msg
        self.fn_llm = fn_llm
        self.fn_estado_jogo = fn_estado_jogo
        self.fn_corrigir = fn_corrigir
        self.fn_criar_asset = fn_criar_asset
        self.timeout_construcao = timeout_construcao

        self.rodando = False

        self.dir = os.path.join(base_dir, "Projetos", self._slug(projeto))
        os.makedirs(self.dir, exist_ok=True)

        self.f_lore = os.path.join(self.dir, "1_LORE.md")
        self.f_obj = os.path.join(self.dir, "2_OBJETIVOS.md")
        self.f_done = os.path.join(self.dir, "3_CONCLUIDOS.md")
        self.f_log = os.path.join(self.dir, "4_DIARIO.md")

        self._criar_templates()

        if descricao:
            self.descricao = descricao
        else:
            self.descricao = self._ler_lore()

        self.lore = self._ler_lore()
        self.genero_hint = genero_hint
        self._iteracao = 0
        self._ciclos_saudaveis = 0

    def _slug(self, s):
        return re.sub(r"[^a-zA-Z0-9_\- ]", "", str(s)).strip().replace(" ", "_")[:60] or "Jogo"

    def _msg(self, m):
        print("[MANAGER] " + m)
        if self.fn_msg:
            try:
                self.fn_msg("Sistema", "[Manager] " + m)
            except Exception:
                pass

    def _criar_templates(self):
        if not os.path.exists(self.f_lore):
            with open(self.f_lore, "w", encoding="utf-8") as f:
                f.write("# Lore do Mundo\n\nEscreva a historia aqui.\n")
        if not os.path.exists(self.f_obj):
            with open(self.f_obj, "w", encoding="utf-8") as f:
                f.write("# Objetivos (opcional — Kael decide sozinho)\n\n"
                        "Os itens abaixo sao apenas anotacoes. O Kael usa o Critic\n"
                        "e o Diretor Criativo para decidir, nao este arquivo.\n")
        if not os.path.exists(self.f_done):
            with open(self.f_done, "w", encoding="utf-8") as f:
                f.write("# Concluidos\n\n")

    def _ler_lore(self, limite=2000):
        try:
            if os.path.exists(self.f_lore):
                with open(self.f_lore, "r", encoding="utf-8") as f:
                    return f.read()[:limite]
        except Exception:
            pass
        return ""

    # ==========================================================
    # EXECUCAO COM TIMEOUT
    # ==========================================================
    def _executar_com_timeout(self, fn, args, timeout=None):
        if fn is None:
            self._msg("ERRO: funcao nao injetada.")
            return False
        timeout = timeout or self.timeout_construcao
        ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(fn, *args)
        try:
            return fut.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            self._msg("TIMEOUT de " + str(timeout) + "s. Abortando.")
            return False
        except Exception as e:
            self._msg("Excecao em execucao: " + str(e)[:200])
            return False
        finally:
            ex.shutdown(wait=False)

    # ==========================================================
    # BOOTSTRAP
    # ==========================================================
    def _bootstrap(self):
        self._msg("Bootstrap: construindo estrutura basica...")
        return self._executar_com_timeout(
            self.fn_construir,
            ("rpg", self.projeto, self.descricao, self.lore),
        )

    # ==========================================================
    # FASE CORRECAO (score < 80)
    # ==========================================================
    def _fase_correcao(self, problema):
        tipo = str(problema.get("tipo", "script")).lower()
        acao = str(problema.get("acao", ""))
        onde = str(problema.get("onde", "ServerScriptService"))

        if not acao:
            self._msg("Problema sem acao, ignorando.")
            return False

        self._msg("Correcao [" + tipo + "]: " + problema.get("problema", "?")[:80])
        self._msg("  Acao: " + acao[:80])

        # Tipos especiais: delega para fn_corrigir com dict COMPLETO
        # (kael_core decide como tratar cada tipo)
        if self.fn_corrigir:
            return self._executar_com_timeout(
                self.fn_corrigir,
                (problema, self.projeto),
                timeout=300,
            )

        # Fallback: usa fn_construir com a acao como descricao
        self._msg("fn_corrigir nao injetada, usando fn_construir como fallback.")
        return self._executar_com_timeout(
            self.fn_construir,
            ("rpg", self.projeto, acao, self.lore),
        )

    # ==========================================================
    # FASE EXPANSAO (score >= 80)
    # ==========================================================
    def _fase_expansao(self):
        if self.fn_criar_asset is None:
            self._msg("fn_criar_asset nao injetada. Pulando expansao.")
            return False

        self._msg("Entrando em modo EXPANSAO (propondo features novas)...")

        try:
            criativo = DiretorCriativo(
                projeto=self.projeto,
                base_dir=self.base_dir,
                fn_llm=self.fn_llm,
                fn_msg=self.fn_msg,
                genero_hint=self.genero_hint,
                descricao_usuario=self.descricao,
            )
            criativo.inicializar()
            ideias = criativo.propor_ideias(n=3)
        except Exception as e:
            self._msg("DiretorCriativo falhou: " + str(e)[:150])
            return False

        if not ideias:
            self._msg("Nenhuma ideia valida proposta. Dormindo.")
            return False

        # Constroi apenas a PRIMEIRA ideia por ciclo
        # (as outras ficam salvas em ideias_criativas.json para proximos ciclos)
        ideia = ideias[0]
        self._msg("Construindo: [" + ideia.get("categoria", "?") + "] "
                  + ideia.get("titulo", "?")[:80])
        self._msg("  Descricao: " + ideia.get("descricao", "?")[:120])

        sucesso = self._executar_com_timeout(
            self.fn_criar_asset,
            (ideia, self.projeto),
            timeout=300,
        )
        self._msg("  Resultado: " + ("OK" if sucesso else "FALHOU"))

        if sucesso:
            self._ciclos_saudaveis = 0
        return sucesso

    # ==========================================================
    # LOOP PRINCIPAL
    # ==========================================================
    def _loop(self):
        if self.fn_llm is None:
            self._msg("ERRO: fn_llm nao injetada. Manager nao pode rodar.")
            self.rodando = False
            return

        critic = GameCritic(
            projeto=self.projeto,
            base_dir=self.base_dir,
            fn_llm=self.fn_llm,
            fn_estado_jogo=self.fn_estado_jogo,
            fn_msg=self.fn_msg,
        )

        self._msg("Gerenciador DUAL iniciado (correcao + expansao).")
        self._msg("Projeto: " + self.projeto)
        time.sleep(2)

        while self.rodando:
            self._iteracao += 1
            self._msg("--- Iteracao " + str(self._iteracao) + " ---")

            # ---------- 1. AVALIAR ----------
            try:
                aval = critic.avaliar(
                    descricao_usuario=self.descricao,
                    force=(self._iteracao == 1),
                )
            except Exception as e:
                self._msg("Critic falhou: " + str(e)[:150])
                time.sleep(30)
                continue

            score = aval.get("score", 0)
            problemas = aval.get("problemas", [])
            projeto_vazio = aval.get("sinais", {}).get("projeto_vazio", False)

            # ---------- 2. BOOTSTRAP ----------
            if projeto_vazio:
                self._msg("Projeto vazio. Bootstrap.")
                ok = self._bootstrap()
                self._msg("  Bootstrap: " + ("OK" if ok else "FALHOU"))
                time.sleep(INTERVALO_APOS_ACAO)
                continue

            # ---------- 3. CORRECAO ----------
            if problemas:
                p = problemas[0]
                self._msg("Score " + str(score) + "/100 com "
                          + str(len(problemas)) + " problema(s). Corrigindo #1.")
                ok = self._fase_correcao(p)
                self._msg("  Resultado: " + ("OK" if ok else "FALHOU"))
                self._ciclos_saudaveis = 0
                time.sleep(INTERVALO_APOS_ACAO)
                continue

            # ---------- 4. EXPANSAO ----------
            if score >= SCORE_SAUDAVEL:
                self._ciclos_saudaveis += 1
                self._msg("Score " + str(score) + "/100 saudavel. "
                          "Ciclo saudavel #" + str(self._ciclos_saudaveis))

                if self._ciclos_saudaveis <= MAX_CICLOS_SAUDAVEIS:
                    ok = self._fase_expansao()
                    if ok:
                        time.sleep(INTERVALO_APOS_EXPANSAO)
                    else:
                        time.sleep(INTERVALO_SAUDAVEL)
                else:
                    self._msg("Maximo de ciclos saudaveis atingido "
                              "(" + str(MAX_CICLOS_SAUDAVEIS) + "). Dormindo "
                              + str(INTERVALO_SAUDAVEL) + "s.")
                    time.sleep(INTERVALO_SAUDAVEL)
                continue

            # ---------- 5. SEM PROBLEMAS MAS SCORE BAIXO ----------
            self._msg("Score " + str(score) + "/100 sem problemas listados. "
                      "Aguardando " + str(INTERVALO_SAUDAVEL) + "s.")
            time.sleep(INTERVALO_SAUDAVEL)

        self._msg("Gerenciador encerrado.")

    def iniciar(self):
        if self.rodando:
            return
        self.rodando = True
        threading.Thread(target=self._loop, daemon=True).start()

    def parar(self):
        self.rodando = False
        self._msg("Gerenciador parado.")

    def status(self):
        return {
            "ativo": self.rodando,
            "projeto": self.projeto,
            "iteracao": self._iteracao,
            "ciclos_saudaveis": self._ciclos_saudaveis,
        }
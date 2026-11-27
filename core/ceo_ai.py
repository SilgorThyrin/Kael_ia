"""Orquestrador Local (Ollama leve) que coordena o Especialista (Gemini) e guarda o cofre."""
import json
import os
import re
import smtplib
import time
from email.message import EmailMessage
from ai.ollama_client import generate_response
from core.external_apis import GoogleManagerClient


def sanitizar_para_nuvem(texto: str) -> str:
    """Remove chaves, senhas e tokens antes de qualquer envio ao Gemini."""
    regras = [
        (r"(GEMINI_API_KEY|PASSWORD|PASS|SENHA|SECRET|TOKEN|API_KEY)\s*=\s*[\x22\x27]?[^\s\x22\x27]+[\x22\x27]?", r"\1=[REDACTED_LOCAL]"),
        (r"AIza[0-9A-Za-z\-_]{20,60}", "[REDACTED_API_KEY]"),
    ]
    limpo = texto
    for padrao, substituto in regras:
        limpo = re.sub(padrao, substituto, limpo, flags=re.IGNORECASE)
    return limpo


def enviar_email_cofre_local(conta_alias: str, destinatario: str, assunto: str, corpo: str) -> dict:
    """Envia e-mail usando credenciais do .env sem expor a senha para nenhuma IA."""
    prefixo = conta_alias.upper().strip()
    usuario = os.environ.get(f"SMTP_{prefixo}_USER")
    senha = os.environ.get(f"SMTP_{prefixo}_PASS")
    host = os.environ.get(f"SMTP_{prefixo}_HOST", "smtp.gmail.com")
    porta = int(os.environ.get(f"SMTP_{prefixo}_PORT", "465"))

    if not usuario or not senha:
        return {"sucesso": False, "erro": f"Credencial '{prefixo}' não encontrada no .env local."}

    msg = EmailMessage()
    msg["From"] = usuario
    msg["To"] = destinatario
    msg["Subject"] = assunto
    msg.set_content(corpo)

    with smtplib.SMTP_SSL(host, porta, timeout=15) as smtp:
        smtp.login(usuario, senha)
        smtp.send_message(msg)

    return {"sucesso": True, "enviado_por": usuario, "para": destinatario}


class CEOOrchestrator:
    def __init__(self, local_model: str = "qwen2.5:1.5b", google_model: str = "gemini-3.5-flash-lite"):
        self.local_model = local_model
        self.manager = GoogleManagerClient(model=google_model)
        self.last_report: dict | None = None
        self.history: list[dict] = []
        self.plugin_manager = None

    def _proteger_texto(self, texto: str) -> str:
        limpo = sanitizar_para_nuvem(texto)
        if self.plugin_manager:
            limpo = self.plugin_manager.run_hooks("pre_cloud", {"texto": limpo}).get("texto", limpo)
        return limpo

    def _decidir_rota(self, prompt: str, has_attachments: bool = False) -> str:
        """Decide se a mensagem fica no Ollama local ou vai para o Gemini com ferramentas."""
        if not self.manager.is_configured:
            return "LOCAL"
        if has_attachments:
            return "NUVEM"

        p = prompt.lower().strip()
        gatilhos_nuvem = (
            "código", "codigo", "script", "python", "luau", "js", "html", "css", "sql",
            "bug", "erro", "corrig", "cria", "criar", "gera", "faz", "fazer", "implementa",
            "arquivo", "pasta", "git", "plugin", "jogo", "roblox", "godot", "gdd",
            "ram", "memória", "memoria", "disco", "porta", "servidor", "ollama", "termux",
            "linux", "android", "rede", "ti", "diagnóstico", "diagnostico", "verifica",
            "olha", "analisa", "tarefa", "lista", "anota", "lembra", "pesquisa", "busca", "buscar", "procura", "procurar", "internet", "web", "bing", "site", "notícia", "noticia", "preço", "preco", "instala",
        )
        if any(g in p for g in gatilhos_nuvem) or len(p.split()) > 12:
            return "NUVEM"

        try:
            triagem = generate_response(
                prompt=prompt,
                system_prompt=(
                    "Classifique a mensagem do usuário em APENAS UMA palavra: "
                    "'LOCAL' (somente saudação curta, agradecimento ou papo casual sem tarefa) "
                    "ou 'NUVEM' (qualquer pergunta real, dúvida técnica, pedido de código, TI, jogo ou ação)."
                ),
                think=False,
                settings={"model": self.local_model, "temperature": 0.0, "max_tokens": 10, "think": False},
            )
            resp = triagem.get("response", "").strip().upper()
            if "LOCAL" in resp and "NUVEM" not in resp:
                return "LOCAL"
        except Exception:
            pass
        return "NUVEM"

    def responder_conversa_natural(
        self,
        prompt: str,
        system_prompt: str = "",
        history: list[dict] | None = None,
        contexto_extra: str = "",
        has_attachments: bool = False,
    ) -> dict:
        """Conversa natural unificada: triagem local + execução com ferramentas sanitizada."""
        rota = self._decidir_rota(prompt, has_attachments=has_attachments)

        if rota == "LOCAL":
            try:
                sys_local = (
                    "Você é o Kael, um assistente pessoal e técnico amigável, direto e natural em português. "
                    "Responda de forma fluida sem mencionar JSON, comandos ou arquitetura interna."
                )
                if system_prompt:
                    sys_local = f"{sys_local}\n\n{system_prompt}"
                live_thk = []
                def _on_local_chunk(kind, piece):
                    if kind == "thinking":
                        live_thk.append(piece)

                res = generate_response(
                    prompt=f"{contexto_extra}\n\n{prompt}".strip() if contexto_extra else prompt,
                    system_prompt=sys_local,
                    history=history,
                    think=True,
                    settings={"model": self.local_model, "temperature": 0.5, "max_tokens": 600, "think": True},
                    on_chunk=_on_local_chunk,
                )
                if not res.get("error") and res.get("response"):
                    thk_txt = (res.get("thinking") or "".join(live_thk) or f"Respondido localmente ({self.local_model}).").strip()
                    return {
                        "response": res["response"].strip(),
                        "thinking": thk_txt,
                        "status": "success",
                    }
            except Exception:
                if not self.manager.is_configured:
                    raise

        hist_limpo = [
            {"role": m.get("role", "user"), "content": self._proteger_texto(str(m.get("content", "")))}
            for m in (history or [])[-10:]
        ]
        res_nuvem = self.manager.conversar_com_ferramentas(
            mensagem=self._proteger_texto(prompt),
            system_prompt=self._proteger_texto(system_prompt) if system_prompt else "",
            history=hist_limpo,
            contexto_extra=self._proteger_texto(contexto_extra) if contexto_extra else "",
        )
        ferramentas = res_nuvem.get("tools_used") or []
        thinking = ""
        if ferramentas:
            pass
        return {
            "response": res_nuvem["response"],
            "thinking": thinking,
            "status": "success",
        }

    def analyze_request(self, prompt: str) -> dict:
        """Compatibilidade com /estratégia em core/ceo_commands.py."""
        sys_prompt = (
            "Você é o Orquestrador Local do Kael (código, TI, jogos e tarefas). "
            "Analise a solicitação e responda APENAS em JSON válido com: "
            "'task_type', 'priority' (alta/média/baixa), 'delegation' (lista) e 'reasoning'."
        )
        res = generate_response(
            prompt,
            system_prompt=sys_prompt,
            think=False,
            settings={"model": self.local_model, "temperature": 0.2, "max_tokens": 300, "think": False},
        )
        try:
            text = res["response"].strip().removeprefix("```json").removesuffix("```").strip()
            return json.loads(text)
        except Exception:
            return {
                "task_type": "multifuncao",
                "priority": "alta",
                "delegation": ["Kael Executor (Gemini)"],
                "reasoning": res.get("response", "Análise concluída."),
            }

    def gerar_ordem_local(self, contexto_empresa: str) -> str:
        """O Orquestrador local analisa o contexto e formula 1 diretriz para o Executor."""
        sys_prompt = (
            "Você é o Orquestrador Local de um sistema multifunções (código, TI, criação de jogos e tarefas). "
            "Leia o contexto e escreva APENAS UMA diretriz direta e curta (máximo 2 frases) para o "
            "Executor agir agora. Se realmente não houver nada a fazer, responda exatamente: AGUARDAR."
        )
        res = generate_response(
            prompt=f"Contexto atual:\n{contexto_empresa}",
            system_prompt=sys_prompt,
            think=False,
            settings={"model": self.local_model, "temperature": 0.2, "max_tokens": 200, "think": False},
        )
        if res.get("error"):
            raise RuntimeError(res["error"])
        return res["response"].strip()

    def auditar_relatorio(self, ordem: str, relatorio: dict) -> str:
        """O Orquestrador local valida em 1 frase a entrega do Executor."""
        sys_prompt = "Você é o Orquestrador Local validando uma tarefa técnica. Responda em 1 frase curta se foi cumprida."
        prompt = (
            f"Tarefa: {ordem}\n"
            f"Entrega: {relatorio.get('resumo_executivo')}\n"
            f"Próximo passo: {relatorio.get('proxima_diretriz_sugerida')}"
        )
        res = generate_response(
            prompt=prompt,
            system_prompt=sys_prompt,
            think=False,
            settings={"model": self.local_model, "temperature": 0.1, "max_tokens": 150, "think": False},
        )
        return res.get("response", "Validação registrada.").strip()

    def executar_ciclo_gerencial(self, contexto_empresa: str, ordem_forcada: str | None = None) -> dict:
        """Ordem Local -> Execução Gemini (sanitizada) -> Auditoria Local."""
        contexto_limpo = self._proteger_texto(contexto_empresa)
        ordem = ordem_forcada.strip() if ordem_forcada else self.gerar_ordem_local(contexto_limpo)

        if ordem.upper() == "AGUARDAR":
            return {"status": "idle", "ordem_ceo": "AGUARDAR", "mensagem": "Orquestrador decidiu aguardar."}

        relatorio = self.manager.executar_ordem(ordem_ceo=sanitizar_para_nuvem(ordem), contexto_empresa=contexto_limpo)
        parecer_ceo = self.auditar_relatorio(ordem, relatorio)

        registro = {
            "timestamp": time.time(),
            "ordem_ceo": ordem,
            "relatorio_gerente": relatorio,
            "parecer_ceo": parecer_ceo,
        }
        self.last_report = registro
        self.history.append(registro)
        self.history = self.history[-20:]
        return {"status": "executed", **registro}


def create_ceo(model: str = "qwen2.5:1.5b", google_model: str = "gemini-3.5-flash-lite") -> CEOOrchestrator:
    return CEOOrchestrator(local_model=model, google_model=google_model)

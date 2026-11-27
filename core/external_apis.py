"""Executor Multifunções via API REST do Google Gemini (leve para Termux 4GB RAM)."""
import json
import os
import time
from pathlib import Path
from typing import Any, Callable
import requests

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
TASKS_FILE = Path.home() / "Kael_ia" / "data" / "tarefas.json"

RELATORIO_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "ordem_recebida": {"type": "STRING"},
        "acoes_executadas": {"type": "ARRAY", "items": {"type": "STRING"}},
        "resumo_executivo": {"type": "STRING"},
        "requer_aprovacao_diretoria": {"type": "BOOLEAN"},
        "acao_critica_proposta": {"type": "STRING"},
        "proxima_diretriz_sugerida": {"type": "STRING"},
    },
    "required": [
        "ordem_recebida",
        "acoes_executadas",
        "resumo_executivo",
        "requer_aprovacao_diretoria",
        "proxima_diretriz_sugerida",
    ],
}


class GoogleManagerClient:
    """Agente Executor Multifunções (Gemini) via HTTP puro."""

    def __init__(self, model: str = "gemini-3.5-flash-lite", api_key: str | None = None):
        self.model = model
        self.api_key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        self._tool_map: dict[str, Callable] = {}
        self._tool_declarations: list[dict] = []

        self.register_tool(
            self.registrar_tarefa,
            {
                "name": "registrar_tarefa",
                "description": "Salva ou atualiza uma tarefa prática no painel local do Kael (código, TI, jogo ou geral).",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "titulo": {"type": "STRING"},
                        "categoria": {"type": "STRING", "description": "codigo, ti, jogo ou geral"},
                        "prioridade": {"type": "STRING", "description": "alta, media ou baixa"},
                    },
                    "required": ["titulo", "categoria", "prioridade"],
                },
            },
        )
        self.register_tool(
            self.listar_tarefas,
            {
                "name": "listar_tarefas",
                "description": "Lista as tarefas atualmente registradas no arquivo local do Kael.",
                "parameters": {"type": "OBJECT", "properties": {}},
            },
        )

    @property
    def is_configured(self) -> bool:
        if not self.api_key:
            self.api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        return bool(self.api_key)

    def register_tool(self, func: Callable, declaration: dict):
        """Registra ou atualiza ferramenta pelo nome, evitando duplicatas no /plugin reload."""
        nome = declaration["name"]
        self._tool_map[nome] = func
        self._tool_declarations = [d for d in self._tool_declarations if d.get("name") != nome]
        self._tool_declarations.append(declaration)

    @staticmethod
    def registrar_tarefa(titulo: str, categoria: str, prioridade: str) -> dict:
        TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tarefas = []
        if TASKS_FILE.is_file():
            try:
                tarefas = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
            except Exception:
                tarefas = []
        nova = {
            "id": len(tarefas) + 1,
            "titulo": titulo,
            "categoria": categoria,
            "prioridade": prioridade,
            "status": "pendente",
            "criada_em": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        tarefas.append(nova)
        TASKS_FILE.write_text(json.dumps(tarefas, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"status": "salva", "tarefa": nova}

    @staticmethod
    def listar_tarefas() -> dict:
        if not TASKS_FILE.is_file():
            return {"total": 0, "tarefas": []}
        try:
            tarefas = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
        except Exception:
            tarefas = []
        return {"total": len(tarefas), "tarefas": tarefas[-20:]}

    def _post_gemini(self, payload: dict) -> tuple[dict, str]:
        headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}
        fila = [self.model] + [
            m for m in (
                "gemini-3.1-flash-lite",
                "gemini-3.7-flash",
                "gemini-3.8-flash",
                "gemini-4-hydrogen",
                "gemini-3.5-flash",
            ) if m != self.model
        ]
        resp = None
        modelo_usado = self.model
        last_err = None

        for idx, modelo in enumerate(fila):
            if idx > 0:
                time.sleep(min(2 * idx, 8))
            url = f"{GEMINI_BASE_URL}/{modelo}:generateContent"
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=(10, 60))
                if resp.status_code not in (404, 429, 503):
                    modelo_usado = modelo
                    break
                last_err = f"HTTP {resp.status_code}"
            except requests.RequestException as exc:
                last_err = str(exc)
                resp = None

        if resp is None:
            raise RuntimeError(f"Falha ao contatar API Gemini: {last_err}")
        if not resp.ok:
            raise RuntimeError(f"HTTP {resp.status_code} ({resp.url}): {resp.text[:500]}")
        return resp.json(), modelo_usado

    def _executar_tools(self, func_calls: list[dict], tools_used: list[str]) -> list[dict]:
        tool_responses = []
        for call in func_calls:
            nome = call["name"]
            args = call.get("args", {})
            fn = self._tool_map.get(nome)
            try:
                resultado = fn(**args) if fn else {"erro": f"Ferramenta '{nome}' desconhecida."}
            except Exception as exc:
                resultado = {"erro": f"Falha ao executar {nome}: {exc}"}
            tools_used.append(nome)
            tool_responses.append({
                "functionResponse": {
                    "name": nome,
                    "response": {"result": resultado},
                }
            })
        return tool_responses

    def executar_ordem(self, ordem_ceo: str, contexto_empresa: str = "") -> dict:
        if not self.is_configured:
            raise RuntimeError("GEMINI_API_KEY não configurada no .env.")

        system_instruction = (
            "Você é o Kael Executor (Especialista Multifunções), trabalhando em conjunto com o "
            "Orquestrador Local (Ollama). Você domina Engenharia de Software (Python, Luau, JS, Shell), "
            "Suporte Técnico de TI (Linux/Termux, rede, memória, serviços), Criação de Jogos "
            "(Roblox Studio, Godot, GDD, mecânicas) e Execução de Tarefas.\n"
            "Use suas ferramentas reais sempre que precisar inspecionar arquivos, rodar diagnósticos ou "
            "acionar comandos do Kael. Entregue a resposta completa e prática dentro de `resumo_executivo`. "
            "Para qualquer ação destrutiva, exclusão em massa, envio externo ou pagamento, NÃO execute: "
            "marque `requer_aprovacao_diretoria=true` e descreva em `acao_critica_proposta`."
        )

        contents: list[dict[str, Any]] = [
            {
                "role": "user",
                "parts": [{
                    "text": f"=== CONTEXTO ===\n{contexto_empresa or 'Sem contexto adicional.'}\n\n=== TAREFA ===\n{ordem_ceo}"
                }],
            }
        ]

        tools_used: list[str] = []
        for _ in range(8):
            payload = {
                "system_instruction": {"parts": [{"text": system_instruction}]},
                "contents": contents,
                "tools": [{"function_declarations": self._tool_declarations}],
                "generationConfig": {
                    "temperature": 0.25,
                    "response_mime_type": "application/json",
                    "response_schema": RELATORIO_SCHEMA,
                },
            }

            data, _ = self._post_gemini(payload)
            candidate_content = data["candidates"][0]["content"]
            parts = candidate_content.get("parts", [])

            func_calls = [p["functionCall"] for p in parts if "functionCall" in p]
            if not func_calls:
                texto_final = "".join(p.get("text", "") for p in parts).strip()
                return json.loads(texto_final)

            contents.append(candidate_content)
            contents.append({"role": "user", "parts": self._executar_tools(func_calls, tools_used)})

        raise RuntimeError("Limite de chamadas de ferramentas excedido pelo Executor.")

    def conversar_com_ferramentas(
        self,
        mensagem: str,
        system_prompt: str = "",
        history: list[dict] | None = None,
        contexto_extra: str = "",
    ) -> dict:
        """Conversa natural em português com acesso às ferramentas reais, sem forçar JSON."""
        if not self.is_configured:
            raise RuntimeError("GEMINI_API_KEY não configurada no .env.")

        instrucao_base = (
            "Você é o Kael, um assistente pessoal e técnico multifunções em português do Brasil.\n"
            "Você conversa naturalmente como um parceiro técnico direto e capaz — sem jargões "
            "corporativos nem exigir comandos com barra do usuário.\n"
            "Domínios: programação (Python, Luau, JS, Shell), técnico de TI (Linux/Termux, rede, "
            "hardware, serviços), criação de jogos (Roblox Studio, Godot, mecânicas, GDD) e tarefas práticas.\n"
            "NUNCA escreva 'Ferramentas usadas' ou invente um ID de ação sem ter chamado a ferramenta real antes. "
            "Sempre que precisar olhar o sistema, ler código do projeto, checar o Git, rodar comandos "
            "do Kael ou salvar tarefas, use suas ferramentas reais antes de responder. "
            "Se o usuário pedir código, entregue o código completo e funcional em Markdown. "
            "Nunca peça confirmação por texto no chat (como \"deseja que eu execute?\", \"responda sim\" ou \"confirme\"). Aprovações ocorrem exclusivamente pelo pop-up de permissão."
        )
        if system_prompt:
            instrucao_base = f"{instrucao_base}\n\n{system_prompt}"

        contents: list[dict[str, Any]] = []
        for msg in (history or [])[-10:]:
            txt = str(msg.get("content", "")).strip()
            if not txt:
                continue
            role = "model" if msg.get("role") == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": txt}]})

        texto_usuario = f"{contexto_extra}\n\n{mensagem}".strip() if contexto_extra else mensagem
        contents.append({"role": "user", "parts": [{"text": texto_usuario}]})

        tools_used: list[str] = []
        modelo_usado = self.model
        for _ in range(8):
            payload = {
                "system_instruction": {"parts": [{"text": instrucao_base}]},
                "contents": contents,
                "tools": [{"function_declarations": self._tool_declarations}],
                "generationConfig": {"temperature": 0.25},
            }

            data, modelo_usado = self._post_gemini(payload)
            candidate_content = data["candidates"][0]["content"]
            parts = candidate_content.get("parts", [])

            func_calls = [p["functionCall"] for p in parts if "functionCall" in p]
            if not func_calls:
                texto_final = "".join(p.get("text", "") for p in parts).strip()
                return {
                    "response": texto_final,
                    "tools_used": tools_used,
                    "model": modelo_usado,
                }

            contents.append(candidate_content)
            contents.append({"role": "user", "parts": self._executar_tools(func_calls, tools_used)})

        raise RuntimeError("Limite de chamadas de ferramentas excedido na conversa.")

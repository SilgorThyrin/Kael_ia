"""Comandos para interagir com o plugin do Roblox Studio."""
import time

TOOL_NAME = "studio"


def _bridge(ctx):
    return getattr(ctx, "plugin_bridge", None)


def ping_studio(ctx, args, flags):
    b = _bridge(ctx)
    if not b:
        return {"response": "🔴 Plugin Bridge não carregado.", "thinking": "Bridge ausente.", "status": "error"}
    task = b.enqueue({"tipo": "ping"})
    return {"response": f"📡 **Ping enfileirado** (`{task['task_id']}`). Ative o polling no plugin do Studio e confira o Output.",
            "thinking": "Tarefa de ping enfileirada para o plugin.", "status": "success"}


def pedir_visao(ctx, args, flags):
    b = _bridge(ctx)
    if not b:
        return {"response": "🔴 Plugin Bridge não carregado.", "thinking": "Bridge ausente.", "status": "error"}
    task = b.enqueue({"tipo": "pedir_visao"})
    return {"response": f"🗺️ **Varredura solicitada** (`{task['task_id']}`). Ative o polling no plugin do Studio para mapear o Workspace.",
            "thinking": "Tarefa de visão enfileirada.", "status": "success"}


def pedir_print(ctx, args, flags):
    return {
        "response": "📸 Captura de screenshot ainda não é suportada pelo plugin Roblox.",
        "thinking": "Nenhuma tarefa foi enfileirada.",
        "status": "error",
    }


def studio_status(ctx, args, flags):
    b = _bridge(ctx)
    if not b:
        return {"response": "🔴 Plugin Bridge não carregado.", "thinking": "Bridge ausente.", "status": "error"}
    if not b.last_state:
        return {"response": "⚪ **Studio nunca enviou estado.** O plugin está instalado e o Studio aberto?",
                "thinking": "Sem estado recebido.", "status": "success"}
    idade = int(time.time() - b.last_state_time)
    objetos = b.last_state.get("total_instancias", 0)
    scripts = len(b.last_state.get("scripts_servidor", []))
    ultimo_teste = "nenhum"
    if b.last_test:
        ultimo_teste = f"{b.last_test.get('nome_script')}: {'✅' if b.last_test.get('sucesso') else '❌'}"
    return {
        "response": (
            "🎛️ **Status do Roblox Studio**\n"
            f"- **Último heartbeat:** há {idade}s\n"
            f"- **Objetos no Workspace:** {objetos}\n"
            f"- **Scripts de servidor:** {scripts}\n"
            f"- **Último teste:** {ultimo_teste}\n"
            f"- **Erros reportados:** {len(b.errors)}\n"
            f"- **Tarefas na fila:** {b.queue_length()}"
        ),
        "thinking": "Estado do plugin consultado via Bridge.",
        "status": "success"
    }


COMMANDS = {
    "/studio_ping": {"handler": ping_studio, "desc": "Ping no plugin do Studio", "capability": "studio"},
    "/studio_visao": {"handler": pedir_visao, "desc": "Pede varredura do Workspace", "capability": "studio"},
    "/studio_print": {"handler": pedir_print, "desc": "Pede screenshot (modo Play)", "capability": "studio"},
    "/studio_status": {"handler": studio_status, "desc": "Estado do plugin/Studio", "capability": "read"},
}
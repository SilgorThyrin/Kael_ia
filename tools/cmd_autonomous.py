"""Comandos do Modo Autônomo do Kael."""

TOOL_NAME = "autonomous"

try:
    from core.autonomous_engine import AutonomousEngine
    AVAILABLE = True
except ImportError:
    AVAILABLE = False
    class AutonomousEngine:
        def __init__(self, *a, **k): pass
        def start_task(self, *a, **k): return {"error": "Engine indisponível."}
        def stop_task(self): return {"message": "Engine indisponível."}
        def get_status(self): return {"status": "unavailable"}


def tarefa(ctx, args, flags):
    """Inicia uma tarefa autônoma."""
    if not AVAILABLE:
        return {"response": "🔴 AutonomousEngine indisponível.", "thinking": "Módulo ausente.", "status": "error"}
    
    if not args:
        return {"response": "⚠️ Uso: `/tarefa [descricao]`", "thinking": "Faltou descrição.", "status": "error"}
    
    description = " ".join(args)
    
    # Cria engine se não existir
    if not hasattr(ctx, 'autonomous_engine'):
        ctx.autonomous_engine = AutonomousEngine(ctx)
    
    result = ctx.autonomous_engine.start_task(description)
    
    if "error" in result:
        return {"response": f"⚠️ {result['error']}", "thinking": "Erro ao iniciar tarefa.", "status": "error"}
    
    return {
        "response": (
            f"🤖 **Modo Autônomo INICIADO!**\n"
            f"- **Tarefa:** {description}\n"
            f"- **ID:** #{result['task_id']}\n\n"
            f"O Kael vai planejar, executar e corrigir sozinho. "
            f"Use `/status_tarefa` para ver o progresso ou `/parar_tarefa` para interromper."
        ),
        "thinking": "Tarefa autônoma iniciada em thread separada.",
        "status": "success"
    }


def _get_engine(ctx):
    if not AVAILABLE:
        return None
    if not hasattr(ctx, "autonomous_engine"):
        ctx.autonomous_engine = AutonomousEngine(ctx)
    return ctx.autonomous_engine


def status_tarefa(ctx, args, flags):
    """Mostra status da tarefa autônoma atual."""
    engine = _get_engine(ctx)
    if engine is None:
        return {"response": "⚪ Nenhuma tarefa autônoma ativa.", "thinking": "Engine não inicializada.", "status": "success"}
    
    status = engine.get_status()
    
    if status['status'] == 'idle':
        return {"response": "⚪ Nenhuma tarefa ativa.", "thinking": "Engine ociosa.", "status": "success"}
    
    subtasks_txt = ""
    if 'subtasks' in status and status['subtasks']:
        subtasks_txt = "\n**Subtarefas:**\n"
        for i, s in enumerate(status['subtasks'], 1):
            icon = (
                "✅" if s['status'] == 'completed'
                else "🔄" if s['status'] == 'running'
                else "⚠️" if s['status'] == 'needs_review'
                else "⏳"
            )
            subtasks_txt += f"{icon} {i}. {s['description'][:60]} — {s['status']}\n"
    
    return {
        "response": (
            f"📊 **Status da Tarefa #{status['task_id']}**\n"
            f"- **Descrição:** {status['description']}\n"
            f"- **Status:** {status['status'].upper()}\n"
            f"{subtasks_txt}\n"
            f"{'**Resultado:** ' + status['result'] if status.get('result') else ''}\n"
            f"{'**Erro:** ' + status['error'] if status.get('error') else ''}"
        ),
        "thinking": "Status da tarefa consultado.",
        "status": "success"
    }


def parar_tarefa(ctx, args, flags):
    """Para a tarefa autônoma atual."""
    engine = _get_engine(ctx)
    if engine is None:
        return {"response": "⚪ Nenhuma tarefa para parar.", "thinking": "Engine não inicializada.", "status": "success"}
    
    result = engine.stop_task()
    return {"response": result['message'], "thinking": "Tarefa pausada.", "status": "success"}


def listar_tarefas(ctx, args, flags):
    engine = _get_engine(ctx)
    if engine is None:
        return {"response": "🔴 AutonomousEngine indisponível.", "thinking": "", "status": "error"}
    tasks = engine.list_tasks()
    if not tasks:
        return {"response": "Nenhuma tarefa autônoma salva.", "thinking": "", "status": "success"}
    lines = ["**Tarefas autônomas recentes:**"]
    for task in tasks:
        lines.append(
            f"- #{task['id']} · {task['status']} · {task['description'][:80]}"
        )
    return {"response": "\n".join(lines), "thinking": "", "status": "success"}


def retomar_tarefa(ctx, args, flags):
    engine = _get_engine(ctx)
    if engine is None:
        return {"response": "🔴 AutonomousEngine indisponível.", "thinking": "", "status": "error"}
    if not args:
        return {
            "response": "Uso: `/retomar_tarefa ID [--repetir-incerta]`",
            "thinking": "",
            "status": "error",
        }
    if any(arg != "--repetir-incerta" for arg in args[1:]):
        return {"response": "Argumento inválido para retomada.", "thinking": "", "status": "error"}
    result = engine.resume_task(
        args[0],
        retry_uncertain="--repetir-incerta" in args[1:],
    )
    if "error" in result:
        return {"response": result["error"], "thinking": "", "status": "error"}
    return {
        "response": result["message"],
        "thinking": "A tarefa foi retomada a partir do último checkpoint.",
        "status": "success",
    }


COMMANDS = {
    "/tarefa": {"handler": tarefa, "desc": "Inicia tarefa autônoma (ex: /tarefa Crie sistema de combate)", "capability": "project_write"},
    "/status_tarefa": {"handler": status_tarefa, "desc": "Mostra progresso da tarefa autônoma", "capability": "read"},
    "/tarefas": {"handler": listar_tarefas, "desc": "Lista tarefas autônomas recentes", "capability": "read"},
    "/retomar_tarefa": {"handler": retomar_tarefa, "desc": "Retoma uma tarefa pausada ou interrompida", "capability": "project_write"},
    "/parar_tarefa": {"handler": parar_tarefa, "desc": "Pausa a tarefa e preserva checkpoints", "capability": "control"},
}
"""Comandos de detecção/remoção de blocos flutuantes em lotes."""

TOOL_NAME = "floating"

try:
    from tools.floating_detector import FloatingDetector
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


def ver_flutuantes(ctx, args, flags):
    if not AVAILABLE:
        return {"response": "🔴 FloatingDetector indisponível.", "thinking": "Módulo ausente.", "status": "error"}
    det = FloatingDetector(str(ctx.project_path))
    place = det.find_place_file()
    if not place:
        return {
            "response": (
                "⚠️ Nenhum `.rbxlx` no projeto.\n"
                f"**Exporte:** Roblox Studio → File → Save As → `.rbxlx` em `{ctx.project_path}`.\n"
                "**Alternativa:** `/limpar_flutuantes` gera script Lua de raycast ao vivo."
            ),
            "thinking": "Place não exportado.", "status": "error"
        }
    parts = det.parse_rbxlx(place)
    floating = det.detect_floating(parts)
    linhas = "\n".join([f"- `{p['name']}` ({p['class']}) Y={p['pos'][1]:.1f}" for p in floating[:20]]) or "- nenhum"
    extra = f"\n- ...e mais {len(floating) - 20}" if len(floating) > 20 else ""

    docs = ctx.project_path / 'Docs'
    docs.mkdir(parents=True, exist_ok=True)
    rel = f"# Blocos Flutuantes\nTotal: {len(floating)} de {len(parts)}\n\n" + \
          "\n".join([f"- {p['name']} | Y={p['pos'][1]:.1f}" for p in floating])
    (docs / 'FLUTUANTES.md').write_text(rel, encoding='utf-8')

    return {
        "response": (
            f"👁️ **Visão do Kael: {place.name}**\n- Partes: {len(parts)}\n"
            f"- **Flutuantes: {len(floating)}**\n\n{linhas}{extra}\n\n"
            f"📄 `Docs/FLUTUANTES.md` | ➡️ `/limpar_flutuantes` remove em lotes."
        ),
        "thinking": "Raycast geométrico estático sobre o XML.", "status": "success"
    }


def limpar_flutuantes(ctx, args, flags):
    if not AVAILABLE:
        return {"response": "🔴 FloatingDetector indisponível.", "thinking": "Módulo ausente.", "status": "error"}
    batch = flags.get('lote', 50)
    det = FloatingDetector(str(ctx.project_path))
    place = det.find_place_file()
    names, copia_msg = [], ""

    if place:
        parts = det.parse_rbxlx(place)
        floating = det.detect_floating(parts)
        names = [p['name'] for p in floating]
        if names:
            out = place.with_name(place.stem + '_limpo.rbxlx')
            n = det.clean_rbxlx(place, {p['referent'] for p in floating}, out)
            copia_msg = f"- 📦 Cópia limpa: `{out.name}` ({n} removidos)\n"

    lua = det.generate_lua_batch(batch=batch, names=names or None)
    validation_response = ctx.process_save_commands(
        f"<kael_save filename='Scripts/remover_flutuantes.lua'>{lua}</kael_save>",
        save_dir=ctx.project_path,
    )

    modo = "DIRECIONADO (lista que o Kael viu)" if names else "RAYCAST AO VIVO"
    return {
        "response": (
            f"🧹 **Análise em lotes concluída** (lotes de {batch})\n- Modo: {modo}\n"
            f"- Blocos na lista: {len(names)}\n{copia_msg}{validation_response}"
        ),
        "thinking": "A gravação de Luau exige um runner de testes compatível.",
        "status": "error",
    }


COMMANDS = {
    "/ver_flutuantes": {"handler": ver_flutuantes, "desc": "Kael vê blocos sem apoio no .rbxlx", "capability": "overwrite"},
}
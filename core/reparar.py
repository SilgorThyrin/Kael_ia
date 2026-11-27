"""Módulo stub limpo para reparo local no Kael."""


def reparar_arquivo_sintaxe(caminho: str) -> dict:
    p = Path(caminho) if "Path" in globals() else __import__("pathlib").Path(caminho)
    if not p.exists():
        return {"ok": False, "erro": f"Arquivo não encontrado: {caminho}"}
    raw = p.read_bytes().replace(b"\x00", b"")
    p.write_bytes(raw)
    try:
        py_compile.compile(str(p), doraise=True)
        return {"ok": True, "arquivo": str(p)}
    except Exception as e:
        return {"ok": False, "arquivo": str(p), "erro": str(e)}

"""Validador estático pré-envio de scripts Luau para o Ecos de Aethelgard."""
import argparse
import re
import sys
from pathlib import Path


def validar_codigo_luau(codigo: str) -> list[str]:
    avisos = []
    linhas = codigo.splitlines()

    openers = 0
    ends = 0
    for idx, linha in enumerate(linhas, start=1):
        limpa = re.sub(r"--.*$", "", linha).strip()
        if not limpa:
            continue

        # Conta palavras-chave que abrem bloco, ignorando 'function' anônima inline com 'end' na mesma linha
        for match in re.finditer(r"\b(?:function|if|for|while)\b", limpa):
            kw = match.group(0)
            if kw == "function" and re.search(r"\bfunction\b.*\bend\b", limpa):
                continue
            openers += 1

        # 'do ... end' isolado (não precedido por 'for' ou 'while' na mesma linha)
        if not re.search(r"\b(?:for|while)\b", limpa):
            for _ in re.finditer(r"\bdo\b", limpa):
                if not re.search(r"\bdo\b.*\bend\b", limpa):
                    openers += 1

        ends += len(re.findall(r"\bend\b", limpa))

        if re.search(r"\bwait\s*\(", limpa) and not re.search(r"\btask\.wait\s*\(", limpa):
            avisos.append(f"Linha {idx}: prefira task.wait() em vez de wait() legado.")

        if re.search(r"Instance\.new\s*\(", limpa) and ".Parent" not in limpa:
            avisos.append(f"Linha {idx}: Instance.new() sem .Parent na mesma linha — confirme atribuição explícita.")

    if openers != ends:
        avisos.append(f"Possível desbalanceamento de blocos: aberturas={openers}, 'end'={ends}.")

    return avisos


def main():
    parser = argparse.ArgumentParser(description="Valida script Luau antes de enviar ao Roblox Studio.")
    parser.add_argument("arquivo", help="Caminho do arquivo .lua ou .luau")
    args = parser.parse_args()

    path = Path(args.arquivo).expanduser()
    if not path.is_file():
        print(f"Arquivo não encontrado: {path}")
        sys.exit(1)

    codigo = path.read_text(encoding="utf-8", errors="replace")
    avisos = validar_codigo_luau(codigo)
    if not avisos:
        print(f"✅ {path.name}: sem alertas básicos de estrutura/APIs.")
    else:
        print(f"⚠️ {path.name} ({len(avisos)} alerta(s)):")
        for a in avisos:
            print(f"  - {a}")


if __name__ == "__main__":
    main()

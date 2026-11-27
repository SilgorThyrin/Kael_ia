import json
import urllib.parse
import urllib.request
from typing import Dict, List


def buscar_repos_github(termo: str, limite: int = 5) -> Dict:
    q = (termo or "").strip()
    if not q:
        return {"erro": "Termo de busca vazio.", "resultados": []}

    params = urllib.parse.urlencode({
        "q": q,
        "sort": "stars",
        "order": "desc",
        "per_page": max(1, min(limite, 8)),
    })
    url = f"https://api.github.com/search/repositories?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Kael-Local-Agent/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"termo": q, "erro": str(exc), "resultados": []}

    itens: List[Dict] = []
    for item in (payload.get("items") or [])[:limite]:
        itens.append({
            "nome": item.get("full_name"),
            "estrelas": item.get("stargazers_count", 0),
            "linguagem": item.get("language") or "N/A",
            "descricao": (item.get("description") or "").strip()[:160],
            "url": item.get("html_url"),
        })

    return {"termo": q, "total_encontrado": payload.get("total_count", 0), "resultados": itens}


if __name__ == "__main__":
    import sys
    consulta = " ".join(sys.argv[1:]) or "python llm agent tools"
    print(json.dumps(buscar_repos_github(consulta, 5), indent=2, ensure_ascii=False))

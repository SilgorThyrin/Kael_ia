"""
============================================================
KAEL WEB RESEARCH v2.0 - Pesquisa de referência com fallbacks
============================================================
Estratégia em cascata:
  1. DuckDuckGo HTML (múltiplos parsers de regex)
  2. DuckDuckGo Instant Answer API (JSON, mais estável)
  3. Wikipedia API (fallback confiável para jogos famosos)
============================================================
"""
import re
import html as html_lib
import requests
import urllib.parse


class WebResearch:
    def __init__(self, timeout=20, max_results=4):
        self.timeout = timeout
        self.max_results = max_results
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    @staticmethod
    def _clean(fragment):
        if not fragment:
            return ""
        texto = re.sub(r'<[^>]+>', ' ', fragment)
        texto = html_lib.unescape(texto)
        return re.sub(r'\s+', ' ', texto).strip()

    # =========================================================
    # Múltiplos parsers para o DuckDuckGo HTML (mais robusto)
    # =========================================================
    def _search_ddg_html(self, query):
        """Tenta vários padrões de regex para extrair resultados."""
        try:
            encoded = urllib.parse.quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded}"
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            if resp.status_code != 200:
                print(f"[PESQUISA] DDG HTML status {resp.status_code}")
                return []
            page = resp.text

            # Padrões alternativos de extração (o DDG muda com frequência)
            patterns = [
                # Padrão 1: classes tradicionais
                (r'class="result__a"[^>]*>(.*?)</a>',
                 r'class="result__snippet"[^>]*>(.*?)</(?:a|span|td)'),
                # Padrão 2: tags article
                (r'<a[^>]+class="result__a"[^>]*>(.*?)</a>',
                 r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>'),
                # Padrão 3: headers h2
                (r'<h2[^>]+class="result__title"[^>]*>(.*?)</h2>',
                 r'<div[^>]+class="result__snippet"[^>]*>(.*?)</div>'),
                # Padrão 4: qualquer link com snippet vizinho
                (r'<a[^>]+class="[^"]*result[^"]*"[^>]*href="[^"]*"[^>]*>(.*?)</a>',
                 r'<span[^>]+class="[^"]*snippet[^"]*"[^>]*>(.*?)</span>'),
            ]

            for title_pat, snippet_pat in patterns:
                titles = re.findall(title_pat, page, re.DOTALL | re.IGNORECASE)
                snippets = re.findall(snippet_pat, page, re.DOTALL | re.IGNORECASE)
                if titles:
                    results = []
                    for i, t in enumerate(titles[:self.max_results]):
                        titulo = self._clean(t)
                        trecho = self._clean(snippets[i]) if i < len(snippets) else ""
                        if titulo and len(titulo) > 3:
                            results.append({"titulo": titulo, "trecho": trecho})
                    if results:
                        return results

            # Fallback extremo: pega qualquer <a> com href http
            fallback = re.findall(
                r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>',
                page, re.DOTALL | re.IGNORECASE
            )
            results = []
            for href, texto in fallback[:self.max_results]:
                titulo = self._clean(texto)
                if titulo and len(titulo) > 5 and "duckduckgo" not in href.lower():
                    results.append({"titulo": titulo, "trecho": f"(fonte: {href[:80]})"})
            return results

        except Exception as e:
            print(f"[PESQUISA] Erro DDG HTML: {e}")
            return []

    # =========================================================
    # DuckDuckGo Instant Answer API (JSON, muito estável)
    # =========================================================
    def _search_ddg_api(self, query):
        try:
            url = "https://api.duckduckgo.com/"
            params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
            resp = requests.get(url, params=params, headers=self.headers, timeout=self.timeout)
            if resp.status_code != 200:
                return []
            data = resp.json()

            results = []
            if data.get("Abstract"):
                results.append({
                    "titulo": data.get("Heading", query),
                    "trecho": data["Abstract"][:500]
                })
            if data.get("RelatedTopics"):
                for topic in data["RelatedTopics"][:self.max_results]:
                    if isinstance(topic, dict) and topic.get("Text"):
                        results.append({
                            "titulo": topic.get("Text", "")[:80],
                            "trecho": topic.get("Text", "")[:300]
                        })
            return results
        except Exception as e:
            print(f"[PESQUISA] Erro DDG API: {e}")
            return []

    # =========================================================
    # Wikipedia API (fallback confiável para jogos famosos)
    # =========================================================
    def _search_wikipedia(self, query):
        try:
            search_url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": self.max_results,
            }
            resp = requests.get(search_url, params=params, headers=self.headers, timeout=self.timeout)
            if resp.status_code != 200:
                return []
            data = resp.json()
            results = []
            for hit in data.get("query", {}).get("search", []):
                results.append({
                    "titulo": hit.get("title", ""),
                    "trecho": self._clean(hit.get("snippet", ""))
                })
            return results
        except Exception as e:
            print(f"[PESQUISA] Erro Wikipedia: {e}")
            return []

    # =========================================================
    # Pesquisa pública unificada
    # =========================================================
    def search(self, query):
        """Tenta DDG HTML → DDG API → Wikipedia até conseguir resultados."""
        print(f"[PESQUISA] Consultando: {query}")

        # 1. DuckDuckGo HTML
        results = self._search_ddg_html(query)
        if results:
            return results

        # 2. DDG Instant Answer API
        results = self._search_ddg_api(query)
        if results:
            return results

        # 3. Wikipedia
        results = self._search_wikipedia(query)
        if results:
            return results

        print(f"[PESQUISA] Nenhum resultado para: {query}")
        return []

    # =========================================================
    # Pesquisa estruturada de gênero + jogos de exemplo
    # =========================================================
    def research_genre(self, genero, exemplos=None, max_queries=5):
        exemplos = exemplos or []
        consultas = [
            f"{genero} games mechanics design analysis",
            f"best {genero} games list gameplay features",
        ]
        for ex in exemplos[:3]:
            consultas.append(f"{ex} game review gameplay mechanics")
        if exemplos:
            consultas.append(f"games similar to {exemplos[0]} {genero}")
        consultas = consultas[:max_queries]

        relatorio = []
        for q in consultas:
            resultados = self.search(q)
            if resultados:
                relatorio.append(f"\n=== Pesquisa: {q} ===")
                for r in resultados:
                    relatorio.append(f"• {r['titulo']}")
                    if r.get('trecho'):
                        relatorio.append(f"  {r['trecho'][:400]}")

        if not relatorio:
            return ""

        header = (
            f"# Relatório de Pesquisa: {genero}\n"
            f"Jogos de referência: {', '.join(exemplos) if exemplos else '(nenhum)'}\n"
            f"Fontes: DuckDuckGo + Wikipedia\n"
        )
        return header + "\n".join(relatorio)


# =============================================================
# TESTE DE DIAGNÓSTICO
# =============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("TESTE DE CONECTIVIDADE WEB DO KAEL")
    print("=" * 60)
    wr = WebResearch()

    print("\n[1/3] DuckDuckGo HTML...")
    r1 = wr._search_ddg_html("Hollow Knight game")
    print(f"   → {len(r1)} resultados encontrados")

    print("[2/3] DuckDuckGo API...")
    r2 = wr._search_ddg_api("The Witcher 3")
    print(f"   → {len(r2)} resultados encontrados")

    print("[3/3] Wikipedia...")
    r3 = wr._search_wikipedia("Elder Scrolls Skyrim")
    print(f"   → {len(r3)} resultados encontrados")

    print("\n[TESTE] Pesquisa completa de gênero:")
    rel = wr.research_genre("RPG", ["The Witcher 3", "Skyrim"])
    if rel:
        print(f"   ✅ Relatório gerado ({len(rel)} caracteres)")
        print("\n" + rel[:800])
    else:
        print("   ❌ Falha total. Verifique conexão com internet.")

    print("=" * 60)
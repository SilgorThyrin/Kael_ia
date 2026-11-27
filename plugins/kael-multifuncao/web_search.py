"""Busca web leve para Termux usando Bing (RSS/HTML) com fallback no DuckDuckGo."""
import base64
import ipaddress
import re
import socket
import urllib.parse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
import requests

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 14; Mobile) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def _decode_bing_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if "bing.com" in parsed.netloc and parsed.path.startswith("/ck/"):
        qs = urllib.parse.parse_qs(parsed.query)
        u = (qs.get("u") or [""])[0]
        if u.startswith("a1"):
            raw = u[2:] + "=" * (-len(u[2:]) % 4)
            try:
                decoded = base64.urlsafe_b64decode(raw).decode("utf-8", errors="ignore")
                if decoded.startswith(("http://", "https://")):
                    return decoded
            except Exception:
                pass
    return url


def _decode_ddg_url(url: str) -> str:
    if url.startswith("//"):
        url = "https:" + url
    parsed = urllib.parse.urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        qs = urllib.parse.parse_qs(parsed.query)
        target = (qs.get("uddg") or [""])[0]
        if target.startswith(("http://", "https://")):
            return target
    return url


class _BingHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self._in_algo = False
        self._li_depth = 0
        self._in_h2 = False
        self._in_title_a = False
        self._in_p = False
        self._cur = None

    def handle_starttag(self, tag, attrs):
        attr_map = dict(attrs)
        cls = attr_map.get("class", "")
        if tag == "li" and "b_algo" in cls.split():
            self._in_algo = True
            self._li_depth = 1
            self._cur = {"titulo": "", "url": "", "resumo": ""}
            return
        if not self._in_algo:
            return
        if tag == "li":
            self._li_depth += 1
        elif tag == "h2":
            self._in_h2 = True
        elif tag == "a" and self._in_h2 and not self._cur["url"]:
            href = attr_map.get("href", "")
            if href.startswith(("http://", "https://")):
                self._cur["url"] = _decode_bing_url(href)
                self._in_title_a = True
        elif tag == "p" and not self._cur["resumo"]:
            self._in_p = True

    def handle_endtag(self, tag):
        if not self._in_algo:
            return
        if tag == "a":
            self._in_title_a = False
        elif tag == "h2":
            self._in_h2 = False
        elif tag == "p":
            self._in_p = False
        elif tag == "li":
            self._li_depth -= 1
            if self._li_depth <= 0:
                if self._cur and self._cur["titulo"] and self._cur["url"]:
                    self._cur["titulo"] = " ".join(self._cur["titulo"].split())
                    self._cur["resumo"] = " ".join(self._cur["resumo"].split())
                    self.results.append(self._cur)
                self._in_algo = False
                self._cur = None

    def handle_data(self, data):
        if not self._in_algo or not self._cur:
            return
        if self._in_title_a:
            self._cur["titulo"] += data
        elif self._in_p:
            self._cur["resumo"] += data


class _DDGHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self._cur = None
        self._in_title = False
        self._in_snippet = False

    def handle_starttag(self, tag, attrs):
        attr_map = dict(attrs)
        cls = attr_map.get("class", "").split()
        if tag == "a" and "result__a" in cls:
            if self._cur and self._cur.get("url"):
                self.results.append(self._cur)
            self._cur = {
                "titulo": "",
                "url": _decode_ddg_url(attr_map.get("href", "")),
                "resumo": "",
            }
            self._in_title = True
        elif "result__snippet" in cls and self._cur is not None:
            self._in_snippet = True

    def handle_endtag(self, tag):
        if tag == "a" and self._in_title:
            self._in_title = False
        elif self._in_snippet and tag in ("a", "div", "span"):
            self._in_snippet = False
            if self._cur and self._cur.get("titulo") and self._cur.get("url"):
                self._cur["titulo"] = " ".join(self._cur["titulo"].split())
                self._cur["resumo"] = " ".join(self._cur["resumo"].split())
                self.results.append(self._cur)
                self._cur = None

    def handle_data(self, data):
        if not self._cur:
            return
        if self._in_title:
            self._cur["titulo"] += data
        elif self._in_snippet:
            self._cur["resumo"] += data


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._skip = 0
        self._parts = []
        self._title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in ("p", "br", "li", "h1", "h2", "h3", "div", "tr"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self._skip > 0:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self._title += data
        elif self._skip == 0:
            txt = data.strip()
            if txt:
                self._parts.append(txt + " ")

    def text(self) -> tuple[str, str]:
        raw = "".join(self._parts)
        cleaned = re.sub(r"\n{3,}", "\n\n", raw).strip()
        return " ".join(self._title.split()), cleaned


def buscar_bing(consulta: str, limite: int = 5) -> list[dict]:
    # 1. Tenta via RSS do Bing (mais leve e direto)
    try:
        r = requests.get(
            "https://www.bing.com/search",
            params={"q": consulta, "format": "rss", "setlang": "pt-BR", "mkt": "pt-BR"},
            headers=_HEADERS,
            timeout=8,
        )
        if r.ok and "<item>" in r.text:
            root = ET.fromstring(r.text)
            itens = []
            for item in root.findall(".//item")[:limite]:
                titulo = (item.findtext("title") or "").strip()
                link = _decode_bing_url((item.findtext("link") or "").strip())
                desc = (item.findtext("description") or "").strip()
                if titulo and link:
                    itens.append({"titulo": titulo, "url": link, "resumo": desc, "fonte": "bing"})
            if itens:
                return itens
    except Exception:
        pass

    # 2. Fallback via HTML do Bing
    try:
        r = requests.get(
            "https://www.bing.com/search",
            params={"q": consulta, "setlang": "pt-BR"},
            headers=_HEADERS,
            timeout=8,
        )
        if r.ok:
            parser = _BingHTMLParser()
            parser.feed(r.text)
            for item in parser.results:
                item["fonte"] = "bing"
            if parser.results:
                return parser.results[:limite]
    except Exception:
        pass

    return []



def buscar_bing_noticias(consulta: str, limite: int = 5) -> list[dict]:
    """Busca notícias recentes via RSS do Bing News."""
    try:
        r = requests.get(
            "https://www.bing.com/news/search",
            params={"q": consulta, "format": "rss", "setlang": "pt-BR", "mkt": "pt-BR"},
            headers=_HEADERS,
            timeout=8,
        )
        if r.ok and "<item>" in r.text:
            root = ET.fromstring(r.text)
            itens = []
            for item in root.findall(".//item")[:limite]:
                titulo = (item.findtext("title") or "").strip()
                link = _decode_bing_url((item.findtext("link") or "").strip())
                desc = (item.findtext("description") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                if titulo and link:
                    itens.append({
                        "titulo": titulo,
                        "url": link,
                        "resumo": f"[{pub}] {desc}".strip(),
                        "fonte": "bing_news",
                    })
            return itens
    except Exception:
        pass
    return []

def buscar_duckduckgo(consulta: str, limite: int = 5) -> list[dict]:
    try:
        r = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": consulta, "kl": "br-pt"},
            headers={**_HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
            timeout=8,
        )
        if r.ok:
            parser = _DDGHTMLParser()
            parser.feed(r.text)
            for item in parser.results:
                item["fonte"] = "duckduckgo"
            return parser.results[:limite]
    except Exception:
        pass
    return []


def _url_publica_segura(url: str) -> tuple[bool, str]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False, "Use apenas URLs http:// ou https:// válidas."
    host = parsed.hostname
    if host.lower() in ("localhost", "ip6-localhost"):
        return False, "Acesso a endereços locais bloqueado."
    try:
        infos = socket.getaddrinfo(host, None)
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False, "Acesso a rede interna/privada bloqueado por segurança."
    except Exception:
        return False, f"Não foi possível resolver o host '{host}'."
    return True, ""


def ler_url_publica(url: str, max_chars: int = 8000) -> dict:
    atual = url.strip()
    for _ in range(4):
        ok, erro = _url_publica_segura(atual)
        if not ok:
            return {"erro": erro}
        r = requests.get(atual, headers=_HEADERS, timeout=8, allow_redirects=False)
        if r.is_redirect or r.is_permanent_redirect:
            loc = r.headers.get("Location", "")
            atual = urllib.parse.urljoin(atual, loc)
            continue
        r.raise_for_status()
        ctype = r.headers.get("Content-Type", "").lower()
        if "text/" not in ctype and "json" not in ctype and "xml" not in ctype:
            return {"erro": f"Tipo de conteúdo não textual ({ctype})."}
        if "html" in ctype:
            ext = _TextExtractor()
            ext.feed(r.text)
            titulo, corpo = ext.text()
            return {"url": atual, "titulo": titulo, "conteudo": corpo[:max_chars]}
        return {"url": atual, "titulo": "", "conteudo": r.text[:max_chars]}
    return {"erro": "Muitos redirecionamentos na URL."}

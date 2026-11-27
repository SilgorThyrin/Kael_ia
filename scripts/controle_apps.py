import json, os, re, subprocess, time
from typing import Dict, List, Optional

BASE_DIR = os.path.expanduser("~/Kael_ia")
DATA_DIR = os.path.join(BASE_DIR, "data")
CACHE_APPS_ANDROID = os.path.join(DATA_DIR, "apps_android.json")
FILA_PC_PATH = os.path.join(DATA_DIR, "fila_pc.json")

ALIASES_ANDROID = {
    "whatsapp": "com.whatsapp",
    "whatsapp_business": "com.whatsapp.w4b",
    "youtube": "com.google.android.youtube",
    "chrome": "com.android.chrome",
    "navegador": "com.android.chrome",
    "samsung_internet": "com.sec.android.app.sbrowser",
    "mexc": "com.mexcpro.client",
    "roblox": "com.roblox.client",
    "github": "com.github.android",
    "discord": "com.discord",
    "telegram": "org.telegram.messenger",
    "spotify": "com.spotify.music",
    "configuracoes": "com.android.settings",
    "ajustes": "com.android.settings",
    "camera": "com.sec.android.app.camera",
    "galeria": "com.sec.android.gallery3d",
    "arquivos": "com.sec.android.app.myfiles",
    "calculadora": "com.sec.android.app.popupcalculator",
    "relogio": "com.sec.android.app.clockpackage",
    "galaxy_wearable": "com.samsung.android.app.watchmanager",
    "acode": "com.foxdebug.acodefree",
    "termux": "com.termux",
    "gmail": "com.google.android.gm",
    "maps": "com.google.android.apps.maps",
    "caixa": "br.com.gabba.Caixa",
}

COMANDOS_PC_PERMITIDOS = {
    "roblox_studio": {"acao": "abrir_app", "alvo": "RobloxStudioBeta.exe", "descricao": "Abrir Roblox Studio no PC"},
    "vscode": {"acao": "abrir_app", "alvo": "Code.exe", "descricao": "Abrir Visual Studio Code no PC"},
    "navegador": {"acao": "abrir_app", "alvo": "chrome.exe", "descricao": "Abrir Google Chrome no PC"},
    "sincronizar_aethelgard": {"acao": "sync_projeto", "alvo": "Ecos_de_Aethelgard", "descricao": "Sincronizar scripts Luau de Ecos de Aethelgard"},
}

def _garantir_diretorios() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(FILA_PC_PATH):
        with open(FILA_PC_PATH, "w", encoding="utf-8") as f:
            json.dump({"comandos": []}, f, ensure_ascii=False, indent=2)

def _coletar_pacotes_pm() -> List[str]:
    pacotes: List[str] = []
    for cmd in (["pm", "list", "packages", "-3"], ["cmd", "package", "list", "packages", "-3"]):
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=6, check=False)
            if res.returncode == 0 and res.stdout:
                for linha in res.stdout.splitlines():
                    linha = linha.strip()
                    if linha.startswith("package:"):
                        pacotes.append(linha.replace("package:", "", 1))
            if pacotes:
                return pacotes
        except Exception:
            continue
    return pacotes

def _coletar_pacotes_storage() -> List[str]:
    encontrados = set(ALIASES_ANDROID.values())
    for base in ("/sdcard/Android/data", "/sdcard/Android/media", "/storage/emulated/0/Android/data", "/storage/emulated/0/Android/media"):
        try:
            if os.path.isdir(base):
                for item in os.listdir(base):
                    if "." in item and not item.startswith("."):
                        encontrados.add(item.strip())
        except Exception:
            continue
    return sorted(encontrados)

def listar_apps_android(forcar_atualizacao: bool = False) -> Dict:
    _garantir_diretorios()
    if not forcar_atualizacao and os.path.exists(CACHE_APPS_ANDROID):
        try:
            with open(CACHE_APPS_ANDROID, "r", encoding="utf-8") as f:
                dados = json.load(f)
                if dados.get("pacotes"):
                    return dados
        except Exception:
            pass
    origem = "pm"
    pacotes = _coletar_pacotes_pm()
    if not pacotes:
        origem = "storage_e_aliases"
        pacotes = _coletar_pacotes_storage()
    else:
        pacotes = sorted(set(pacotes) | set(ALIASES_ANDROID.values()))
    payload = {"ok": True, "origem": origem, "atualizado_em": int(time.time()), "total": len(pacotes), "pacotes": pacotes}
    with open(CACHE_APPS_ANDROID, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload

def resolver_pacote_android(nome_ou_pacote: str) -> Optional[str]:
    termo_raw = nome_ou_pacote.strip().lower().replace(" ", "_")
    termo = re.sub(r"[^a-zA-Z0-9._-]", "", termo_raw)
    if not termo:
        return None
    if termo in ALIASES_ANDROID:
        return ALIASES_ANDROID[termo]
    if "." in termo and not termo.startswith("."):
        return termo
    dados = listar_apps_android(forcar_atualizacao=False)
    for pkg in dados.get("pacotes", []):
        if termo in pkg.lower():
            return pkg
    return None

def abrir_app_android(nome_ou_pacote: str) -> Dict:
    pacote = resolver_pacote_android(nome_ou_pacote)
    if not pacote:
        return {"ok": False, "erro": f"Aplicativo {nome_ou_pacote} nao encontrado no mapeamento."}
    comandos = [
        ["am", "start", "--user", "0", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER", "-p", pacote],
        ["monkey", "-p", pacote, "-c", "android.intent.category.LAUNCHER", "1"],
    ]
    ultimo_erro = ""
    for cmd in comandos:
        try:
            exec_res = subprocess.run(cmd, capture_output=True, text=True, timeout=8, check=False)
            saida = (exec_res.stdout + "\n" + exec_res.stderr).strip()
            if exec_res.returncode == 0 and "Error:" not in saida and "Exception" not in saida:
                return {"ok": True, "plataforma": "android", "pacote": pacote, "metodo": cmd[0], "mensagem": f"Aplicativo {pacote} iniciado no Android."}
            ultimo_erro = saida or f"Codigo de saida {exec_res.returncode}"
        except Exception as e:
            ultimo_erro = str(e)
    return {"ok": False, "pacote": pacote, "erro": ultimo_erro or "Nao foi possivel iniciar o aplicativo no Android."}

def enfileirar_comando_pc(chave_comando: str, payload_extra: Optional[Dict] = None) -> Dict:
    _garantir_diretorios()
    chave = chave_comando.strip().lower()
    if chave not in COMANDOS_PC_PERMITIDOS:
        return {"ok": False, "erro": f"Comando {chave_comando} nao esta na whitelist do PC.", "permitidos": list(COMANDOS_PC_PERMITIDOS.keys())}
    spec = COMANDOS_PC_PERMITIDOS[chave]
    item = {"id": f"pc_{int(time.time() * 1000)}", "criado_em": int(time.time()), "status": "pendente", "chave": chave, "acao": spec["acao"], "alvo": spec["alvo"], "descricao": spec["descricao"], "extra": payload_extra or {}}
    with open(FILA_PC_PATH, "r", encoding="utf-8") as f:
        dados = json.load(f)
    dados.setdefault("comandos", []).append(item)
    dados["comandos"] = dados["comandos"][-50:]
    with open(FILA_PC_PATH, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    return {"ok": True, "plataforma": "windows_pc", "item": item, "mensagem": f"Comando {spec['descricao']} enfileirado para o PC Windows."}

def listar_fila_pc(apenas_pendentes: bool = True) -> List[Dict]:
    _garantir_diretorios()
    with open(FILA_PC_PATH, "r", encoding="utf-8") as f:
        dados = json.load(f)
    comandos = dados.get("comandos", [])
    return [c for c in comandos if c.get("status") == "pendente"] if apenas_pendentes else comandos



# === INTENTS DE AÇÃO INTERNA EM APPS ANDROID ===
import urllib.parse


def resolver_contato_whatsapp(dest: str) -> str:
    """Resolve nome de contato via termux-contact-list ou extrai dígitos se já for telefone."""
    import json, unicodedata
    dest = (dest or "").strip()
    if not dest:
        return ""
    digitos = "".join(ch for ch in dest if ch.isdigit())
    if len(digitos) >= 8:
        return digitos if digitos.startswith("55") else "55" + digitos

    def _norm(s):
        return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn").strip()

    alvo_norm = _norm(dest)
    cache_path = os.path.expanduser("~/Kael_ia/data/contatos_cache.json")
    contatos = []
    try:
        res = subprocess.run(["termux-contact-list"], capture_output=True, text=True, timeout=6)
        if res.returncode == 0 and res.stdout.strip().startswith("["):
            contatos = json.loads(res.stdout)
            open(cache_path, "w", encoding="utf-8").write(res.stdout)
    except Exception:
        pass
    if not contatos and os.path.exists(cache_path):
        try:
            contatos = json.loads(open(cache_path, encoding="utf-8").read())
        except Exception:
            contatos = []

    for c in contatos:
        nome = _norm(str(c.get("name") or ""))
        if alvo_norm == nome or alvo_norm in nome:
            num = "".join(ch for ch in str(c.get("number") or "") if ch.isdigit())
            if len(num) >= 8:
                return num if num.startswith("55") else "55" + num
    return ""

def executar_intent_android(especificacao: str) -> dict:
    """
    Formato esperado: 'musica|<app_hint>|<query>' ou 'pesquisa|<app_hint>|<query>' ou 'whatsapp|<destino>|<texto>'
    """
    import urllib.parse, urllib.request
    partes = (especificacao or "").split("|", 2)
    if len(partes) < 3:
        return {"ok": False, "error": "Especificação de intent inválida."}
    tipo, alvo_app, termo = partes[0].strip().lower(), partes[1].strip().lower(), partes[2].strip()
    q_enc = urllib.parse.quote(termo)

    if tipo == "musica":
        try:
            if any(b in alvo_app for b in ("brave", "chrome", "navegador", "browser")):
                import re as _re
                pacote_nav = resolver_pacote_android("brave" if "brave" in alvo_app else "chrome")
                url_yt = f"https://www.youtube.com/results?search_query={q_enc}"
                try:
                    req = urllib.request.Request(url_yt, headers={"User-Agent": "Mozilla/5.0"})
                    html_yt = urllib.request.urlopen(req, timeout=6).read().decode("utf-8", errors="ignore")
                    padrao = chr(34) + r"videoId" + chr(34) + r":" + chr(34) + r"([a-zA-Z0-9_-]{11})" + chr(34)
                    m_vid = _re.search(padrao, html_yt)
                    if m_vid:
                        url_yt = f"https://www.youtube.com/watch?v={m_vid.group(1)}"
                except Exception:
                    pass
                cmd = ["am", "start", "--user", "0", "-a", "android.intent.action.VIEW", "-d", url_yt]
                if pacote_nav:
                    cmd += ["-p", pacote_nav]
                subprocess.run(cmd, capture_output=True, text=True)
                return {"ok": True, "modo": "BROWSER_AUTOPLAY", "url": url_yt, "pacote": pacote_nav}
            pacote = resolver_pacote_android(alvo_app) if alvo_app not in ("", "musica", "música", "youtube music", "yt music") else ""
            if pacote:
                cmd = [
                    "am", "start", "--user", "0",
                    "-a", "android.media.action.MEDIA_PLAY_FROM_SEARCH",
                    "-e", "query", termo,
                    "-p", pacote,
                ]
                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode == 0 and "Error" not in (res.stderr or ""):
                    return {"ok": True, "modo": "MEDIA_PLAY_FROM_SEARCH", "pacote": pacote, "query": termo}
                subprocess.run(["termux-clipboard-set", termo], capture_output=True, text=True)
                abriu = abrir_app_android(pacote)
                return {"ok": bool(abriu.get("ok")), "modo": "APP_ABERTO_CLIPBOARD", "pacote": pacote, "query": termo}
            url_ytm = f"https://music.youtube.com/search?q={q_enc}"
            subprocess.run(["am", "start", "--user", "0", "-a", "android.intent.action.VIEW", "-d", url_ytm], capture_output=True, text=True)
            return {"ok": True, "modo": "VIEW_MUSIC_URL", "url": url_ytm, "pacote": ""}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    if tipo == "pesquisa":
        if "youtube" in alvo_app:
            url = f"https://www.youtube.com/results?search_query={q_enc}"
        else:
            url = f"https://www.google.com/search?q={q_enc}"
        subprocess.run(["am", "start", "--user", "0", "-a", "android.intent.action.VIEW", "-d", url], capture_output=True, text=True)
        return {"ok": True, "modo": "ACTION_VIEW", "url": url}

    if tipo == "whatsapp":
        num = resolver_contato_whatsapp(alvo_app)
        if alvo_app and not num:
            return {"ok": False, "error": f"Contato '{alvo_app}' não encontrado na agenda (verifique permissão de Contatos do Termux:API)."}
        if num and termo:
            url = f"https://wa.me/{num}?text={q_enc}"
        elif num:
            url = f"https://wa.me/{num}"
        else:
            url = f"https://api.whatsapp.com/send?text={q_enc}"
        subprocess.run(["am", "start", "--user", "0", "-a", "android.intent.action.VIEW", "-d", url], capture_output=True, text=True)
        return {"ok": True, "modo": "WHATSAPP_URI", "url": url, "telefone": num}

    return {"ok": False, "error": f"Tipo de intent desconhecido: {tipo}"}

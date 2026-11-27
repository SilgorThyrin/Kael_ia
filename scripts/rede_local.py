import socket
import subprocess
import concurrent.futures
from typing import List, Dict

def obter_ip_local() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

def _ping_ou_porta(ip: str) -> bool:
    # Tenta conexão rápida em portas comuns (SSH/Termux, HTTP/Kael, SMB/Windows)
    for porta in (8000, 8022, 22, 445, 80):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.25)
        try:
            if s.connect_ex((ip, porta)) == 0:
                return True
        except Exception:
            pass
        finally:
            s.close()
    return False

def listar_dispositivos_lan() -> Dict:
    ip_local = obter_ip_local()
    if ip_local == "127.0.0.1":
        return {"ip_local": ip_local, "dispositivos": [], "erro": "Sem conexão de rede local."}

    prefixo = ".".join(ip_local.split(".")[:3])
    encontrados = {}

    # 1. Lê tabela ARP existente (ip neigh)
    try:
        out = subprocess.check_output(["ip", "neigh", "show"], text=True, stderr=subprocess.DEVNULL)
        for linha in out.splitlines():
            partes = linha.split()
            if partes and partes[0].startswith(prefixo + "."):
                ip = partes[0]
                if "FAILED" not in linha:
                    encontrados[ip] = {"ip": ip, "origem": "arp", "kael_ativo": False}
    except Exception:
        pass

    # 2. Varredura rápida paralela na sub-rede para detectar portas abertas (incluindo Kael :8000)
    ips_alvo = [f"{prefixo}.{i}" for i in range(1, 255) if f"{prefixo}.{i}" != ip_local]
    with concurrent.futures.ThreadPoolExecutor(max_workers=40) as ex:
        resultados = ex.map(lambda ip: (ip, _ping_ou_porta(ip)), ips_alvo)
        for ip, ativo in resultados:
            if ativo:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.3)
                kael_on = False
                try:
                    kael_on = (s.connect_ex((ip, 8000)) == 0)
                except Exception:
                    pass
                finally:
                    s.close()
                encontrados[ip] = {
                    "ip": ip,
                    "origem": "scan",
                    "kael_ativo": kael_on
                }

    lista = sorted(encontrados.values(), key=lambda x: int(x["ip"].split(".")[-1]))
    return {"ip_local": ip_local, "dispositivos": lista}

if __name__ == "__main__":
    import json
    print(json.dumps(listar_dispositivos_lan(), indent=2, ensure_ascii=False))

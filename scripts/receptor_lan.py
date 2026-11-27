import argparse
import os
import tarfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

DESTINO_PADRAO = Path.home() / "Kael_ia"
ARQ_TEMP = Path("/tmp/kael_recebido.tar.gz")

class ReceptorHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/receber-pacote":
            self.send_response(404)
            self.end_headers()
            return
        tamanho = int(self.headers.get("Content-Length", "0"))
        if tamanho <= 0:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error":"Pacote vazio"}')
            return
        ARQ_TEMP.parent.mkdir(parents=True, exist_ok=True)
        with open(ARQ_TEMP, "wb") as f:
            restante = tamanho
            while restante > 0:
                bloco = self.rfile.read(min(65536, restante))
                if not bloco:
                    break
                f.write(bloco)
                restante -= len(bloco)

        DESTINO_PADRAO.mkdir(parents=True, exist_ok=True)
        with tarfile.open(ARQ_TEMP, "r:gz") as tf:
            tf.extractall(path=DESTINO_PADRAO)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        msg = f'{{"status":"instalado","destino":"{DESTINO_PADRAO}"}}'.encode("utf-8")
        self.wfile.write(msg)

    def log_message(self, format, *args):
        return

def main():
    global DESTINO_PADRAO
    parser = argparse.ArgumentParser()
    parser.add_argument("--porta", type=int, default=8099)
    parser.add_argument("--destino", type=str, default=str(DESTINO_PADRAO))
    args = parser.parse_args()
    DESTINO_PADRAO = Path(args.destino).expanduser()
    confirm = input(f"Confirmar recebimento e extração do Kael em {DESTINO_PADRAO} na porta {args.porta}? [s/N]: ").strip().lower()
    if confirm != "s":
        print("Recebimento cancelado pelo usuário.")
        return
    server = HTTPServer(("0.0.0.0", args.porta), ReceptorHandler)
    print(f"Receptor LAN aguardando pacote em 0.0.0.0:{args.porta} -> {DESTINO_PADRAO}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    main()

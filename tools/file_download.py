"""Bounded HTTPS downloads into an explicitly selected project folder."""
import ipaddress
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import socket
import tempfile
import time
from urllib.parse import urljoin, urlsplit

import requests


MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
MAX_REDIRECTS = 5
CHUNK_SIZE = 64 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 120


class DownloadError(ValueError):
    pass


def _validate_url(url, resolve_host):
    if (
        not isinstance(url, str)
        or not url
        or len(url) > 4096
        or any(character.isspace() or ord(character) < 32 for character in url)
    ):
        raise DownloadError("Informe uma URL HTTPS válida.")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise DownloadError("A URL informada é inválida.") from exc
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        raise DownloadError("Downloads aceitam somente URLs HTTPS públicas na porta padrão.")

    host = parsed.hostname.rstrip(".")
    if not host:
        raise DownloadError("A URL precisa conter um host público.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None

    if address is not None:
        if not address.is_global:
            raise DownloadError("A URL não pode apontar para endereços locais ou privados.")
    elif resolve_host:
        try:
            resolved = socket.getaddrinfo(
                host.encode("idna").decode("ascii"),
                443,
                type=socket.SOCK_STREAM,
            )
        except (OSError, UnicodeError) as exc:
            raise DownloadError("Não foi possível validar o endereço público da URL.") from exc
        addresses = {
            item[4][0].split("%", 1)[0]
            for item in resolved
            if item and len(item) > 4 and item[4]
        }
        if not addresses or any(
            not ipaddress.ip_address(item).is_global for item in addresses
        ):
            raise DownloadError("A URL precisa resolver somente para endereços públicos.")
    return parsed


def validate_download_request(url, relative_path, project_path, *, resolve_host=True):
    _validate_url(url, resolve_host)
    if not isinstance(relative_path, str) or not relative_path.strip() or len(relative_path) > 512:
        raise DownloadError("Informe um destino relativo dentro do projeto.")
    if any(ord(character) < 32 for character in relative_path):
        raise DownloadError("O destino contém caracteres inválidos.")

    normalized = relative_path.replace("\\", "/")
    posix_path = PurePosixPath(normalized)
    windows_path = PureWindowsPath(relative_path)
    invalid_windows_chars = set('<>:"|?*')
    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or any(part in {"", ".", ".."} for part in normalized.split("/"))
        or any(
            any(character in invalid_windows_chars for character in part)
            or part.endswith((" ", "."))
            for part in posix_path.parts
        )
    ):
        raise DownloadError("O destino deve ser um caminho relativo, sem '..' ou raiz de disco.")

    try:
        project_root = Path(project_path).resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise DownloadError("A pasta do projeto não está disponível.") from exc
    if not project_root.is_dir():
        raise DownloadError("O destino do download precisa ser uma pasta de projeto.")

    target = project_root.joinpath(*posix_path.parts).resolve(strict=False)
    if target == project_root or project_root not in target.parents:
        raise DownloadError("O destino saiu da pasta do projeto.")
    if target.exists():
        raise DownloadError("O arquivo de destino já existe; escolha outro nome para evitar sobrescrita.")
    return target


def download_file(url, relative_path, project_path):
    target = validate_download_request(url, relative_path, project_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    session = requests.Session()
    session.trust_env = False
    response = None
    try:
        current_url = url
        for redirect_count in range(MAX_REDIRECTS + 1):
            _validate_url(current_url, resolve_host=True)
            try:
                response = session.get(
                    current_url,
                    stream=True,
                    timeout=(5, 30),
                    allow_redirects=False,
                )
            except requests.RequestException as exc:
                raise DownloadError(f"Falha ao baixar o arquivo: {exc}") from exc

            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location")
                response.close()
                response = None
                if not location or redirect_count >= MAX_REDIRECTS:
                    raise DownloadError("A URL excedeu o limite de redirecionamentos.")
                current_url = urljoin(current_url, location)
                _validate_url(current_url, resolve_host=False)
                continue

            if not 200 <= response.status_code < 300:
                try:
                    response.raise_for_status()
                except requests.RequestException as exc:
                    raise DownloadError(f"O servidor recusou o download: {exc}") from exc
                raise DownloadError(
                    f"O servidor retornou um status HTTP inesperado: {response.status_code}."
                )
            break
        else:
            raise DownloadError("A URL excedeu o limite de redirecionamentos.")

        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                announced_size = int(content_length)
            except ValueError as exc:
                raise DownloadError("O servidor retornou um tamanho de arquivo inválido.") from exc
            if announced_size < 0 or announced_size > MAX_DOWNLOAD_BYTES:
                raise DownloadError("O arquivo excede o limite de 50 MiB.")

        file_descriptor, temp_name = tempfile.mkstemp(
            prefix=".kael-download-",
            suffix=".part",
            dir=target.parent,
        )
        temp_path = Path(temp_name)
        total_bytes = 0
        started_at = time.monotonic()
        try:
            with os.fdopen(file_descriptor, "wb") as output:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if time.monotonic() - started_at > DOWNLOAD_TIMEOUT_SECONDS:
                        raise DownloadError("O download excedeu o limite de 120 segundos.")
                    if not chunk:
                        continue
                    total_bytes += len(chunk)
                    if total_bytes > MAX_DOWNLOAD_BYTES:
                        raise DownloadError("O arquivo excede o limite de 50 MiB.")
                    output.write(chunk)
        except requests.RequestException as exc:
            raise DownloadError(f"A conexão foi interrompida durante o download: {exc}") from exc

        if target.exists():
            raise DownloadError("O destino passou a existir durante o download; nenhum arquivo foi substituído.")
        try:
            output_descriptor = os.open(
                str(target),
                os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0),
                0o666,
            )
        except FileExistsError as exc:
            raise DownloadError("O destino passou a existir durante o download; nenhum arquivo foi substituído.") from exc
        except OSError as exc:
            raise DownloadError(f"Não foi possível criar o arquivo no destino: {exc}") from exc
        try:
            with os.fdopen(output_descriptor, "wb") as output, temp_path.open("rb") as source:
                shutil.copyfileobj(source, output)
        except OSError as exc:
            if target.exists():
                target.unlink()
            raise DownloadError(f"Não foi possível finalizar o arquivo no destino: {exc}") from exc
        return {
            "path": str(target),
            "bytes": total_bytes,
            "source": current_url,
        }
    finally:
        if response is not None:
            response.close()
        session.close()
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()

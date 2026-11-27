import socket
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.tool_registry import ToolRegistry
from tools import cmd_download
from tools.file_download import DownloadError, download_file, validate_download_request


class FakeResponse:
    def __init__(self, chunks=(), headers=None, status_code=200):
        self.chunks = list(chunks)
        self.headers = headers or {}
        self.status_code = status_code
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP failure")

    def iter_content(self, chunk_size):
        yield from self.chunks

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.trust_env = True
        self.closed = False

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)

    def close(self):
        self.closed = True


class FileDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.projects_root = Path(self.temp.name) / "projects"
        self.project = self.projects_root / "Game"
        self.project.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    @patch(
        "tools.file_download.socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )
    @patch("tools.file_download.requests.Session")
    def test_downloads_public_https_file_inside_project(self, session_factory, _dns):
        session = FakeSession([
            FakeResponse(
                chunks=[b"asset", b"-data"],
                headers={"Content-Length": "10"},
            )
        ])
        session_factory.return_value = session

        result = download_file(
            "https://assets.example/file.bin",
            "Assets/file.bin",
            self.project,
        )

        self.assertEqual(Path(result["path"]).read_bytes(), b"asset-data")
        self.assertEqual(result["bytes"], 10)
        self.assertEqual(len(session.calls), 1)
        self.assertFalse(session.calls[0][1]["allow_redirects"])
        self.assertFalse(session.trust_env)
        self.assertTrue(session.closed)
        self.assertEqual(list((self.project / "Assets").glob(".kael-download-*.part")), [])

    def test_rejects_non_https_private_hosts_and_paths_outside_project(self):
        for url, path in (
            ("http://assets.example/file.bin", "Assets/file.bin"),
            ("https://127.0.0.1/file.bin", "Assets/file.bin"),
            ("https://assets.example/file.bin", "../outside.bin"),
            ("https://assets.example/file.bin", "C:\\outside.bin"),
        ):
            with self.subTest(url=url, path=path), self.assertRaises(DownloadError):
                validate_download_request(
                    url,
                    path,
                    self.project,
                    resolve_host=False,
                )

    @patch(
        "tools.file_download.socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.4", 443))],
    )
    def test_rejects_public_hostname_that_resolves_to_private_address(self, _dns):
        with self.assertRaises(DownloadError):
            validate_download_request(
                "https://assets.example/file.bin",
                "Assets/file.bin",
                self.project,
            )

    @patch(
        "tools.file_download.socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )
    @patch("tools.file_download.requests.Session")
    def test_rejects_redirect_to_private_address(self, session_factory, _dns):
        session = FakeSession([
            FakeResponse(
                headers={"Location": "https://127.0.0.1/internal"},
                status_code=302,
            )
        ])
        session_factory.return_value = session

        with self.assertRaises(DownloadError):
            download_file(
                "https://assets.example/file.bin",
                "Assets/file.bin",
                self.project,
            )

        self.assertEqual(len(session.calls), 1)
        self.assertTrue(session.responses == [])
        self.assertEqual(list(self.project.rglob(".kael-download-*.part")), [])

    @patch(
        "tools.file_download.socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )
    @patch("tools.file_download.requests.Session")
    def test_rejects_oversized_stream_without_leaving_partial_file(
        self, session_factory, _dns
    ):
        session_factory.return_value = FakeSession([
            FakeResponse(chunks=[b"123", b"45"])
        ])

        with patch("tools.file_download.MAX_DOWNLOAD_BYTES", 4):
            with self.assertRaises(DownloadError):
                download_file(
                    "https://assets.example/file.bin",
                    "Assets/file.bin",
                    self.project,
                )

        self.assertFalse((self.project / "Assets" / "file.bin").exists())
        self.assertEqual(list((self.project / "Assets").glob(".kael-download-*.part")), [])

    def test_refuses_to_overwrite_existing_file(self):
        target = self.project / "existing.bin"
        target.write_bytes(b"keep")

        with self.assertRaises(DownloadError):
            validate_download_request(
                "https://assets.example/file.bin",
                "existing.bin",
                self.project,
                resolve_host=False,
            )
        self.assertEqual(target.read_bytes(), b"keep")

    def make_registry(self):
        policy = SimpleNamespace(
            is_within_projects_root=lambda path: self.projects_root.resolve()
            in Path(path).resolve().parents,
            requires_approval=lambda capability, path: False,
        )
        ctx = SimpleNamespace(project_path=self.project, permission_policy=policy)
        registry = ToolRegistry(ctx)
        registry.register_module(cmd_download)
        return ctx, registry

    def test_command_is_loaded_by_tool_auto_discovery(self):
        _ctx, registry = self.make_registry()

        registry.auto_discover()

        self.assertIn("/baixar_arquivo", registry.commands)

    def test_invalid_download_command_is_rejected_before_permission(self):
        _ctx, registry = self.make_registry()

        result = registry.dispatch(
            "/baixar_arquivo http://assets.example/file.bin Assets/file.bin"
        )

        self.assertEqual(result["status"], "error")
        self.assertNotIn("permission", result)

    @patch("tools.cmd_download.download_file")
    def test_command_requires_one_time_approval_and_downloads_only_afterward(
        self, download_mock
    ):
        ctx, registry = self.make_registry()
        download_mock.return_value = {
            "path": str(self.project / "Assets" / "file.bin"),
            "bytes": 7,
            "source": "https://assets.example/file.bin",
        }
        command = "/baixar_arquivo https://assets.example/file.bin Assets/file.bin"

        pending = registry.dispatch(command)

        self.assertEqual(pending["status"], "permission_required")
        self.assertIn("https://assets.example/file.bin", pending["permission"]["details"])
        self.assertIn("Assets/file.bin", pending["permission"]["details"])
        download_mock.assert_not_called()

        result = registry.resolve_approval(pending["permission"]["id"], True)

        self.assertEqual(result["status"], "success")
        self.assertIn("Assets/file.bin", result["response"])
        download_mock.assert_called_once_with(
            "https://assets.example/file.bin",
            "Assets/file.bin",
            self.project.resolve(),
        )
        self.assertIs(ctx.project_path, self.project)

    @patch("tools.cmd_download.download_file")
    def test_approval_is_bound_to_the_project_that_was_shown(self, download_mock):
        ctx, registry = self.make_registry()
        pending = registry.dispatch(
            "/baixar_arquivo https://assets.example/file.bin Assets/file.bin"
        )
        other_project = self.projects_root / "Other"
        other_project.mkdir()
        ctx.project_path = other_project

        result = registry.resolve_approval(pending["permission"]["id"], True)

        self.assertEqual(result["status"], "error")
        self.assertIn("projeto ativo mudou", result["response"])
        download_mock.assert_not_called()

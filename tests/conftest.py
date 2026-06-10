"""A stub Daily Problems API server (stdlib http.server) so the CLI can be
tested end-to-end over real HTTP without the Flask application.

It implements just enough of the JSON API: token login, problem listing, input
download, and submit (compares against a fixed answer hash)."""
from __future__ import annotations

import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

VALID_TOKEN = "test-token-123"
ANSWER = b"42\n"
ANSWER_HASH = hashlib.sha256(ANSWER).hexdigest()
INPUT_BYTES = b"5\n37\n"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence test output
        pass

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self) -> bool:
        return self.headers.get("Authorization") == f"Bearer {VALID_TOKEN}"

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        return json.loads(self.rfile.read(length))

    def do_POST(self) -> None:
        if self.path == "/api/login":
            data = self._read_json()
            if data.get("username") == "alice" and data.get("password") == "password1":
                self._send_json(200, {"token": VALID_TOKEN, "username": "alice"})
            else:
                self._send_json(401, {"error": "ユーザー名またはパスワードが違います。"})
            return
        if self.path == "/api/submit/1":
            if not self._authed():
                self._send_json(401, {"error": "認証が必要です。"})
                return
            submitted = (self._read_json().get("hash") or "").lower()
            ok = submitted == ANSWER_HASH
            self._send_json(200, {"correct": ok, "result": "AC" if ok else "WA"})
            return
        self._send_json(404, {"error": "not found"})

    def do_GET(self) -> None:
        if self.path == "/api/problems":
            if not self._authed():
                self._send_json(401, {"error": "認証が必要です。"})
                return
            self._send_json(200, {"problems": [
                {"id": 1, "date": "2026-06-01", "title": "Sum",
                 "difficulty": "Easy", "input_filename": "in.txt", "has_input": True},
            ]})
            return
        if self.path == "/api/inputs/1":
            if not self._authed():
                self._send_json(401, {"error": "認証が必要です。"})
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", 'attachment; filename="in.txt"')
            self.send_header("Content-Length", str(len(INPUT_BYTES)))
            self.end_headers()
            self.wfile.write(INPUT_BYTES)
            return
        self._send_json(404, {"error": "not found"})


@pytest.fixture
def stub_server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        httpd.shutdown()
        thread.join(timeout=5)

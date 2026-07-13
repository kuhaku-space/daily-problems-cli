"""A stub Daily Problems API server (stdlib http.server) so the CLI can be
tested end-to-end over real HTTP without the Flask application.

It implements just enough of the JSON API: bearer-token auth, problem listing,
input download, and submit (compares against a fixed answer hash). Tokens are
issued out-of-band (there is no password-login endpoint), so tests use
``VALID_TOKEN`` directly."""
from __future__ import annotations

import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

VALID_TOKEN = "test-token-123"
ANSWER = b"42\n"
ANSWER_HASH = hashlib.sha256(ANSWER).hexdigest()
TOKEN_ANSWER = b"42"
TOKEN_ANSWER_HASH = hashlib.sha256(TOKEN_ANSWER).hexdigest()
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
            self._send_json(410, {"error": "パスワードによるAPIトークン発行は廃止済みです。"})
            return
        if self.path in {"/api/submit/1", "/api/submit/2"}:
            if not self._authed():
                self._send_json(401, {"error": "認証が必要です。"})
                return
            submitted = (self._read_json().get("hash") or "").lower()
            expected = ANSWER_HASH if self.path.endswith("/1") else TOKEN_ANSWER_HASH
            ok = submitted == expected
            self._send_json(200, {"correct": ok, "result": "AC" if ok else "WA"})
            return
        if self.path == "/api/problems":  # create
            if not self._authed():
                self._send_json(401, {"error": "認証が必要です。"})
                return
            data = self._read_json()
            self._send_json(201, {
                "id": 7,
                "title": data.get("title"),
                "difficulty": data.get("difficulty") or "Medium",
                "status": "scheduled" if data.get("date") else "queued",
                "date": data.get("date") or None,
                "input_filename": data.get("input_filename"),
                "has_input": bool(data.get("input")),
            })
            return
        if self.path == "/api/problems/7/edit":
            if not self._authed():
                self._send_json(401, {"error": "認証が必要です。"})
                return
            data = self._read_json()
            self._send_json(200, {
                "id": 7,
                "title": data.get("title") or "Sum",
                "difficulty": data.get("difficulty") or "Medium",
                "status": "queued" if data.get("date") == "" else "scheduled",
                "date": data.get("date") or None,
                "input_filename": None if data.get("remove_input") else "in.txt",
                "has_input": not data.get("remove_input"),
            })
            return
        if self.path == "/api/problems/7/delete":
            if not self._authed():
                self._send_json(401, {"error": "認証が必要です。"})
                return
            self._send_json(200, {"deleted": True})
            return
        self._send_json(404, {"error": "not found"})

    def do_GET(self) -> None:
        if self.path == "/api/problems":
            if not self._authed():
                self._send_json(401, {"error": "認証が必要です。"})
                return
            self._send_json(200, {"problems": [
                {"id": 1, "date": "2026-06-01", "title": "Sum",
                 "difficulty": "Easy", "input_filename": "in.txt", "has_input": True,
                 "output_formatter": "identity-v1"},
                {"id": 2, "date": "2026-06-02", "title": "Token Sum",
                 "difficulty": "Easy", "input_filename": None, "has_input": False,
                 "output_formatter": "tokens-v1"},
            ]})
            return
        if self.path == "/api/problems/mine":
            if not self._authed():
                self._send_json(401, {"error": "認証が必要です。"})
                return
            self._send_json(200, {"problems": [
                {"id": 7, "title": "Draft", "difficulty": "Hard", "status": "queued",
                 "date": None, "input_filename": None, "has_input": False,
                 "output_formatter": "tokens-v1"},
                {"id": 1, "title": "Sum", "difficulty": "Easy", "status": "published",
                 "date": "2026-06-01", "input_filename": "in.txt", "has_input": True,
                 "output_formatter": "identity-v1"},
            ]})
            return
        if self.path.startswith("/api/problems/open-dates/next"):
            if not self._authed():
                self._send_json(401, {"error": "認証が必要です。"})
                return
            self._send_json(200, {
                "from": "2026-07-01", "count": 2,
                "dates": ["2026-07-03", "2026-07-05"],
            })
            return
        if self.path.startswith("/api/problems/open-dates"):
            if not self._authed():
                self._send_json(401, {"error": "認証が必要です。"})
                return
            self._send_json(200, {"month": "2026-07", "dates": ["2026-07-03", "2026-07-05"]})
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

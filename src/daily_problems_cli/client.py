"""Minimal HTTP client for the daily JSON API, over urllib (no dependencies)."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request


class ApiError(Exception):
    """A non-2xx API response (or transport failure). ``status`` is None for
    transport errors."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class Client:
    def __init__(self, server: str, token: str = "") -> None:
        self.server = server.rstrip("/")
        self.token = token

    def _request(self, method: str, path: str, *, json_body=None) -> tuple[int, bytes, dict]:
        url = self.server + path
        data = None
        headers = {}
        if json_body is not None:
            data = json.dumps(json_body).encode()
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(), dict(exc.headers)
        except urllib.error.URLError as exc:
            raise ApiError(f"サーバーに接続できません ({self.server}): {exc.reason}") from exc

    def _json(self, method: str, path: str, *, json_body=None) -> dict:
        status, body, _ = self._request(method, path, json_body=json_body)
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            raise ApiError(f"不正な応答 (HTTP {status})", status)
        if status >= 400:
            message = payload.get("error") if isinstance(payload, dict) else None
            raise ApiError(message or f"HTTP {status}", status)
        return payload

    def login(self, username: str, password: str, label: str = "cli") -> dict:
        return self._json(
            "POST", "/api/login",
            json_body={"username": username, "password": password, "label": label},
        )

    def problems(self) -> list[dict]:
        return self._json("GET", "/api/problems").get("problems", [])

    def submit(self, problem_id: int, sha256: str, code: str = "") -> dict:
        return self._json(
            "POST", f"/api/submit/{problem_id}",
            json_body={"hash": sha256, "code": code},
        )

    # --- 作問者向け (authoring) -------------------------------------------

    def create_problem(self, payload: dict) -> dict:
        """Create a problem. ``payload`` carries only the keys the caller set."""
        return self._json("POST", "/api/problems", json_body=payload)

    def authored_problems(self) -> list[dict]:
        """List problems authored by the current user (all statuses)."""
        return self._json("GET", "/api/problems/mine").get("problems", [])

    def update_problem(self, problem_id: int, payload: dict) -> dict:
        """Partially update a problem; ``payload`` holds only changed keys."""
        return self._json("POST", f"/api/problems/{problem_id}/edit", json_body=payload)

    def delete_problem(self, problem_id: int) -> dict:
        return self._json("POST", f"/api/problems/{problem_id}/delete")

    def open_dates(self, month: str = "") -> dict:
        """Dates in ``month`` (YYYY-MM, defaults to current) with no problem."""
        query = urllib.parse.urlencode({"month": month}) if month else ""
        path = "/api/problems/open-dates" + (f"?{query}" if query else "")
        return self._json("GET", path)

    def next_open_dates(self, from_date: str = "", count: int | None = None) -> dict:
        """The next open dates starting at ``from_date`` (default today)."""
        params = {}
        if from_date:
            params["from"] = from_date
        if count is not None:
            params["count"] = count
        query = urllib.parse.urlencode(params)
        path = "/api/problems/open-dates/next" + (f"?{query}" if query else "")
        return self._json("GET", path)

    def download_input(self, problem_id: int) -> tuple[bytes, str]:
        """Return (content, suggested_filename) for a problem's input file."""
        status, body, headers = self._request("GET", f"/api/inputs/{problem_id}")
        if status >= 400:
            try:
                message = json.loads(body).get("error")
            except (json.JSONDecodeError, AttributeError):
                message = None
            raise ApiError(message or f"HTTP {status}", status)
        disposition = headers.get("Content-Disposition", "")
        filename = ""
        marker = 'filename="'
        if marker in disposition:
            filename = disposition.split(marker, 1)[1].split('"', 1)[0]
        return body, filename

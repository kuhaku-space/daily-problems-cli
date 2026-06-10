"""Persisted CLI config: server URL and API token.

Lives at ``$DAILY_CONFIG`` if set, else ``$XDG_CONFIG_HOME/daily/config.toml``
(default ``~/.config/daily/config.toml``). Read via stdlib ``tomllib``; written
by hand (the standard library has no TOML writer) — only two string keys, so a
trivial serializer is enough and we don't take a dependency."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


def config_path() -> Path:
    override = os.environ.get("DAILY_CONFIG")
    if override:
        return Path(override)
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "daily" / "config.toml"


@dataclass
class Config:
    server: str = ""
    token: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.server and self.token)


def load() -> Config:
    path = config_path()
    if not path.is_file():
        return Config()
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    return Config(server=str(data.get("server", "")), token=str(data.get("token", "")))


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def save(config: Config) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (
        f'server = "{_toml_escape(config.server)}"\n'
        f'token = "{_toml_escape(config.token)}"\n'
    )
    path.write_text(body, encoding="utf-8")
    # Token is a credential — keep the file private (best-effort; no-op on Windows).
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path

"""Unit tests for the CLI config store. No network, no server."""
from __future__ import annotations

import stat

from daily_problems_cli import config as cfg


def test_config_path_uses_daily_config_env(monkeypatch, tmp_path):
    target = tmp_path / "custom.toml"
    monkeypatch.setenv("DAILY_CONFIG", str(target))
    assert cfg.config_path() == target


def test_config_path_falls_back_to_xdg(monkeypatch, tmp_path):
    monkeypatch.delenv("DAILY_CONFIG", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert cfg.config_path() == tmp_path / "daily" / "config.toml"


def test_load_missing_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("DAILY_CONFIG", str(tmp_path / "nope.toml"))
    config = cfg.load()
    assert config.server == "" and config.token == ""
    assert not config.configured


def test_save_then_load_roundtrip(monkeypatch, tmp_path):
    path = tmp_path / "config.toml"
    monkeypatch.setenv("DAILY_CONFIG", str(path))
    saved_path = cfg.save(cfg.Config(server="https://x.example.com", token="abc123"))
    assert saved_path == path
    loaded = cfg.load()
    assert loaded.server == "https://x.example.com"
    assert loaded.token == "abc123"
    assert loaded.configured


def test_save_is_private(monkeypatch, tmp_path):
    path = tmp_path / "config.toml"
    monkeypatch.setenv("DAILY_CONFIG", str(path))
    cfg.save(cfg.Config(server="s", token="t"))
    mode = stat.S_IMODE(path.stat().st_mode)
    # Owner-only (best effort; on platforms without chmod this may differ).
    assert mode & 0o077 == 0


def test_save_escapes_quotes(monkeypatch, tmp_path):
    """A token or server containing a quote must survive the round-trip."""
    path = tmp_path / "config.toml"
    monkeypatch.setenv("DAILY_CONFIG", str(path))
    cfg.save(cfg.Config(server='http://a"b', token='to"ken'))
    loaded = cfg.load()
    assert loaded.server == 'http://a"b'
    assert loaded.token == 'to"ken'

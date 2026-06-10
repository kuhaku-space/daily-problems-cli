"""End-to-end CLI tests against a stub HTTP API (conftest.stub_server)."""
from __future__ import annotations

import pytest

from conftest import ANSWER_HASH, INPUT_BYTES
from daily_problems_cli import config as cli_config
from daily_problems_cli.__main__ import main


@pytest.fixture(autouse=True)
def _isolated_config(monkeypatch, tmp_path):
    monkeypatch.setenv("DAILY_CONFIG", str(tmp_path / "config.toml"))


def _login(server: str) -> int:
    return main(["login", "--server", server, "--username", "alice", "--password", "password1"])


def test_login_persists_token(stub_server, capsys):
    assert _login(stub_server) == 0
    out = capsys.readouterr().out
    assert "ログインしました" in out
    saved = cli_config.load()
    assert saved.server == stub_server
    assert saved.token


def test_login_wrong_password_errors(stub_server, capsys):
    rc = main(["login", "--server", stub_server, "--username", "alice", "--password", "nope"])
    assert rc == 2
    assert "エラー" in capsys.readouterr().err


def test_list(stub_server, capsys):
    _login(stub_server)
    capsys.readouterr()
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert "Sum" in out and "Easy" in out


def test_get_downloads_input(stub_server, tmp_path, capsys):
    _login(stub_server)
    dest = tmp_path / "in.txt"
    assert main(["get", "1", "-o", str(dest)]) == 0
    assert dest.read_bytes() == INPUT_BYTES


def test_submit_wrong_then_correct(stub_server, tmp_path, capsys):
    _login(stub_server)
    capsys.readouterr()

    wrong = tmp_path / "wrong.txt"
    wrong.write_bytes(b"nope\n")
    assert main(["submit", "1", str(wrong)]) == 1
    assert "WA" in capsys.readouterr().out

    correct = tmp_path / "ok.txt"
    correct.write_bytes(b"42\n")
    assert main(["submit", "1", str(correct)]) == 0
    out = capsys.readouterr().out
    assert "AC" in out
    assert ANSWER_HASH in out  # the computed hash is shown


def test_commands_require_login(capsys):
    """With no stored config, auth-needing commands fail cleanly (exit 2)."""
    assert main(["list"]) == 2
    assert "daily login" in capsys.readouterr().err


def test_submit_missing_file(stub_server, capsys):
    _login(stub_server)
    capsys.readouterr()
    assert main(["submit", "1", "/no/such/file.txt"]) == 2
    assert "見つかりません" in capsys.readouterr().err


def test_connection_error_is_clean(capsys, monkeypatch, tmp_path):
    """A dead server surfaces a friendly error, not a traceback."""
    monkeypatch.setenv("DAILY_CONFIG", str(tmp_path / "config.toml"))
    cli_config.save(cli_config.Config(server="http://127.0.0.1:1", token="x"))
    assert main(["list"]) == 2
    assert "接続できません" in capsys.readouterr().err

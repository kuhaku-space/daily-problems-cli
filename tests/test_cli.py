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


def test_download_alias_downloads_input(stub_server, tmp_path, capsys):
    _login(stub_server)
    dest = tmp_path / "downloaded.txt"
    assert main(["download", "1", "-o", str(dest)]) == 0
    assert dest.read_bytes() == INPUT_BYTES


def test_dl_alias_downloads_input(stub_server, tmp_path, capsys):
    _login(stub_server)
    dest = tmp_path / "dl.txt"
    assert main(["dl", "1", "-o", str(dest)]) == 0
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


def test_create_with_answer_file(stub_server, tmp_path, capsys):
    _login(stub_server)
    capsys.readouterr()
    answer = tmp_path / "expected.txt"
    answer.write_bytes(b"42\n")
    statement = tmp_path / "statement.md"
    statement.write_text("2 数の和を求めよ。", encoding="utf-8")
    rc = main([
        "create", "--title", "Sum", "--statement-file", str(statement),
        "--answer", str(answer), "--difficulty", "Easy", "--date", "2026-07-03",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "作成しました" in out
    assert "#7" in out and "Sum" in out and "2026-07-03 (金)" in out  # 曜日付き


def test_create_requires_answer(stub_server, capsys):
    _login(stub_server)
    capsys.readouterr()
    rc = main(["create", "--title", "X", "--statement", "hi"])
    assert rc == 2
    assert "想定出力" in capsys.readouterr().err


def test_create_rejects_bad_hash(stub_server, capsys):
    _login(stub_server)
    capsys.readouterr()
    rc = main(["create", "--title", "X", "--statement", "hi", "--answer-sha256", "zzz"])
    assert rc == 2
    assert "16 進数" in capsys.readouterr().err


def test_mine_lists_all_statuses(stub_server, capsys):
    _login(stub_server)
    capsys.readouterr()
    assert main(["mine"]) == 0
    out = capsys.readouterr().out
    assert "キュー" in out and "公開" in out  # 状態の日本語表記
    assert "ID" in out and "タイトル" in out  # ヘッダ行
    assert "Draft" in out and "Sum" in out
    assert "—" in out  # a queued problem has no date


def test_edit_requires_a_change(stub_server, capsys):
    _login(stub_server)
    capsys.readouterr()
    assert main(["edit", "7"]) == 2
    assert "1 つ以上" in capsys.readouterr().err


def test_edit_queue_reverts_date(stub_server, capsys):
    _login(stub_server)
    capsys.readouterr()
    assert main(["edit", "7", "--queue"]) == 0
    out = capsys.readouterr().out
    assert "更新しました" in out and "queued" in out


def test_delete_with_yes(stub_server, capsys):
    _login(stub_server)
    capsys.readouterr()
    assert main(["rm", "7", "--yes"]) == 0
    assert "削除しました" in capsys.readouterr().out


def test_delete_aborts_on_no(stub_server, capsys, monkeypatch):
    _login(stub_server)
    capsys.readouterr()
    monkeypatch.setattr("builtins.input", lambda *a: "n")
    assert main(["rm", "7"]) == 1
    assert "中止" in capsys.readouterr().out


def test_open_dates_defaults_to_next(stub_server, capsys):
    _login(stub_server)
    capsys.readouterr()
    assert main(["open-dates", "--count", "2"]) == 0
    out = capsys.readouterr().out
    assert "2026-07-01 (水) 以降" in out and "2026-07-05 (日)" in out


def test_open_dates_month(stub_server, capsys):
    _login(stub_server)
    capsys.readouterr()
    assert main(["open-dates", "--month", "2026-07"]) == 0
    out = capsys.readouterr().out
    assert "2026-07" in out and "2026-07-03" in out


def test_connection_error_is_clean(capsys, monkeypatch, tmp_path):
    """A dead server surfaces a friendly error, not a traceback."""
    monkeypatch.setenv("DAILY_CONFIG", str(tmp_path / "config.toml"))
    cli_config.save(cli_config.Config(server="http://127.0.0.1:1", token="x"))
    assert main(["list"]) == 2
    assert "接続できません" in capsys.readouterr().err

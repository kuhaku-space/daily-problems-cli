"""``daily`` CLI entry point.

Commands:
  daily login [--server URL] [--username U] [--label L]   authenticate, store token
  daily list                                              list today's problems
  daily get <id> [-o DIR|FILE]                            download a problem's input
  daily download <id> [-o DIR|FILE]                       same as get
  daily dl <id> [-o DIR|FILE]                             same as get
  daily submit <id> <outfile> [--code FILE]               hash & submit an output file

Authoring commands (作問者用):
  daily create --title T (--statement TEXT|--statement-file F) \
               (--answer FILE|--answer-sha256 HEX) [--input FILE] \
               [--difficulty D] [--date YYYY-MM-DD] [--editorial(-file)]   create a problem
  daily mine                                              list your authored problems
  daily edit <id> [same options as create, all optional] [--queue] [--remove-input]  update
  daily rm <id> [--yes]                                   delete a queued/future problem
  daily open-dates [--from YYYY-MM-DD] [--count N] [--month YYYY-MM]  free dates (next by default)
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import sys
import unicodedata
from datetime import date
from pathlib import Path

from . import config as cfg
from .client import ApiError, Client


DIFFICULTIES = ["Easy", "Medium", "Hard", "Expert"]
WEEKDAYS_JA = ["月", "火", "水", "木", "金", "土", "日"]  # date.weekday(): 0=月
STATUS_LABELS = {"published": "公開", "scheduled": "予約", "queued": "キュー"}


def _with_weekday(date_str: str) -> str:
    """``"2026-07-03"`` -> ``"2026-07-03 (金)"``; unparseable input is returned as-is."""
    try:
        d = date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return date_str
    return f"{date_str} ({WEEKDAYS_JA[d.weekday()]})"


def _display_width(text: str) -> int:
    """Terminal column count, counting East-Asian wide/fullwidth chars as 2."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _display_width(text))


def _print_table(header: list[str], rows: list[list[str]]) -> None:
    """Print rows as columns aligned on display width, with a header rule."""
    widths = [max(_display_width(r[i]) for r in [header, *rows]) for i in range(len(header))]
    print("  ".join(_pad(cell, widths[i]) for i, cell in enumerate(header)).rstrip())
    print("  ".join("-" * widths[i] for i in range(len(header))))
    for row in rows:
        print("  ".join(_pad(cell, widths[i]) for i, cell in enumerate(row)).rstrip())


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_text(path: str) -> str:
    file = Path(path)
    if not file.is_file():
        raise ApiError(f"ファイルが見つかりません: {file}")
    return file.read_text(encoding="utf-8")


def _resolve_answer_hash(answer_file: str | None, answer_sha256: str | None) -> str | None:
    """Turn the two answer flags into a hash, or None if neither was given.

    ``--answer`` names an expected-output file whose sha256 we compute (like
    ``submit``); ``--answer-sha256`` supplies the digest directly."""
    if answer_file and answer_sha256:
        raise ApiError("--answer と --answer-sha256 は同時に指定できません。")
    if answer_file:
        file = Path(answer_file)
        if not file.is_file():
            raise ApiError(f"想定出力ファイルが見つかりません: {file}")
        return _sha256_file(file)
    if answer_sha256:
        digest = answer_sha256.strip().lower()
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ApiError("--answer-sha256 は 64 桁の 16 進数で指定してください。")
        return digest
    return None


def _statement(inline: str | None, file: str | None, *, field: str) -> str | None:
    if inline is not None and file is not None:
        raise ApiError(f"--{field} と --{field}-file は同時に指定できません。")
    if file is not None:
        return _read_text(file)
    return inline


def _client_from_config(config: cfg.Config) -> Client:
    if not config.configured:
        raise ApiError("先に `daily login` でログインしてください。")
    return Client(config.server, config.token)


def cmd_login(args) -> int:
    server = (args.server or cfg.load().server or "http://127.0.0.1:8000").rstrip("/")
    username = args.username or input("ユーザー名: ").strip()
    password = args.password or getpass.getpass("パスワード: ")
    client = Client(server)
    result = client.login(username, password, label=args.label)
    saved = cfg.save(cfg.Config(server=server, token=result["token"]))
    print(f"{result['username']} としてログインしました。トークンを {saved} に保存しました。")
    return 0


def cmd_list(args) -> int:
    client = _client_from_config(cfg.load())
    problems = client.problems()
    if not problems:
        print("公開中の問題はありません。")
        return 0
    width = max(len(str(p["id"])) for p in problems)
    for p in problems:
        flag = "" if p["has_input"] else "  (入力なし)"
        date_str = _with_weekday(p["date"])
        print(f"{str(p['id']).rjust(width)}  {date_str}  [{p['difficulty']}]  {p['title']}{flag}")
    return 0


def cmd_get(args) -> int:
    client = _client_from_config(cfg.load())
    content, suggested = client.download_input(args.problem_id)
    out = Path(args.output) if args.output else Path(suggested or f"input_{args.problem_id}.txt")
    if out.is_dir():
        out = out / (suggested or f"input_{args.problem_id}.txt")
    out.write_bytes(content)
    print(f"入力を {out} に保存しました ({len(content)} bytes)。")
    return 0


def cmd_submit(args) -> int:
    client = _client_from_config(cfg.load())
    outfile = Path(args.outfile)
    if not outfile.is_file():
        raise ApiError(f"出力ファイルが見つかりません: {outfile}")
    digest = _sha256_file(outfile)
    code = ""
    if args.code:
        code = Path(args.code).read_text(encoding="utf-8", errors="replace")
    print(f"sha256({outfile.name}) = {digest}")
    result = client.submit(args.problem_id, digest, code=code)
    verdict = result["result"]
    print(f"=> {verdict}" + (" ✅" if result["correct"] else " ❌"))
    return 0 if result["correct"] else 1


def _print_authored(p: dict) -> None:
    date_str = _with_weekday(p["date"]) if p.get("date") else "(未定・キュー)"
    flag = "" if p.get("has_input") else "  (入力なし)"
    print(f"#{p['id']}  [{p['status']}]  {date_str}  [{p['difficulty']}]  {p['title']}{flag}")


def cmd_create(args) -> int:
    client = _client_from_config(cfg.load())
    title = args.title or input("タイトル: ").strip()
    statement = _statement(args.statement, args.statement_file, field="statement")
    if not statement:
        raise ApiError("問題文を --statement か --statement-file で指定してください。")
    answer = _resolve_answer_hash(args.answer, args.answer_sha256)
    if not answer:
        raise ApiError("想定出力を --answer (ファイル) か --answer-sha256 で指定してください。")

    payload: dict = {"title": title, "statement": statement, "answer_sha256": answer}
    if args.difficulty:
        payload["difficulty"] = args.difficulty
    if args.date:
        payload["date"] = args.date
    editorial = _statement(args.editorial, args.editorial_file, field="editorial")
    if editorial is not None:
        payload["editorial"] = editorial
    if args.input:
        payload["input"] = _read_text(args.input)
        payload["input_filename"] = args.input_filename or Path(args.input).name

    created = client.create_problem(payload)
    print("問題を作成しました。")
    _print_authored(created)
    return 0


def cmd_mine(args) -> int:
    client = _client_from_config(cfg.load())
    problems = client.authored_problems()
    if not problems:
        print("作成した問題はありません。")
        return 0
    rows = []
    for p in problems:
        rows.append([
            f"#{p['id']}",
            STATUS_LABELS.get(p.get("status"), p.get("status") or ""),
            _with_weekday(p["date"]) if p.get("date") else "—",
            p.get("difficulty") or "",
            "あり" if p.get("has_input") else "なし",
            p["title"],
        ])
    _print_table(["ID", "状態", "公開日", "難易度", "入力", "タイトル"], rows)
    return 0


def cmd_edit(args) -> int:
    client = _client_from_config(cfg.load())
    payload: dict = {}
    if args.title is not None:
        payload["title"] = args.title
    statement = _statement(args.statement, args.statement_file, field="statement")
    if statement is not None:
        payload["statement"] = statement
    if args.difficulty:
        payload["difficulty"] = args.difficulty
    answer = _resolve_answer_hash(args.answer, args.answer_sha256)
    if answer:
        payload["answer_sha256"] = answer
    editorial = _statement(args.editorial, args.editorial_file, field="editorial")
    if editorial is not None:
        payload["editorial"] = editorial
    if args.queue:
        if args.date:
            raise ApiError("--date と --queue は同時に指定できません。")
        payload["date"] = ""  # 空文字でリリースキューに戻す
    elif args.date:
        payload["date"] = args.date
    if args.remove_input:
        if args.input:
            raise ApiError("--input と --remove-input は同時に指定できません。")
        payload["remove_input"] = True
    elif args.input:
        payload["input"] = _read_text(args.input)
        payload["input_filename"] = args.input_filename or Path(args.input).name

    if not payload:
        raise ApiError("変更する項目を 1 つ以上指定してください。")
    updated = client.update_problem(args.problem_id, payload)
    print("問題を更新しました。")
    _print_authored(updated)
    return 0


def cmd_delete(args) -> int:
    client = _client_from_config(cfg.load())
    if not args.yes:
        answer = input(f"問題 #{args.problem_id} を削除します。よろしいですか? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("中止しました。")
            return 1
    result = client.delete_problem(args.problem_id)
    if result.get("deleted"):
        print(f"問題 #{args.problem_id} を削除しました。")
        return 0
    print(f"問題 #{args.problem_id} を削除できませんでした。", file=sys.stderr)
    return 1


def cmd_open_dates(args) -> int:
    client = _client_from_config(cfg.load())
    if args.month:  # 月指定があれば当該月の空き日程、なければ直近を表示
        result = client.open_dates(month=args.month)
        dates = result.get("dates", [])
        label = result.get("month", "")
    else:
        result = client.next_open_dates(from_date=args.from_date or "", count=args.count)
        dates = result.get("dates", [])
        label = f"{_with_weekday(result.get('from', ''))} 以降"
    if not dates:
        print(f"{label}: 空き日程はありません。")
        return 0
    print(f"{label} の空き日程:")
    for d in dates:
        print(f"  {_with_weekday(d)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="daily", description="Daily Problems CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_login = sub.add_parser("login", help="ログインしてトークンを保存")
    p_login.add_argument("--server", help="サーバーURL (例: http://127.0.0.1:8000)")
    p_login.add_argument("--username", help="ユーザー名 (省略時はプロンプト)")
    p_login.add_argument("--password", help="パスワード (省略時はプロンプト)")
    p_login.add_argument("--label", default="cli", help="トークンのラベル")
    p_login.set_defaults(func=cmd_login)

    p_list = sub.add_parser("list", help="公開中の問題一覧")
    p_list.set_defaults(func=cmd_list)

    p_get = sub.add_parser("get", help="入力ファイルをダウンロード")
    p_get.add_argument("problem_id", type=int)
    p_get.add_argument("-o", "--output", help="保存先のファイルまたはディレクトリ")
    p_get.set_defaults(func=cmd_get)

    p_download = sub.add_parser("download", help="入力ファイルをダウンロード")
    p_download.add_argument("problem_id", type=int)
    p_download.add_argument("-o", "--output", help="保存先のファイルまたはディレクトリ")
    p_download.set_defaults(func=cmd_get)

    p_dl = sub.add_parser("dl", help="入力ファイルをダウンロード")
    p_dl.add_argument("problem_id", type=int)
    p_dl.add_argument("-o", "--output", help="保存先のファイルまたはディレクトリ")
    p_dl.set_defaults(func=cmd_get)

    p_submit = sub.add_parser("submit", help="出力ファイルのハッシュを計算して提出")
    p_submit.add_argument("problem_id", type=int)
    p_submit.add_argument("outfile", help="提出する出力ファイル")
    p_submit.add_argument("--code", help="一緒に保存するソースコードのファイル")
    p_submit.set_defaults(func=cmd_submit)

    # --- 作問者向けサブコマンド ------------------------------------------

    def add_content_args(p) -> None:
        """Flags shared by create/edit for problem content."""
        p.add_argument("--title", help="問題タイトル")
        p.add_argument("--statement", help="問題文 (インライン)")
        p.add_argument("--statement-file", help="問題文を読み込むファイル")
        p.add_argument("--difficulty", choices=DIFFICULTIES, help="難易度")
        p.add_argument("--answer", help="想定出力ファイル (sha256 を計算)")
        p.add_argument("--answer-sha256", help="想定出力の sha256 ハッシュ (64桁)")
        p.add_argument("--input", help="入力ファイル (内容を送信)")
        p.add_argument("--input-filename", help="ダウンロード時のファイル名 (既定: 入力ファイル名)")
        p.add_argument("--editorial", help="解説 (インライン)")
        p.add_argument("--editorial-file", help="解説を読み込むファイル")
        p.add_argument("--date", help="公開日 YYYY-MM-DD (省略時はリリースキュー)")

    p_create = sub.add_parser("create", help="問題を作成 (作問者用)")
    add_content_args(p_create)
    p_create.set_defaults(func=cmd_create)

    p_new = sub.add_parser("new", help="問題を作成 (create のエイリアス)")
    add_content_args(p_new)
    p_new.set_defaults(func=cmd_create)

    p_mine = sub.add_parser("mine", help="自分が作成した問題一覧 (作問者用)")
    p_mine.set_defaults(func=cmd_mine)

    p_edit = sub.add_parser("edit", help="問題を更新 (作問者用)")
    p_edit.add_argument("problem_id", type=int)
    add_content_args(p_edit)
    p_edit.add_argument("--queue", action="store_true", help="公開日を外してリリースキューに戻す")
    p_edit.add_argument("--remove-input", action="store_true", help="入力ファイルを削除")
    p_edit.set_defaults(func=cmd_edit)

    p_rm = sub.add_parser("rm", help="問題を削除 (キュー/未来日のみ・作問者用)")
    p_rm.add_argument("problem_id", type=int)
    p_rm.add_argument("-y", "--yes", action="store_true", help="確認プロンプトをスキップ")
    p_rm.set_defaults(func=cmd_delete)

    p_delete = sub.add_parser("delete", help="問題を削除 (rm のエイリアス)")
    p_delete.add_argument("problem_id", type=int)
    p_delete.add_argument("-y", "--yes", action="store_true", help="確認プロンプトをスキップ")
    p_delete.set_defaults(func=cmd_delete)

    p_dates = sub.add_parser(
        "open-dates",
        help="空き日程 (既定: 直近の空き日程。--month で月単位表示・作問者用)",
    )
    p_dates.add_argument("--month", help="対象月 YYYY-MM を月単位で表示 (省略時は直近)")
    p_dates.add_argument("--from", dest="from_date", help="直近表示の起点日 YYYY-MM-DD (既定: 今日)")
    p_dates.add_argument("--count", type=int, help="直近表示する日数 (1-366, 既定: 7)")
    p_dates.set_defaults(func=cmd_open_dates)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ApiError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

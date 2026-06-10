"""``daily`` CLI entry point.

Commands:
  daily login [--server URL] [--username U] [--label L]   authenticate, store token
  daily list                                              list today's problems
  daily get <id> [-o DIR|FILE]                            download a problem's input
  daily submit <id> <outfile> [--code FILE]               hash & submit an output file
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import sys
from pathlib import Path

from . import config as cfg
from .client import ApiError, Client


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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
        print(f"{str(p['id']).rjust(width)}  {p['date']}  [{p['difficulty']}]  {p['title']}{flag}")
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

    p_submit = sub.add_parser("submit", help="出力ファイルのハッシュを計算して提出")
    p_submit.add_argument("problem_id", type=int)
    p_submit.add_argument("outfile", help="提出する出力ファイル")
    p_submit.add_argument("--code", help="一緒に保存するソースコードのファイル")
    p_submit.set_defaults(func=cmd_submit)

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

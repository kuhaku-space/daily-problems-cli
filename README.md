# daily — Daily Problems CLI

[Daily Problems](https://github.com/izulabo-ou/app-daily-problems) の入力ダウンロードと提出をコマンドラインから行うクライアントです。標準ライブラリのみで動き、追加の依存はありません。

## インストール

Python 3.11 以上が必要です。[uv](https://docs.astral.sh/uv/) を使うのが簡単です。

```bash
uv tool install "git+https://github.com/kuhaku-space/daily-problems-cli"
```

pip でも入れられます。

```bash
pip install "git+https://github.com/kuhaku-space/daily-problems-cli"
```

インストールせずに試すこともできます。

```bash
uvx --from "git+https://github.com/kuhaku-space/daily-problems-cli" daily --help
```

### Nix flake で使う

このリポジトリは flake になっているので、Nix だけでビルド・実行できます。

```bash
# とりあえず実行する
nix run github:kuhaku-space/daily-problems-cli -- --help

# プロファイルにインストールする
nix profile install github:kuhaku-space/daily-problems-cli
```

他の flake の `devShell` に追加したい場合は、入力として取り込み、その
`packages.<system>.default` をシェルに含めます。

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    daily-problems-cli.url = "github:kuhaku-space/daily-problems-cli";
    # nixpkgs を共有して重複ダウンロードを避ける
    daily-problems-cli.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, daily-problems-cli }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
    in {
      devShells.${system}.default = pkgs.mkShell {
        packages = [
          daily-problems-cli.packages.${system}.default
        ];
      };
    };
}
```

オーバーレイ経由で `pkgs.daily-problems-cli` として取り込むこともできます。

```nix
let
  pkgs = import nixpkgs {
    inherit system;
    overlays = [ daily-problems-cli.overlays.default ];
  };
in
pkgs.mkShell {
  packages = [ pkgs.daily-problems-cli ];
}
```

## 使い方

```bash
daily login --server https://your-daily-problems.example.com   # ログインしてトークンを保存
daily list                                                     # 公開中の問題一覧
daily get 12 -o input.txt                                      # 問題12の入力をダウンロード
daily download 12 -o input.txt                                 # get と同じ
daily dl 12 -o input.txt                                       # get と同じ
daily submit 12 output.txt                                     # output.txt の SHA-256 を計算して提出
```

- `login` はトークンを発行して設定ファイルに保存します。ユーザー名・パスワードは省略するとプロンプトで尋ねます。
- `submit` は出力ファイルの SHA-256 を CLI 側で計算して送ります。正解(AC)なら終了コード 0、不正解(WA)なら 1。
- トークンは Daily Problems のプロフィールページ「API トークン」からも発行・失効できます。

### 作問者向けコマンド

問題の作成・管理を行うコマンドです（利用には作問権限が必要です）。

```bash
# 問題を作成する。問題文はファイルから、想定出力は SHA-256 を CLI 側で計算
daily create --title "Two Sum" \
             --statement-file statement.md \
             --answer expected_output.txt \
             --input sample_input.txt \
             --difficulty Easy \
             --date 2026-07-03            # --date を省くとリリースキューに入る

daily mine                                # 自分が作成した問題を全ステータス表示
daily edit 12 --difficulty Hard           # 一部だけ更新（指定した項目のみ変更）
daily edit 12 --queue                     # 公開日を外してリリースキューに戻す
daily edit 12 --remove-input              # 入力ファイルを削除
daily rm 12                               # 削除（確認あり。-y で確認をスキップ）
daily open-dates                          # 今日以降の直近の空き日程（既定）
daily open-dates --count 14               # 今日以降の空き日程を最大14件
daily open-dates --from 2026-08-01        # 起点日を指定
daily open-dates --month 2026-08          # 指定月を月単位で表示
```

- `create` / `edit` の想定出力は `--answer <ファイル>`（SHA-256 を計算）か `--answer-sha256 <64桁の16進>` のどちらかで指定します。問題文・解説はそれぞれ `--statement` / `--statement-file`、`--editorial` / `--editorial-file` でインライン・ファイルのどちらでも渡せます。
- `--input` を指定すると入力ファイルの内容が送信され、ダウンロード名は既定でそのファイル名になります（`--input-filename` で上書き可）。
- `edit` は指定したフラグの項目だけを更新します。`rm`（別名 `delete`）はキュー中または未来日の問題のみ削除できます。
- `new` は `create` の、`delete` は `rm` の別名です。

## 設定

設定は `$DAILY_CONFIG`(既定 `~/.config/daily/config.toml`、`$XDG_CONFIG_HOME` を尊重)に保存されます。

```toml
server = "https://your-daily-problems.example.com"
token  = "..."
```

トークンは資格情報のため、設定ファイルは `600` で保護されます。

## 開発

```bash
uv sync
uv run pytest
```

Nix を使う場合は `nix develop` で uv と pytest 入りのシェルに入れます。

```bash
nix develop
uv run pytest
```

## ライセンス

[MIT](LICENSE)

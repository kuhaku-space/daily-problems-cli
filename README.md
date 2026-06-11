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

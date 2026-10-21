# ADR 0010: Windowsローカル開発にDev Containerを採用

- 状態: 採用
- 日付: 2026-07-22

## 背景

Windowsローカル環境では、Python仮想環境、OR-Toolsのバイナリ依存、Unix系の開発ツールが
開発者ごとに異なりやすい。一方でこのRepositoryはWindows、Linux、Python 3.11、3.12を
CIで検証しており、Windows固有の手順だけを増やしても品質ゲートの再現性は高まらない。

Docker DesktopはWSL 2をバックエンドとしてLinux Containerを実行できる。利用者向けの
UbuntuなどのWSLディストリビューションはDocker Desktopの利用に必須ではない。

## 判断

- `.devcontainer/`にPython 3.12の最小Dev Containerを置き、Windowsローカル開発の推奨経路にする
- Containerは非rootの`vscode`利用者で実行し、初回作成時に`python -m pip install -e ".[dev]"`を実行する
- Docker socket、privileged設定、ポート公開、認証情報の環境変数注入を含めない
- Docker Compose、Ubuntuの利用者向けWSLディストリビューション、GitHub CLIのContainer内導入は
  現時点で導入しない
- 既存のWindows PowerShellとLinuxの直接セットアップを代替経路として維持し、CIは従来どおり
  Python 3.11と3.12の両方を検証する

## 代替案

### WindowsのPython仮想環境だけを利用する

最小の導入で済むが、依存バイナリやツールの差異を各開発者が解決する必要がある。直接セットアップは
残すが、標準経路にはしない。

### Ubuntuを必須のWSLディストリビューションにする

Linuxファイルシステム上での作業には有用だが、Docker DesktopによるDev Containerの作成には不要であり、
初期設定を増やすため採用しない。

### Docker Composeを導入する

現行プロダクトは外部サービスや複数Containerを必要としない。単一の開発Containerより設定と
運用負荷が増えるため採用しない。

## 影響

Windows開発者はDocker DesktopのLinuxエンジンとVS CodeのDev Containers拡張機能を用意する。
初回のContainer作成にはイメージとPython依存のダウンロードが必要になる。Containerを作り直した
場合も依存は再導入されるが、ホストのPythonや認証情報に依存せず、`python tools/check.py`を同じ
Linux環境で実行できる。

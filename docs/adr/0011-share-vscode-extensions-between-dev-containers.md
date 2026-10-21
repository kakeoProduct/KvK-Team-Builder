# ADR 0011: Dev Container間でVS Code拡張機能を共有

- 状態: 採用
- 日付: 2026-07-22
- 注記: volume名は、ADR 0026で伏せる語を除いた表記に書き換えた。当時の表記は旧Repositoryの履歴にある

## 背景

Dev Containerを作り直すたびに、Codex、Python、Pylance、RuffのVS Code拡張機能を再取得すると、
Windowsローカル開発の初期化時間とネットワーク依存が増える。これらの拡張機能はPythonの
解析、テスト実行、Ruffの表示に必要であり、Containerごとに同じ版を導入する必要がある。

一方、VS Code Server全体を共有すると、接続状態、利用者設定、拡張機能以外の状態まで共有され、
Container間の不具合や認証情報の混入範囲が広がる。

## 判断

- `customizations.vscode.extensions`へ`OpenAI.chatgpt`、`ms-python.python`、
  `ms-python.vscode-pylance`、`charliermarsh.ruff`を定義し、Container作成時に自動導入する
- Docker Desktop上の`kvk-vscode-extensions`名前付きvolumeを、非root利用者の
  `/home/vscode/.vscode-server/extensions`だけへmountする
- volumeは同じDocker Desktop上で作成した本RepositoryのDev Container間だけで再利用する
- VS Code Server全体、Workspace、Docker socket、`GH_TOKEN`、その他の認証情報は共有しない
- Codexのログイン状態は共有volumeへ保存せず、利用者がVS CodeまたはCodexで個別に認証する

## 代替案

### Containerごとに拡張機能を再導入する

設定は少ないが、Container再作成のたびに拡張機能の取得を待つ必要があるため採用しない。

### VS Code ServerのホームDirectory全体を共有する

拡張機能以外の状態まで共有して原因切り分けが難しくなり、認証情報を含む範囲も広がるため
採用しない。

### ホストのVS Code拡張機能Directoryをbind mountする

WindowsとLinuxのパス・実行環境が混在し、Container内で必要なLinux向け拡張機能を保証できないため
採用しない。

## 影響

初回のみContainer内で拡張機能を取得し、その後のContainer作成では同じDocker Desktop内のvolumeを
再利用できる。volumeはGit管理されず、別のPCやDocker Desktop環境へは自動で移行しない。拡張機能の
破損や互換性問題が起きた場合は、対象volumeを削除して再作成する。

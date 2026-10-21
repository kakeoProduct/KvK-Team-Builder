# ADR 0016: Dev Containerで作業ツリーの所有者を実行利用者へそろえる

- 状態: 提案中
- 日付: 2026-10-17

## 背景

ADR 0010のDev Containerは、非rootの`vscode`利用者でContainerを動かす。WindowsのDocker Desktopで
`C:\`上の作業ツリーを開くと、作業ツリーは`uid=0;gid=0;metadata`を指定した9p（drvfs）で共有され、
既存のファイルはroot所有に見える。Gitは作業ツリーと`.git`の所有者を実行利用者と比べるため、
「dubious ownership」でGitコマンドが失敗した。

この失敗は、Git操作だけでなく、Gitの状態を読む共有記憶Script、SessionStart Hook、Stop Hookも
止めていた。共有記憶の開始状態が保存されず、Hookは失敗しても作業を止めない設計のため、
記録漏れの確認が黙って無効になっていた。

`metadata`オプションにより所有者の変更はNTFS側に保存され、Container内で新しく作ったファイルは
既に`vscode`所有になる。そのため、既存の作業ツリーと`.git`の所有者を一度rootで変更すれば
解消するが、`vscode`はroot権限を持たない。

## 判断

- イメージへ`sudo`を導入し、root所有で引数を取らない`/usr/local/bin/fix-workspace-owner`だけを、
  `vscode`がパスワードなしで実行できるようにする。sudoersでは空の引数指定で、引数付きの実行も
  拒否する。sudoersは`visudo --check`で検証してからイメージへ含める
- `postStartCommand`で起動のたびにこのScriptを実行する。Scriptはsudoが設定する`SUDO_UID`と
  `SUDO_GID`を所有者とし、`/workspaces`直下にあるGit作業ツリーの最上位と`.git`だけを変更する。
  Gitが所有者を検査するのはこの2つだけなので、再帰的には変更しない
- Symbolic Linkはたどらず、`chown -h`で変更する
- `safe.directory`による例外は設定しない。所有者の不一致を隠すのではなく、一致させる

## 代替案

### `safe.directory`へ作業ツリーを登録する

設定1行で済むが、所有者の不一致を残したまま検査を無効にする。利用者全体のGit設定（`--global`）へ
例外を追加することにもなるため採用しない。

### Containerの最初のプロセスだけをrootで動かす

sudoは不要になるが、Container自体が非rootではなくなり、ADR 0010の前提が大きく変わる。
Dev Containerの`overrideCommand`との組み合わせも必要になるため採用しない。

### Repositoryを「Clone Repository in Container Volume」でVolumeへ置く

所有者の不一致が根本から解消し、ファイル操作も速くなる。ただしソースが`C:\`から離れ、
Windows側での直接編集やWindows用の仮想環境と並行する現在の運用ができなくなるため、
標準の手順にはしない。

### 利用者がホストから一度だけ`docker exec -u root`で変更する

Repositoryの変更は不要だが、cloneし直した利用者や新しい開発者ごとに同じ手作業が必要になる。

## 影響

- 既存のContainerは作り直すまで変わらない。`Dev Containers: Rebuild Container`が必要になる
- イメージに`sudo`が加わる。許可は1つのScriptに限られ、任意のroot実行はできない
- Linuxホストで`updateRemoteUserUID`によりUIDがそろう環境では、所有者は既に一致しており、
  Scriptは同じ所有者を設定し直すだけになる
- Scriptはイメージの構築時にコピーされる。Scriptを変更した場合もContainerの再構築が必要になる

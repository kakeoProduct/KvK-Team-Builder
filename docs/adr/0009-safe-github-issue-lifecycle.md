# ADR 0009: GitHub Issueの安全な作成と完全削除

- 状態: 提案中
- 日付: 2026-07-20

## 背景

GitHub Issueの作成と削除をCodexと人間で再現可能にするには、Repositoryの文脈、重複、認証、権限、
外部作用の承認を同じ手順で扱う必要がある。Issueの作成は重複や不正確なmetadataを残す可能性があり、
完全削除は本文とコメントを復元できない。さらにGitHub REST APIはPull RequestもIssueとして返すため、
番号だけを根拠に削除するとPull Requestを誤って対象にする危険がある。

Pull Request作成で採用したCodespaces Secretの`GH_TOKEN`は、Repository限定のfine-grained PATとして
Issue操作にも利用できる。新しいTOKEN保存方式は追加せず、操作ごとの承認境界をSkillで定義する。

## 判断

- `$manage-github-issue`は、本文準備、単一Issueの作成、単一Issueの完全削除だけを扱う
- 作成前にopenとclosedの既存Issueを検索し、RepositoryのIssue Templateがあれば正本として使う
- label、assignee、milestone、Project、Issue typeを推測せず、本文は一時Fileから`--body-file`で渡す
- 作成の明示的な依頼を単一の`gh issue create`の承認として扱い、準備やPreviewでは作成しない
- 削除前に対象を再取得し、REST APIの応答に`pull_request`がないことを確認する
- 削除対象のRepository、番号、題名、状態、URL、コメント数、復元不能であることを提示し、その後の
  同一対象に対する再承認を必須にする
- 再承認直後に対象とPull Request除外を再検証してから`gh issue delete --yes`を実行し、一括削除と
  自動再試行を行わない
- 解決済みや古いIssueにはCloseを推奨するが、削除依頼をCloseへ暗黙に変更しない
- 認証はADR 0008と同じ`GH_TOKEN`または既存のGitHub CLI認証を利用し、TOKENを保存または表示しない

## 代替案

### IssueをCloseする操作だけを提供する

履歴を保持でき、通常の完了や重複には適している。しかし、秘密情報や法的・運用上不要な記録の完全
削除が必要な場合を扱えないため、既定の推奨として残しつつ、再承認付きの完全削除も提供する。

### 最初の削除依頼をそのまま実行承認とする

操作は短くなるが、番号の誤り、Repositoryの取り違え、Pull Requestの誤認を訂正する機会がない。
復元不能な外部作用に対して安全性が不足するため採用しない。

### GitHub Web画面だけでIssueを削除する

GitHubが確認画面を提供する一方、Codexと人間で検証手順を共有できず、自動化時の対象確認も残らない。
緊急時の手動手段としては利用できるが、標準手順にはしない。

## 影響

Issue作成は重複と不正確なmetadataを抑え、Issue TemplateがあるRepositoryでは同じ契約を再利用できる。
完全削除には必ず2回の利用者操作が必要となり、対象確認後に手順が一度停止する。PATにはIssueの読み書き
権限が必要で、完全削除にはRepository管理者権限が必要になる。権限不足、Network制限、削除結果が不明な
失敗は自動回復せず、安全な停止として利用者へ報告する。

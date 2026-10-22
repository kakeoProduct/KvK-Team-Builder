# ADR 0028: CIを作業branchのpushで重複して実行せず、Pull Requestの古い実行を中止する

- 状態: 提案中
- 日付: 2026-10-22
- 置き換え: ADR 0027のうち、CIをすべてのpushとPull Requestで実行するとした点

## 背景

CIの「品質チェック」は、`push`と`pull_request`の両方を条件に、Ubuntu、Windows×Python 3.11、3.12の
4つのjobで`python tools/check.py`を実行していた。`push`にbranchの指定がないため、作業branchへpushして
Pull Requestを開くと、同じコミットに対して4つのjobが2回走り、Pull Requestにはチェックが8つ並ぶ。2026-10-21の
実行記録では、作業branchのコミットと、`dev`からのリリースPull Requestのコミットの両方で、`push`と
`pull_request`の実行が1回ずつあった。リリースPull Requestを取り込んだ後の`main`へのpushでも、同じ4つの
jobが走った。1つのjobはUbuntuで約70〜120秒、Windowsで約160〜240秒だった。

公開Repositoryの標準のrunnerは無料のため、費用ではなく、重複したチェックと待ち時間が問題になる。
利用者はCIの数を適切に絞ることを求め、OSとPythonの版の行列は維持し、重複だけを除く案を選んだ。

一次情報（確認日2026-10-21〜22）では次を確かめた。

- `push`はpushしたbranchの先頭のコミットを、`pull_request`は基準branchとのmerge commit
  （`refs/pull/番号/merge`）を検証する。イベントが違うため、両方を条件にすると両方が走る
  （GitHub Docs「Events that trigger workflows」）
- GitHubのPython向けの公式テンプレート（`actions/starter-workflows`の`ci/python-package.yml`）は
  `push`と`pull_request`の両方を、Scientific Python Development Guideの例は`push`だけを既定branchに
  絞っている
- `concurrency`で同じグループに入った実行は、`cancel-in-progress`がfalseでも待機中の古い実行が
  中止される。公式文書は、グループを`github.head_ref || github.run_id`にしてPull Requestの実行だけを
  中止する例を示している（GitHub Docs「Control the concurrency of workflows and jobs」）
- `github.head_ref`はPull Requestのhead（source）branchで、`pull_request`と`pull_request_target`の
  ときだけ値が入る。`github.run_id`はRepository内で実行ごとに一意な番号である（GitHub Docs「Contexts
  reference」）。（作成者の読み取り）branchの名前にはforkの所有者もPull Requestの番号も含まれないため、
  別のforkの同じ名前のbranchから出たPull Requestは同じ値になる
- `push`と`pull_request`の重複を避けるよう求める、GitHubの文章による推奨は見つからなかった

## 判断

- `push`の対象を`main`と`dev`に絞り、`pull_request`の対象branchは絞らない。作業branchは`dev`への
  Pull Requestで、`dev`は`main`へのリリースPull Requestで検証する。取り込んだ後の`main`と`dev`は
  `push`で検証する
- `concurrency`のグループを`${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}`
  とし、`cancel-in-progress: true`にする。同じPull Requestへ続けてpushすると古い実行を中止し、`main`と
  `dev`へのpushの実行は中止しない。Pull Requestは番号ごとにグループが分かれるため、forkや同じ名前の
  branchから出たPull Requestの実行を中止しない。公式文書の例の`github.head_ref`は、レビューでこの
  衝突が分かり、利用者の同意を得て番号へ変えた
- OSとPythonの版の4つのjobと、job名は変えない。branch保護の必須チェックは設定し直さない
- `dev`へのpush、リリースPull Request、取り込んだ後の`main`へのpushは同じ内容を検証するため、
  リリースごとに3回実行される。`dev`へのpushとリリースPull Requestは`dev`の同じ先頭コミットに対して
  実行される。リリースPull Requestが検証するmerge commitと、取り込んだ後の`main`の先頭は`dev`の先頭とは
  別のコミットだが、`main`にはリリースのmerge commitだけが加わるため、内容は`dev`の先頭と同じになる。
  リリースの頻度は低く、利用者は`push`の対象を`main`と`dev`にすると決めたため、この重複は残す
- Pull Requestを作る前の作業branchのpushではCIを実行しない。利用者はこの影響を示された上で案を選んだ
- （作成者の仮定）Pull Requestを作る前は手元の`python tools/check.py`で確かめる。Pull Requestを作る前に
  CIで確かめたい場合は、利用者が明示したときに`$create-github-pr`でDraft Pull Requestを作る

## 代替案

- **全pushとPull Requestで実行し続ける**: Pull Requestを作る前でもCIが走るが、作業branchの
  コミットごとに同じ4つのjobが2回走り、チェックの表示も倍になる。
- **`push`を`main`だけに絞る**: `dev`へ取り込んだ後のコミットが検証されなくなる。branch保護で
  「Require branches to be up to date before merging」を有効にしないため（ADR 0027）、取り込んだ後の
  組み合わせはPull Requestの時点と変わり得る。
- **`pull_request`の対象を`dev`に絞る**: リリースPull Requestで必須チェックが走らず、
  Pendingのまま取り込めなくなる。
- **`concurrency`のグループを`github.ref`にする**: `main`と`dev`へのpushが同じグループに入り、
  続けて取り込むと、`cancel-in-progress: true`のため途中のコミットの実行中または待機中の実行が
  中止される。
- **`concurrency`のグループを`github.head_ref`にする**: 公式文書の例の形だが、forkの`dev`から出た
  Pull RequestとリリースPull Request（head `dev`）や、別々のforkの同じ名前のbranchから出た
  Pull Requestが同じグループに入り、互いの実行を中止する。第三者がリリースPull RequestのCIを
  繰り返し中止させ得る。
- **行列を減らす、または静的検査を別jobにする**: 1つのOSで1つの版だけを省くと、OS依存の
  不具合（ADR 0019のWindowsだけの失敗など）を見逃し得る。静的検査の分離は失敗の原因を
  job名で示せるが、チェックの数が増え、必須チェックの設定と`tools/check.py`の構成も変える必要が
  あり、今回の目的に合わない。

## 影響

- 作業branchのPull Requestのチェックは8つから4つになる。必須チェックの名前は変わらない
- Pull Requestを作る前の作業branchのpushでは、CIの結果が得られない
- forkからのPull Requestは従来どおり`pull_request`で検証され、ほかのPull Requestの実行を中止しない
- `concurrency`で古い実行が中止されることは、この変更を取り込んだ後の最初のPull Requestで
  利用者が確かめる
- `tests/test_ai_harness.py`がトリガーと`concurrency`の設定を検査する

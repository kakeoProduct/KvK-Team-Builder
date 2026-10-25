# ADR 0030: ブラウザ用補助ツールの実物のHTMLをNode.jsとjsdomで検査する

- 状態: 提案中
- 日付: 2026-10-25
- 置き換え: ADR 0013のうち、`web/`の正しさをブラウザでの動作確認だけで担保する点。集結タイムライン計算と
  周期ウェーブタイマーは、本ADRの検査を品質ゲートに含める。`web/`をRuff、mypy、pytestの対象外とする点は維持する

## 背景

集結タイムライン計算は、1周目と2周目でパターンの順番が変わり、1周目を周期ごとに繰り返すと待ち時間を
破る指示を出すことがあった。2026-10-25に、実物のHTMLをjsdomで読み込んでボタンを押し、出力テキストだけで
性質を検査したところ、決定的な乱数で作った1000件の入力のうち165件で、1周目の繰り返しが待ち時間を破った。
コードを読むだけでは、この不具合に気づけなかった。

周期の求め方を直し、集結タイムライン計算と周期ウェーブタイマーにページ内のタブを加えるにあたり、
同じ検査を常に実行して退行を防ぐ必要がある。ADR 0013では`web/`を品質ゲートの対象外とし、正しさを
ブラウザでの動作確認で担保するとしていた。ADR 0021では、FEのためにNode.jsをCIとDev Containerへ
加える方針を決めたが、まだ実施していない。現状のDev ContainerにはNode.jsがない。

## 判断

- 実物のHTMLをNode.jsとjsdomで読み込み、画面と同じ操作で動かす検査を`tests/web/`へ置く。HTMLの計算を
  検査用に別の言語へ移植しない。検査はNode.js標準の`node:test`で書き、テスト用のライブラリを増やさない
- 検査は`tools/check_web.py`から実行し、`python tools/check.py`の1項目にする。Node.jsまたはjsdomが
  見つからない場合は、入れ方を示して失敗させる。黙って省略しない
- Node.jsのバージョンは`.node-version`に1つだけ書いて固定する（22.11.0）。CIは`actions/setup-node`で
  このファイルを読み、Dev Containerは同じバージョンの公式イメージから`node`と`npm`を複写する。
  構造テストがこの3か所の一致を確かめる
- jsdomはRepositoryの最上位の`package.json`へ版を固定して書き、`package-lock.json`をコミットする。
  CIとDev Containerは`npm ci`で入れる。CIはnpmのcacheを使う
- Dev Containerは作成時の`postCreateCommand`で`npm ci`も実行し、作り直した後は手作業なしで
  品質ゲートが成功する状態にする
- 対象は、検査を書いた集結タイムライン計算と周期ウェーブタイマーとする。他のツールは、修正するときに
  検査を加える

## 代替案

### 計算をPythonへ移植してpytestで検査する

Node.jsが不要になるが、検査するのは移植したコードであり、実物のHTMLではない。移植のずれで不具合を
見逃すおそれがあるため、利用者は実物での確認を求めた。

### Playwrightなどの実ブラウザで検査する

レイアウトやメディアクエリまで確かめられるが、ブラウザの取得でCIとDev Containerが重くなり、
WindowsのCIでの安定性も確かめる必要がある。今回の検査は計算、タブ、保存、読み込みであり、
DOMとlocalStorageを持つjsdomで足りるため採用しない。画面幅による表示の違いは、従来どおり
ブラウザで確かめる（COM-053）。

### Node.jsがない環境では検査を省略する

手元で品質ゲートが通りやすくなるが、検査が実行されないまま成功と表示される。必須の検査であるため
採用しない。

### Dev ContainerのFeatureでNode.jsを入れる

設定は短いが、Container作成時にFeatureの取得とインストールが走り、版の固定もFeatureの実装に依存する。
公式イメージから複写すれば、`.node-version`と同じ版を1行で固定できるため採用しない。

## 影響

- 開発環境にNode.jsとnpmが必要になる。Dev Containerは`Dev Containers: Rebuild Container`で作り直す。
  Containerを使わない環境は、`DEVELOPMENT.md`の手順でNode.jsを入れ、`npm ci`を実行する
- CIの各jobにNode.jsの準備と`npm ci`の手順が加わり、実行時間が少し延びる。job名、matrix、
  既存の手順は変えない
- ルートの`package.json`は、ADR 0021で決めたnpm workspacesのルートになる予定のファイルである。
  FEを加えるときは、このファイルへworkspacesを加える
- `node_modules/`はGit管理外とする

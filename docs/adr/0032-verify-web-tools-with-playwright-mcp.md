# ADR 0032: ブラウザ用補助ツールをPlaywright MCPで実際に操作して確かめる

- 状態: 提案中
- 日付: 2026-11-04

## 背景

`web/`のツールは、変更したときにDesktop幅とMobile幅のブラウザで主要な操作を確かめる（COM-053）。
`tests/web/`のjsdomの検査（ADR 0030）は計算、保存、読み込みを確かめるが、メディアクエリによる表示の
違いや、画面に見えるかどうかは確かめられない。2026-11-03のレビューでも、自動取り込みの通知が900px以下で
隠れ、1280px幅でも画面の外に出る問題は、jsdomでは見つからず、実際のブラウザで確かめて確定した。

Dev ContainerはPythonの最小イメージで、ブラウザの共有ライブラリと日本語フォントがない。sudoは作業ツリーの
所有者をそろえるScriptにしか許していない（ADR 0016）ため、Containerを作った後には入れられない。これまでの
確認は、別Sessionの一時ディレクトリへ手で展開したライブラリと、自作のCDP Scriptに頼っており、再現できなかった。
その画面では、サイドバーの絵文字のアイコンも表示されなかった。

利用者は、AIエージェントが実際の操作で確かめられる仕組みを導入するよう求めた（2026-11-03）。ADR 0030は
実ブラウザを品質ゲートに含める案を、CIとDev Containerが重くなる理由で採らなかった。本ADRは品質ゲートには
含めず、Dev Containerで手で確かめる手段だけを加える。

## 判断

- Dev ContainerのDockerfileで、Debianの`chromium`と`fonts-noto-cjk`をイメージの作成時に入れる。
  サイドバーなどの絵文字のアイコンを確かめるため、`fonts-noto-color-emoji`も入れる（作成者の判断）
- Playwright MCP（`@playwright/mcp`）を`package.json`の`devDependencies`へ版を固定して書き、
  `package-lock.json`で固定する。版は公開から2週間以上たった`0.0.83`（2026-09-28公開）とする（作成者の判断）。lockで入る
  `playwright`と`playwright-core`は、この版が厳密に指定するalpha版（`1.64.0-alpha-1790635538000`）である。
  起動は`npx --no -- playwright-mcp`とし、lockfileの版がなければ取得せずに失敗させる。`--`がないと、npxが
  `--executable-path`などをnpmの設定として読み取り、サーバーへ渡さない（作成者の判断）
- Claude Codeは`.mcp.json`、Codexは`.codex/config.toml`で、同じ引数のサーバーを登録する。構造テストが
  両者の一致を確かめる
- ブラウザは画面なし（`--headless`）、閲覧データをディスクへ残さない（`--isolated`）で起動する。自動で名前を
  付けた画面写真などは`--output-dir`のGit管理外の`tmp/playwright-mcp/`へ書く。名前を指定した出力は作業ツリーから
  の相対で解決され、作業ツリーの中ならどこへでも書けるため、名前を省くか`tmp/playwright-mcp/`から始める
- Dockerの既定のseccompはuser namespaceを禁じており、ContainerではChromiumのsandboxを使えない。
  Containerの制限は緩めず、`--no-sandbox`で起動する。`--allowed-origins`で、ブラウザが要求する先を
  `http://127.0.0.1:8765`だけにする。利用者はこの方式を選び（2026-11-03）、上流の次の注意を知った上で
  維持すると決めた（2026-11-04）
- 上流は`--allowed-origins`を、安全境界ではなく、リダイレクトにも効かないと明記している。sandboxを外した
  危険を実際に補っているのは、外部の資源を読まない自作の`web/`だけを開くという前提である（作成者の仮定）。
  2026-11-04の時点で、`web/`のHTMLとJSは外部のURLを読み込まない。構造テストが`web/`の下のHTML、JS、CSS、SVGの
  文字列を確かめ、`web/`に外部の資源を加えるときはこの判断を見直すよう案内する
- `web/`は`python -m http.server 8765 --bind 127.0.0.1 --directory web`で配信して開く。`file://`は
  Playwright MCPが既定で開かない。また、ページと同じoriginから`web/pet-bonus.js`とlocalStorageを使うためでもある。
  ポートは`--allowed-origins`と合わせて8765に固定する（作成者の判断）。使用中のときは変更したファイルと確かめる
  ページが読むファイルを配信元から取得して作業ツリーと比べ、すべて一致すれば続ける。一致しないか取得できなければ共用せず、終わるのを待つか、
  手元のブラウザで確かめ、どちらもできなければ未実施として報告する。確かめ終えたら自分が起動した配信を止める
- 読み取り専用のレビュー担当にはブラウザのToolを使わせない。画面写真の保存は書き込みに当たる。
  Claude Codeでは、`enforce_read_only_agent.py`が既に`mcp__.*`を拒否する（ADR 0018）。Codexで担当ごとに
  MCPのサーバーを外せるかは確かめておらず、仕組みでは強制していない。ブラウザでの確認は主エージェントが行い、
  結果を担当へ渡す。担当ごとの強制は、Codexの実機で確かめるまで文書の規則に留める（利用者の判断、2026-11-04）
- `browser_run_code_unsafe`は使わない（作成者の判断）。上流の既定で有効で、Node.jsのプロセスでコードを実行できる
  ため、Bash Toolを通らず、Git保護のHookと`.env`の拒否を迂回できる。`browser_drop`と`browser_file_upload`も使わない
  （作成者の判断）。作業ツリーのファイルをページへ渡すため、ページのJSから`.env`を読め、`.env`の読み取りの拒否を
  迂回できる。`web/`にはファイルの入力もdropの処理もない。Claude Codeでは、この3つを`.claude/settings.json`の`permissions.deny`で拒否する
  （利用者の判断、2026-11-04）
- ブラウザのToolの`filename`は`tmp/playwright-mcp/`の下に限る。上流の`filename`は作業ツリーの内側なら通り、読み取り
  専用と宣言された`browser_network_request`を含むToolで、Hookの実体、`.claude/settings.json`、`.git/config`を任意の
  内容へ上書きできる。上流に限る設定はないため、Claude Codeでは`tools/hooks/restrict_browser_files.py`が主Sessionを
  含めて拒否する（利用者の判断、2026-11-04）。止めるのは名前を指定した出力だけで、ページの操作は限らない。受け付けるのは
  `tmp/playwright-mcp/`から始まる相対パスだけで、同じ場所を指す絶対パスと`:`や`\`を含む名前も拒否する。`tool_input`の
  `_meta`は、`_meta.cwd`が`filename`の解決の基準を変えるため、値にかかわらず拒否する（いずれも作成者の判断）
- Codexでは、Toolの拒否も`filename`の制限も、対応する設定を確かめておらず、仕組みでは強制していない
  （利用者の判断、2026-11-04）。使わないことと`filename`の規則は文書に書く（作成者の判断）

## 代替案

### Containerのseccompを緩めてsandboxを使う

`devcontainer.json`で、user namespaceを許すseccompを渡せばsandboxを使えるが、ブラウザ以外の
プロセスにも緩和が及ぶ。利用者はContainerの制限を緩めない方式を選んだ（2026-11-03）。

### MCPの登録を共有せず、利用者ごとのローカル設定にする

`--no-sandbox`の判断を利用者ごとに任せられるが、CodexとClaude Codeで設定がずれ、AIエージェントが
同じ手順で確かめられなくなる。Claude Codeでは、Hookと`permissions.deny`が共有の設定にあるため、登録を
分けても安全性は上がらない。採らなかった（作成者の判断）。

### Chrome DevTools MCP、またはChromeの拡張機能（Claude in Chrome）

Chrome DevTools MCPは通信や性能の調査に強いが、Mobile幅の再現と画面の構造の読み取りはPlaywright MCPの
ほうが向く。Chromeの拡張機能は利用者のホストのChromeを操作するもので、Dev Containerの中からは届かない。

### Playwrightの実行時にブラウザを取得する（`npx playwright install --with-deps`）

Playwrightと版をそろえたブラウザを使えるが、依存ライブラリの導入にrootが要り、Dockerfileでの取得は
Playwrightの版と結び付く。Debianの`chromium`ならaptで共有ライブラリごと入る。

### Playwright Testで画面の検査を品質ゲートに加える

回帰を自動で防げるが、CIへのブラウザの導入と、WindowsのCIでの安定性の確認が要る（ADR 0030と同じ理由）。
今回は確認の手段を整えることに限り、必要になったら別に判断する。

## 影響

- 既存のContainerは`Dev Containers: Rebuild Container`で作り直す。イメージはブラウザとフォントの分だけ大きくなる。
  作り直したContainerで、Debianの`chromium` 156とPlaywright MCP 0.0.83の組み合わせが動くことを確かめた（2026-11-04）
- Claude Codeは、共有された`.mcp.json`のサーバーを初めて使う前に利用者へ承認を求める。Codexは信頼した
  Projectでだけ`.codex/config.toml`を読む（Codexでの動作は未確認）
- `chromium`はDebianのセキュリティ更新に従い、イメージを作った時点の版になる。Playwright MCPとの組み合わせで
  動かなくなった場合は、MCPの版を上げるか、イメージを作り直す
- `--executable-path`はContainerのパスであり、Windowsで直接開いた場合はサーバーが起動しない。Containerの外の
  Linuxで同じパスにChromiumがあれば、sandboxを使える環境でも外して起動する。品質ゲートとほかの機能には影響しない
- 出力先は、サーバーを起動した場所からの相対で解決される。Repositoryの最上位以外から起動すると、Git管理外に
  ならない場所へ出るおそれがある
- Session用worktreeでは、そのworktreeで`npm ci`を実行するまでサーバーが起動しない
- CIの`npm ci`も`@playwright/mcp`とPlaywrightを入れるが、install時のScriptがなく、ブラウザは取得しない
- Playwright MCPの版を上げるときは、Toolの追加と改名、`filename`や`paths`に当たる引数、`_meta`のようにサーバーの共通
  処理が読む引数、ダウンロードのような引数なしの書き込みの変更を確かめる。拒否するToolの名前と、ファイルにつながる引数名は、インストールした版の一覧と
  テストで照合する
- Hookの登録と`permissions.deny`の変更は、Claude Codeの新しいSessionから有効になる。実機での発火は、変更後の新しい主Session
  （Claude Code 2.1.317、Playwright MCP 0.0.83）で、Playwright MCPのToolの呼び出しと一覧により次のとおり確かめた（2026-11-04）
  - `filename`に`page.png`を渡した`browser_take_screenshot`は`restrict_browser_files.py`が拒否し、ファイルは作られなかった
  - 名前なしの画面写真は`tmp/playwright-mcp/`へ保存され、引数なしの`browser_snapshot`も通った
  - `browser_drop`、`browser_file_upload`、`browser_run_code_unsafe`は、インストールした版の定義では既定で一覧に出る
    Tool（`capability: "core"`で`skillOnly`なし）だが、Claude CodeのToolの一覧に出ず、ToolSearchの指定でも見つからなかった。この項は
    Toolの呼び出しではなく一覧で確かめ、実行して試してはいない
  - `_meta.cwd`へ別のディレクトリを渡した`browser_take_screenshot`は、`filename`が`tmp/playwright-mcp/`の下でも
    `restrict_browser_files.py`が拒否し、そのディレクトリと`tmp/playwright-mcp/`のどちらにも出力されなかった。Hookが先に
    拒否するため、Claude Codeが`_meta`をサーバーへ転送するかどうかは確かめていない
- ブラウザの幅を変えてもタッチ操作は再現しない。`--isolated`のため、ブラウザを閉じるとlocalStorageも消える。
  Toolの呼び出しが1時間ないとブラウザは閉じる（`--idle-timeout`の既定）

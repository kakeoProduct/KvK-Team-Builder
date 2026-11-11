# アーキテクチャ

## 設計方針

このシステムは「KvKチーム編成」をコアドメインとする、戦術的DDDを取り入れた
モジュラーモノリスとして設計します。境界づけられたコンテキストは「KvKチーム編成」と
「戦闘タイミング」の2つです（ADR 0021）。Markdown入力、JSON永続化、OR-Tools、CLI、
Web UIはドメインの外側に置きます。以下の処理フローとCP-SATモデルは「KvKチーム編成」の
現行の実装で、所属固定のモデル（ADR 0034）です。応援、選択肢の提示、FRM-037の目的関数などの
目標仕様は`docs/requirements/team-building/`にあり（ADR 0023）、実装Issueが完了するたびにこの文書へ
反映します。

目標の依存方向は次のとおりです。

```text
入力側アダプター              アプリケーション          ドメイン
CLI / Web / Markdown ──────→ BuildTeamPlan ─────────→ モデル / ポリシー / サービス
                                   ↑                        ↑
                                   │                        │
接続先アダプター              アプリケーション境界          │
JSONリポジトリ / CP-SAT ──────────────────────────────────┘

ValidatedTeamPlan ─────────→ Markdown / Web表示変換
```

ドメインは外部表現やLibraryへ依存しません。アプリケーションはユースケースと境界を定義し、
アダプターとインフラストラクチャがそれを実装します。入力アダプターはドメイン型を
ユースケースへ渡し、ユースケースは外部表示形式ではなく検証済み結果を返します。
詳細なモデル、ユビキタス言語、
移行先構造は[ドメインモデル](domain-model.md)を参照してください。

「KvKチーム編成」は`src/kvk_team/team_building/`の`domain`、`application`、`adapters`へ
移行済みです（#28）。編成ルール`KvKRules`はチームマスタを必須で受け取り、JSONからの読み込みと
既定部品の組み立ては`interfaces/cli/composition.py`で行います。依存方向は
`tests/test_dependency_direction.py`が品質ゲートで検査します。ユースケース`BuildTeamPlan`は
`Member`の一覧と運用者の指定`OperatorSpecification`を受け取り、検証済み編成`ValidatedTeamPlan`を返します。機能変更と大規模移動を
同じPull Requestへ混在させません。

## リポジトリ構成

モノリポジトリのまま、Pythonの配布物は1つとし、コンテキストをサブパッケージで分けます。
目標の構成は次のとおりです（ADR 0021）。

```text
src/kvk_team/
  team_building/     KvKチーム編成: domain / application / adapters
  battle_timing/     戦闘タイミング: domain / application / adapters
  interfaces/
    cli/             編成CLI
    web/             Djangoプロジェクト、Django NinjaのAPI、FEの配信
frontend/            React、TypeScript、Vite（npm workspaces）
  src/api/           OpenAPIの定義と生成した型（コミットし、品質ゲートで差分を確かめる）
web/                 既存のHTMLツール（各ページと共通部品）。置き換えが済んだものから削除する
tests/               team_building/、battle_timing/、interfaces/、構造テスト
docs/requirements/   要件定義書
tools/               PythonとFEに共通の品質ゲート
```

- `team_building`と`battle_timing`は互いをimportしません。組み合わせる場合は`interfaces`で
  各コンテキストのユースケースを呼びます
- 依存方向は`interfaces -> application -> domain`、`adapters -> application / domain`です。
  `domain`はDjango、Django Ninja、JSON、Markdown、OR-Tools、`pathlib`をimportしません
- Djangoの永続化モデルを使う場合は、そのコンテキストの`adapters/`に置きます。永続化の方式は
  #2で決めます
- FEは表示、入力、毎フレームのタイマー描画だけを持ち、ドメインルールを複製しません
- 編成処理の移動は#28、Node.jsと品質ゲートの統合は#21で行います

## 処理フロー

```text
team_master.json ─→ JsonTeamMasterRepository ─────────→ TeamMaster（KvKRules）
settings.json ───→ JsonOperatorSettingsRepository ───→ OperatorSpecification
answers.json ────→ JsonAnswersRepository ────────────→ tuple[Answer]
前回のJSON ──────→ JsonPlanRecordRepository ─────────→ PlanRecord（OperatorSpecification.previous_plan）
                                                              ↓
参加者一覧.md ─→ MarkdownMemberParser ─→ list[Member]         ↓
                                ↓                             ↓
                     BuildTeamPlan: resolve_leaders、check_answers
                     （1人に決まらない、ほかの指定によらない回答の誤り → SpecificationError）
                                ↓
              回答なしの判定に使う編成 → 回答を順に1つずつ確かめる（late_startsへ加える）
                                ↓
                      MembershipOptimizer（内部でAvailabilityResolver）
              ↙ SolvedPlan（TeamPlan、最適性）   ↘ ProvenInfeasible（理由）→ NoValidPlanError
                                ↓                   時間切れ → OptimizationTimeoutError
                       TeamPlanValidator（参加者一覧と指定から計算し直す）
         ↓ 必須条件OK    ↘ 休止だけ: 最適ならLowerBoundShortfallError（番号付きの質問）、
                            最適と示せなければShortfallUndeterminedError。ほかのNGは再試行（上限でBuildError）
   ValidatedTeamPlan（編成＋警告・出撃の指標・待機・別枠・最適性・注記）
                ↓                                      ↓
     TeamPlanMarkdownExporter        PlanRecord.from_validated → render_plan_record
                ↓                                      ↓
  <出力のフォルダ>/<実行の時刻>/チーム編成.md     <出力のフォルダ>/<実行の時刻>/チーム編成.json
```

アプリケーションのユースケース`BuildTeamPlan`が、参加者と運用者の指定を受け取り、Optimizer、
ValidatorをProtocol経由で調整し、再試行します。OptimizerとValidatorには同じ`OperatorSpecification`を
渡します。Optimizerの結果は、解あり（`SolvedPlan`。探索の制限内に最適だと示せたかを持つ）、
解がないことの証明（`ProvenInfeasible`。理由を持つ）、時間切れ（`OptimizationTimeoutError`の送出。
ADR 0019）の3つに分けます。下限の不足（延長境界時刻より前の休止）は、最適だと示せた編成でだけ
「避けられない」と判断し、理由を示して止めます。最適だと示せない編成で判断すると避けられる不足を
運用者へ示すことになるため、時間切れのエラーにします（FRM-090の性質(6)、ADR 0034）。
Validatorが必須条件を満たすと判定した編成だけが`ValidatedTeamPlan`になり、
必須条件エラーを含む検証結果からは生成できません。CLIの`TeamBuilder`
（`interfaces/cli/team_builder.py`）は、Markdownの解析、`BuildTeamPlan`、Exporterをこの順に
呼び出すだけです。Exporterは`ValidatedTeamPlan`だけを受け取るため、未検証の候補を誤って出力できません。
`ValidatedTeamPlan`が型で保証するのは「検証結果に必須条件エラーがない」ことだけで、その検証結果が
同じ編成のものであることは、`BuildTeamPlan`が生成する前提で守ります。ほかの経路で生成しません。

運用者の回答（遅れて出撃する隊と応援先）は、`BuildTeamPlan`が次の順に確かめます（作成者の仮定A-41、ADR 0035）。
ほかの指定によらない誤りは`domain/answers.py`の`check_answers`で最適化の前に入力のエラーにします。次に回答なしの
判定に使う編成を作り、回答を対象の隊の番号、時刻、指定の順に1つずつ確かめます。対象が不足でなければ使わなかったと
注記し、そうでなければ指定を加えて、対象の休止をなくし、ほかの（隊、時間帯）に休止を新しく生まない編成を
Optimizerに探させます（`optimize`の`allowed_shortfalls`）。見つかれば受け入れ、ないと証明されれば受け入れなかったと
注記します。見つかった編成に休止が残り、最適性を示せなければ時間切れのエラーにします（FRM-090の性質(6)）。
受け入れた指定の編成に休止が残れば、隊と序盤かどうかでまとめた番号付きの問い（`ShortfallQuestion`）を
持つ`LowerBoundShortfallError`を送出します。アプリは回答を覚えず、運用者が同じファイルへ足していきます。

出力は、CLIの2つ目の引数の出力のフォルダに、実行の時刻（現地時刻の`YYYYMMDD-HHMMSS`）のフォルダを新しく作って
書きます。同じ名前があれば`-2`、`-3`を付け、前の出力を上書きしません（DAT-008、ADR 0036）。編成のMarkdownと
一緒に、検証済み編成から作った編成の記録（`PlanRecord`）を編成のJSON（DAT-010）として書きます。終了コード2、3、4
では何も書きません。時刻は`main`の`clock`から受け取り、テストでは固定します。

運用者が共有した回の編成のJSONを`--previous`で渡すと、Repositoryが`PlanRecord`へ変換し、運用者の指定の
`previous_plan`としてOptimizerとValidatorへ同じ値を渡します。この版のOptimizerとValidatorは使わず、前回からの
移動の数（FRM-071、FRM-037の⑦）は分割案の5で加えます。`TeamBuilder`は今回の参加者一覧に当たらない人数だけを
数え、CLIは編成に使わないことを標準エラーへ示し、出力した実行（終了コード0）では、その人数を名前なしで示します（作成者の仮定A-42の(6)）。前回の編成は回答を確かめる手順に
影響しないため、FRM-090の性質(1)は前回の編成を変えた実行でも同じく成り立ちます（作成者の仮定A-42）。

## 設定の永続化境界

設定は、Repositoryで管理する常設の既定値（チームマスタ）と、イベントごとに運用者が渡す指定
（`settings.json`）に分けます（ADR 0034）。どちらもインターフェース層の組み立て
（CLIでは`interfaces/cli/composition.py`）がRepositoryから読み込み、チームマスタは`KvKRules`として、
運用者の指定は`OperatorSpecification`としてユースケースへ渡します。ユースケースはRepositoryに
依存しません。

```text
TeamMasterRepository (Protocol)
    └── JsonTeamMasterRepository        team_master.json（--team-master、省略時は同梱）
OperatorSpecificationRepository (Protocol)
    └── JsonOperatorSettingsRepository  settings.json（--settings、省略時は同梱の架空の例）
AnswersRepository (Protocol)
    └── JsonAnswersRepository           answers.json（--answers、省略時は回答なし）
PlanRecordRepository (Protocol)
    └── JsonPlanRecordRepository        編成のJSON（--previous、省略時は前回の編成なし）。書き出しはrender_plan_record
```

編成のJSON（DAT-010）は、出力するたびにイベントのフォルダの`output/<実行の時刻>/`（Git管理外）へ書き、前回の
編成として読み戻します。版（`schema_version` 1）を持ち、違う版、未知の項目、型の誤り、成り立たない記録（同じ
メンバーが2回、同じ番号の隊など）は、名前を書かずに位置と項目で示して読み込みエラーにします。

運用者の回答（DAT-009）は、番号付きの質問への答えで、イベントのフォルダ（Git管理外）の`answers.json`に置きます。
編成の前に決める指定（`settings.json`）と分けます（ADR 0035）。Repositoryは形式の変換だけを行い、回答の妥当性は
ドメインとアプリケーションが確かめます。

チームマスタ（`schema_version` 2）は、イベント開始と終了と、第4隊以降の出撃人数の上限
（`member_cap`）だけを持ち、名前を含みません。以前の形（`schema_version` 1。隊ごとの集結主、
代理集結主、役割、運用メモ、戦力関係）は、移し方を示して読み込みエラーにします。

運用者の指定は、イベントのフォルダ（Git管理外）の`settings.json`に置きます（DAT-001、DAT-007、
ADR 0029）。現在は`leaders`だけを読み、DAT-007のほかのキーは、後のIssueで実装するまで黙って
無視せず、キーを示して読み込みエラーにします。同梱の`settings.example.json`は`sample/`の架空の
リーダーで、`--settings`の省略時に使い、標準エラーへ注意を出します。

JSON固有の辞書はRepository内で`TeamMaster`、`EventTimeSettings`、`OperatorSpecification`、`Answer`、`PlanRecord`へ
変換します。Optimizer以降はファイルパスやJSON構造を認識しません。上位隊の3隊×8人、出撃人数の
下限の基本8人、延長境界時刻の24:00、30分単位の時間帯は利用者が決めた固定値で、`domain/team.py`の
定数とします。戦力関係`第1隊 > 第2隊 >= 第3隊`は固定値ではなく、分割案の3でFRM-027へ置き換えるまで
維持する現行の規則として同じファイルに置きます（ADR 0034）。

## ドメインモデル

### 参加者（Member）

名前、同盟、Tier、VC可否、参加開始・終了時刻を持つ不変dataclassです。
同盟情報がない場合は`未設定`を使用します。同盟は現行の目的関数では評価しません。

別枠（参加時間未定）はMember固有の属性ではありません。毎回の参加開始時刻が確定しているか
によって`AvailabilityResolver`が判定します。

### 運用者の指定（OperatorSpecification）

1回の編成で運用者が渡す指定を1つの不変な値にまとめ、OptimizerとValidatorへ同じ値を渡します。
リーダー一覧（`MemberRef`の組。名前と同盟）を持ち、並び順が隊の番号です。回答から受け入れた遅れて出撃する隊
（`LateStart`。隊、出撃開始時刻、応援`SupportRef`の一覧）を`late_starts`に持ちます（ADR 0035）。前回の編成などは、
要件のあるIssueで加えます。リーダーは`resolve_leaders`で参加者一覧のメンバーへ解決し、1人に決まらなければ
`SpecificationError`（入力のエラー）にします。回答（`Answer`）は、問いの対象の（隊、時間帯）と`LateStart`を持ちます。

### 所属固定の編成（TeamPlan）

隊ごとの`TeamMembership`（番号、リーダー、所属メンバー）、待機、別枠を保持します。所属は時間帯を
またいで変わらず、同じメンバーが時間帯ごとに別の隊へ移ることを表現できません。時間帯ごとの出撃
（`Sortie`）は`sorties`が所属と参加時間、応援から計算します。参加時間未定のリーダーは別枠に置き、
`TeamMembership.members`へ含めません。

遅れて出撃する隊は`TeamMembership.start_minutes`に出撃開始時刻を持ち、出撃開始前の時間帯は所属メンバーを出撃させ
ません。応援（`Support`。メンバー、時間帯、応援先）は`TeamPlan.supports`に持ち、応援先の出撃（`Sortie.supporters`）に
数えます。出撃人数（`Sortie.head_count`）は所属メンバーと応援の合計で、休止は所属メンバーだけで判定します。

## 時間の解決

イベント時間は現在21:00〜25:00、刻みは30分です。参加区間は開始時刻を含み、
終了時刻を含みません。

```text
21:30〜22:30
    → 21:30〜22:00スロットに参加
    → 22:00〜22:30スロットに参加
```

開始時刻が完全に未定の場合は【別枠】参加時間未定へ分離します。`遅れるかも`だけでは別枠に
しません。終了時刻がない途中抜けは、既存の優先度に基づいて保守的に補完します。参加時間未定の
読み方の拡張（時刻のない途中参加など）は実装Issueの1で行います。

## CP-SATモデル

時間確定メンバー`m`と隊`t`について所属のBool変数`x[m, t]`を、メンバーごとに待機のBool変数`w[m]`を
作成します。時間帯`s`の出撃人数は、`s`の全体に参加している`m`の`x[m, t]`の和です。

### 必須制約

1. 各メンバーはちょうど1つの隊か待機（`x`と`w`の和が1）
2. 参加時間が確定したリーダーは自分の隊に所属
3. 第1〜3隊は各時間帯でリーダー在席なら8人、不在なら7人
4. 第1〜3隊の所属メンバーは全員VC可能で、リーダー以外は全時間帯に参加する人に限る（FRM-020〜FRM-022）。
   時間帯ごとの人数だけでは、途中で抜ける人と途中から来る人の入れ替わりを許すため、所属の変数で禁じる
5. 第4隊以降の出撃人数は`member_cap`以下
6. 全時間帯で、第1〜3隊のTier戦力の合計が`第1隊 > 第2隊 >= 第3隊`

7. 遅れて出撃する隊の出撃開始前の時間帯は、人数、休止、上限の対象にしない
8. 応援するメンバーはその遅れて出撃する隊に所属し（作成者の仮定A-16）、応援先のない出撃開始前の参加者は
   遅れて出撃する隊に所属しない（FRM-047）
9. 応援先の出撃人数（所属メンバーと応援の合計）は`member_cap`以下で、応援を受ける時間帯に所属メンバーが1人以上
   参加する（FRM-042、FRM-048）
10. `allowed_shortfalls`を渡した場合は、延長境界時刻より前の休止をその（隊、時間帯）だけに限る（回答の受け入れの確認）

最適化の前に、第1〜3隊のリーダーのVCと、全時間帯に参加するVC可能なメンバーの人数を確かめ、
足りなければ理由を示して`ProvenInfeasible`を返します。応援先がほかの遅れて出撃する隊の出撃開始前に当たる場合も、
理由を示して`ProvenInfeasible`を返します。

### 目的関数

次の段を辞書式に比べます。各段の重みは、それより下の段の取り得る幅の合計より大きくします。

1. 延長境界時刻（24:00）より前の休止の（隊、時間帯）の数
2. 延長境界時刻より前で、出撃人数が8人に足りない人数の2乗の和
3. 延長境界時刻以降の休止の（隊、時間帯）の数
4. 延長境界時刻以降で、8人に足りない人数の2乗の和
5. 待機の人数
6. 第1〜3隊の戦力（大きいほどよい。第1隊を重く数える）

2と4は暫定の指標です。FRM-031の「8人未満の（隊、時間帯）の数」は、6人以下を禁じるFRM-039と組で
入れないと少数の隊を捨てる編成を選ぶため、Issue 3でFRM-037の指標とともに置き換えます（ADR 0034）。
同盟分散は評価しません。

## 検証（Validator）

Optimizerとは独立して、参加者一覧と運用者の指定から次を再計算します。

- 所属の重複、参加者一覧にいないメンバー、隊にも待機にもいない確定参加者
- 別枠が参加時間未定のメンバーと一致すること
- 隊の数と番号がリーダー一覧と一致し、リーダーが自分の隊に所属すること
- 第1〜3隊の所属人数（リーダーを含めて8人、別枠のリーダーの隊は7人）、リーダー以外の常時稼働
  （`TOP_TEAM_ALWAYS`）、所属メンバーのVC、各時間帯の人数（リーダー在席なら8人、不在なら7人）
- 第4隊以降の出撃人数の上限
- `第1隊 > 第2隊 >= 第3隊`
- 延長境界時刻より前の休止（下限の不足。`ValidationReport.shortfalls`）
- 出撃開始時刻と応援が運用者の指定と一致すること（`SPECIFICATION_MISMATCH`）
- 遅れて出撃する隊が第4隊以降で、出撃開始時刻が戦闘開始より後の区切りにあること（`LATE_START`）
- 応援が、遅れて出撃する隊の出撃開始前の所属メンバーによるもので、その時間帯に参加し、応援先が第5隊以降の
  ほかの隊で出撃開始以降かつ休止中でないこと。出撃開始前に参加する所属メンバーに時間帯ごとの応援先があること
  （`SUPPORT`）。指定と一致していても条件を満たさない編成を拒否する（FRM-047）
- 出撃人数（応援を含む）、戦力、VC人数、在席のリーダー。出撃開始前の時間帯は人数、休止、リーダー不在を判定しない

第4隊以降の8人未満、リーダー不在（上位隊の7人を含む。FRM-029）、延長境界時刻以降の休止は警告です。
必須条件エラーと警告を分離することで、成立した編成を出力しつつ運用上のリスクを残します。

## 出力

Exporterは隊ごとに「第N隊 リーダー: 名前」（別枠のリーダーの隊は「リーダー不在」）の見出し、遅れて出撃する隊の
出撃開始時刻、所属メンバーを出力し、応援（ある場合）、待機、【別枠】参加時間未定、時間帯別の出撃、注記（ある場合）、
自己チェックと警告を続けます。番号付きの質問の文は`adapters/output/shortfall_question_text.py`が作り、CLIが
標準エラーへ出します。
チャット共有用テキスト（OUT-001〜OUT-014）への置き換えは実装Issueの6で行います。

## Web UI境界とデザイン

将来のWeb UIは入力側と出力側のAdapterとして、アプリケーションのユースケースを
呼び出します。編成人数、VC、リーダー、戦力関係、警告判定をUIへ再実装しません。
Web表示は`ValidatedTeamPlan`と明示的な失敗型を、編成中、検証済み、警告あり、出力不可の
状態へ変換します。

UIの設計とレビューは`.agents/skills/apple-design/SKILL.md`を基準にします。外観の模倣では
なく、即時Feedback、予測可能な空間関係、中断可能な操作、読みやすい文字組み、節度ある
Material表現を適用します。低モーション、低透明度、高Contrast、Keyboard、Focus、文字拡大を
同じComponentの要件として扱い、警告と必須条件エラーを色だけで区別しません。

Interactionのために主要なUI FrameworkまたはAnimation Libraryを追加する場合は、既存基盤の
不足、代替案、Bundleと保守への影響をADRに記録します。基盤が高度なGestureを提供しない場合は、
装飾用の依存を増やさず、主要経路のFeedback、状態表現、可読性を優先します。

## ブラウザ用補助ツールの境界

`web/`のHTMLツールは、Python側のどのコンテキストにも依存しない独立したツールです。
行軍秒数、集結時間、占領時間、周期などの計算は、新しいアプリの「戦闘タイミング」
（`battle_timing`）へ移植し、置き換えが済んだツールから削除します（ADR 0021、#32）。
置き換えが済むまでは各HTMLが実装の正本であり、編成のユースケースを呼び出しません。

各ツールの要件の正本は`docs/requirements/web-tools/`の要件定義書であり、HTMLは実装の正本です。
両者が食い違う場合は、利用者の判断に基づいて同じ変更でそろえます（ADR 0020）。

`web/`はRuff、mypy、pytestの対象外です。HTMLの計算をPythonへ移植するときは、
要件定義書の要件IDをテストの期待値にし、移植中のHTMLとPythonの食い違いを要件定義書で
判断します。

集結タイムライン計算と周期ウェーブタイマーは、実物のHTMLをNode.jsとjsdomで読み込み、画面と同じ
操作で動かす`tests/web/`の検査で確かめます。カウントダウン表は、集結タイムライン計算と共有する速度ペットの
ボーナスだけを同じ方法で確かめます（ADR 0031）。`tools/check_web.py`が`python tools/check.py`の1項目として
実行し、Node.jsまたはjsdomがなければ入れ方を示して失敗します。Node.jsの版は`.node-version`、jsdomの
版は`package.json`と`package-lock.json`で固定します（ADR 0030）。画面幅による表示の違いは、Dev Containerの
Playwright MCPで実際のブラウザを操作して確かめます。品質ゲートには含めません（ADR 0032）。

ツールどうしは同じoriginのlocalStorageでつながります。集結タイムライン計算は計算のたびに
`siegeTimelineForWaveTimer`へ結果を書き、周期ウェーブタイマーはそれを読むだけで、書き換えません。
速度ペットのボーナスは、集結タイムライン計算とカウントダウン表が共通部品`web/pet-bonus.js`で
同じキーに保存します（ADR 0031）。

## エラー方針

- 入力構造の不備: `ParseError`
- JSONマスタの不備: `TeamMasterLoadError`
- 運用者の指定の不備: `OperatorSettingsLoadError`（ファイル）、`SpecificationError`（リーダーが参加者一覧で
  1人に決まらないなど）
- 運用者の回答の不備: `AnswersLoadError`（ファイル）、`SpecificationError`（ほかの指定によらない回答の誤り）
- 最適化の失敗: `OptimizationError`
  - 解の有無を確定する前に探索の制限へ達した: `OptimizationTimeoutError`
- 必須条件を満たす編成を出力できない: `BuildError`
  - CP-SATが解の不存在を証明した（`ProvenInfeasible`の理由を示す）: `NoValidPlanError`
  - 最適な編成でも延長境界時刻より前の休止が残る（番号付きの質問と注記を持つ）: `LowerBoundShortfallError`
  - 最適だと示せないまま休止が残る（時間切れ）: `ShortfallUndeterminedError`
- 時間切れの共通の型: `SearchTimeoutError`（`application/ports.py`）。`OptimizationTimeoutError`と
  `ShortfallUndeterminedError`が継承する

Optimizerは時間切れ（`UNKNOWN`）を解の不存在（`INFEASIBLE`）として報告しません。解の不存在は
`ProvenInfeasible`として返し、例外にしません（ADR 0034）。CLIは、`LowerBoundShortfallError`を番号付きの質問として
終了コード3、`SearchTimeoutError`を終了コード4、ほかの入力のエラーと`BuildError`を終了コード2で終えます（ADR 0035）。

CP-SATの探索は既定で実時間を上限にし、8 workerで並列実行するため、実行環境の速さと
負荷で結果が変わります。再現性が必要な場合は`KvKRules.maximum_deterministic_time`で
決定的時間を上限にし、`solver_worker_count`を1にします。テストはこの設定を使用します
（ADR 0019）。
- 事後検証が規定回数失敗: `BuildError`

CLIはこれらを捕捉し、不完全な出力を正常結果として扱いません。

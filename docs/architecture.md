# アーキテクチャ

## 設計方針

このシステムは「KvKチーム編成」をコアドメインとする、戦術的DDDを取り入れた
モジュラーモノリスとして設計します。境界づけられたコンテキストは「KvKチーム編成」と
「戦闘タイミング」の2つです（ADR 0021）。Markdown入力、JSON永続化、OR-Tools、CLI、
Web UIはドメインの外側に置きます。以下の処理フローとCP-SATモデルは「KvKチーム編成」の
現行の実装です。所属固定のモデルなどの目標仕様は`docs/requirements/team-building/`にあり
（ADR 0023）、実装Issueが完了するたびにこの文書へ反映します。

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
`Member`の一覧を受け取り、検証済み編成`ValidatedTeamPlan`を返します。機能変更と大規模移動を
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
web/                 既存の単体HTMLツール。置き換えが済んだものから削除する
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
team_master.json ─→ JsonTeamMasterRepository ─→ TeamMaster
                                                ↓
参加者一覧.md ─→ MarkdownMemberParser ─→ list[Member]
                                                ↓
                                   AvailabilityResolver
                                      ↙             ↘
                              時間確定          時間確定待ち
                                  ↓                  ↓
                          TimeSlotTeamOptimizer      │
                                  ↓                  │
                           DynamicTeamPlan ←─────────┘
                                  ↓
                         DynamicTeamValidator
                    ↓ 必須条件OK       ↘ NGなら再試行（上限でBuildError）
              ValidatedTeamPlan（編成＋警告・指標・待機）
                                  ↓
                    DynamicMarkdownExporter
                                  ↓
                           チーム編成.md
```

アプリケーションのユースケース`BuildTeamPlan`が、Optimizer、ValidatorをProtocol経由で調整し、
再試行します。Validatorが必須条件を満たすと判定した編成だけが`ValidatedTeamPlan`になり、
必須条件エラーを含む検証結果からは生成できません。CLIの`TeamBuilder`
（`interfaces/cli/team_builder.py`）は、Markdownの解析、`BuildTeamPlan`、Exporterをこの順に
呼び出すだけです。Exporterは`ValidatedTeamPlan`だけを受け取るため、未検証の候補を誤って出力できません。
`ValidatedTeamPlan`が型で保証するのは「検証結果に必須条件エラーがない」ことだけで、その検証結果が
同じ編成のものであることは、`BuildTeamPlan`が生成する前提で守ります。ほかの経路で生成しません。

## マスタ永続化境界

集結主やチーム人数をPythonコードから分離するため、チームマスタは`TeamMasterRepository`の実装から
読み込みます。読み込みはインターフェース層の組み立て（CLIでは`interfaces/cli/composition.py`）が
行い、`KvKRules`としてユースケースと各部品へ渡します。ユースケースはRepositoryに依存しません。

同梱の`team_master.json`は公開用の例で、集結主、代理集結主、役割、運用メモは架空です。CLIの`--team-master`で
Git管理外のJSONを指定すると、`composition.py`の`default_rules`が同梱の代わりにそれを
`JsonTeamMasterRepository`で読み込みます。省略時は同梱の例を使います（ADR 0026）。

```text
TeamMasterRepository (Protocol)
    ├── JsonTeamMasterRepository  現在
    └── DatabaseTeamMasterRepository  将来
```

JSON固有の辞書はRepository内で`TeamMaster`、`TeamDefinition`、
`EventTimeSettings`へ変換します。Optimizer以降はファイルパスやJSON構造を
認識しません。Webアプリ化後も、DB Adapterを追加して同じドメインモデルを返せば
サービスと最適化ロジックを再利用できます。

JSONマスタには次を保持します。

- スキーマバージョン
- イベント開始、終了、時間刻み
- チームラベル、集結主、代理集結主
- 表示用の役割と運用メモ
- チームごとの目標人数と最大人数
- VC必須チーム
- チーム間の戦力関係

同盟ごとのチーム所有情報や役割適性は、属性が確定した段階でマスタへ追加できます。

## ドメインモデル

### 参加者（Member）

名前、同盟、Tier、VC可否、参加開始・終了時刻を持つ不変dataclassです。
同盟情報がない場合は`未設定`を使用します。同盟は現行の目的関数では評価しません。

流動枠や待機枠はMember固有の属性ではありません。毎回の参加開始時刻が確定しているか
によって`AvailabilityResolver`が判定します。

### 動的編成（DynamicTeamPlan）

チームと30分スロットごとの`SlotAssignment`、および今回の`standby_members`を
保持します。同じメンバーが異なる時間帯に別チームへ移ることを表現できます。

## 時間の解決

イベント時間は現在21:00〜25:00、刻みは30分です。参加区間は開始時刻を含み、
終了時刻を含みません。

```text
21:30〜22:30
    → 21:30〜22:00スロットに参加
    → 22:00〜22:30スロットに参加
```

開始時刻が完全に未定の場合は待機枠へ分離します。`遅れるかも`だけでは待機扱いに
しません。終了時刻がない途中抜けは、既存の優先度に基づいて保守的に補完します。

## CP-SATモデル

時間確定メンバー`m`、チーム`t`、時間スロット`s`について、参加可能な組だけ
Bool変数`x[m, t, s]`を作成します。

### 必須制約

1. 参加中の各メンバーは各スロットで1チームだけに所属
2. 各チームの同時配置はJSONマスタの最大人数以下
3. A〜Cは全スロットで8人
4. A〜Cへ配置する全員がVC可能
5. 参加中の固定集結主を指定チームへ固定
6. 固定集結主が不在なら参加中の代理集結主を固定
7. 全スロットで`A > B >= C`

D〜Kの8人は目標値です。参加者総数が足りない場合も実行可能とし、Validatorが
時間帯と不足人数を警告します。

### 目的関数

次の順で損失を抑えます。数値は`ObjectiveWeights`へ集約しています。

1. D〜Kの8人未満
2. 継続参加中のチーム移動
3. 9人目の配置
4. A〜Cへの戦力配分

同盟分散は評価しません。役割適性も現時点では表示情報であり、メンバー属性の追加後に
独立した制約として実装します。

## 検証（Validator）

Optimizerとは独立して、各30分スロットで次を再計算します。

- 確定参加者の重複、未配置、参加時間外配置
- チーム別の最大人数とA〜Cの固定人数
- A〜CのVC
- 固定集結主と代理集結主
- `A > B >= C`
- 人数、戦力、VC人数、稼働中の集結主

D〜Kの8人未満、固定集結主と代理の到着待ちは警告です。到着待ちは、その時間帯に固定集結主も
代理も参加していない状態を指し、まだ到着していない場合と途中で離脱した場合を区別しません。
必須条件エラーと警告を
分離することで、成立した編成を出力しつつ運用上のリスクを残します。

## 出力

Exporterは各チームについて21:00の初期配置を出力し、次のスロットとの差分から
退出・参加を生成します。時間確定待ち、全時間帯の集計、必須条件、警告を末尾へ
付加します。

## Web UI境界とデザイン

将来のWeb UIは入力側と出力側のAdapterとして、アプリケーションのユースケースを
呼び出します。編成人数、VC、集結主、戦力関係、警告判定をUIへ再実装しません。
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

`web/`の単体HTMLツールは、Python側のどのコンテキストにも依存しない独立したツールです。
行軍秒数、集結時間、占領時間、周期などの計算は、新しいアプリの「戦闘タイミング」
（`battle_timing`）へ移植し、置き換えが済んだツールから削除します（ADR 0021、#32）。
置き換えが済むまでは各HTMLが実装の正本であり、編成のユースケースを呼び出しません。

各ツールの要件の正本は`docs/requirements/web-tools/`の要件定義書であり、HTMLは実装の正本です。
両者が食い違う場合は、利用者の判断に基づいて同じ変更でそろえます（ADR 0020）。

`web/`はRuff、mypy、pytestの対象外です。HTMLの計算をPythonへ移植するときは、
要件定義書の要件IDをテストの期待値にし、移植中のHTMLとPythonの食い違いを要件定義書で
判断します。

## エラー方針

- 入力構造の不備: `ParseError`
- JSONマスタの不備: `TeamMasterLoadError`
- 必須条件が成立しない: `OptimizationError`
  - CP-SATが解の不存在を証明した: `InfeasibleRosterError`
  - 解の有無を確定する前に探索の制限へ達した: `OptimizationTimeoutError`

Optimizerは時間切れ（`UNKNOWN`）を解の不存在（`INFEASIBLE`）として報告しません。
どちらも`OptimizationError`の派生のため、境界での捕捉と終了コードは共通です。

CP-SATの探索は既定で実時間を上限にし、8 workerで並列実行するため、実行環境の速さと
負荷で結果が変わります。再現性が必要な場合は`KvKRules.maximum_deterministic_time`で
決定的時間を上限にし、`solver_worker_count`を1にします。テストはこの設定を使用します
（ADR 0019）。
- 事後検証が規定回数失敗: `BuildError`

CLIはこれらを捕捉し、不完全な出力を正常結果として扱いません。

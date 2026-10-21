# ドメインモデル

## コアドメインと境界

コアドメインは「KvKチーム編成」です。1回のKvKイベントについて、参加可能な`Member`を
時間帯ごとに`Team`へ割り当て、必須条件を満たした編成と運用上の警告を生成します。

境界づけられたコンテキストは次の2つです（ADR 0021）。

| コンテキスト | パッケージ | 責務 |
|---|---|---|
| KvKチーム編成 | `team_building` | 参加可能な参加者を時間帯ごとにチームへ割り当て、必須条件と警告を扱う |
| 戦闘タイミング | `battle_timing` | 行軍秒数、到着の同期、集結タイムライン、周期、占領時間の判定を秒単位で扱う |

コンテキストどうしは互いをimportせず、モデルを共有しません。同じ語を両方で使う場合も、
それぞれのコンテキストで意味を定義します。入力解析、永続化、ソルバー、表示方式ごとには
コンテキストを作りません。それらは各コンテキストへ接続するアダプターまたは
インフラストラクチャです。

## ユビキタス言語: KvKチーム編成（`team_building`）

| 日本語 | コード上の用語 | 意味 |
|---|---|---|
| 参加者 | `Member` | 名前で識別され、Tier、VC、参加可能時間を持つエンティティ |
| 参加可能時間 | `Availability` | `Member`が配置可能な半開区間と時間確定状態 |
| 時間枠 | `TimeSlot` | 開始を含み終了を含まない編成単位 |
| チーム | `Team` / `TeamLabel` | A〜Kで識別される配置先 |
| チーム定義 | `TeamDefinition` | 集結主、代理、人数、VCなどのポリシー値 |
| チームマスタ | `TeamMaster` | イベント時間と全Teamのポリシーを持つ不変なドメイン設定 |
| 編成候補 | `DynamicTeamPlan` | 全時間枠の配置と待機`Member`を持つ、検証前の候補 |
| 検証済み編成 | `ValidatedTeamPlan` | 必須条件を満たすことを確認した出力可能な編成と、その検証結果（警告、指標、待機）。必須条件エラーを含む検証結果からは生成できない |
| 必須条件 | `Invariant` | 違反時に編成を出力しないドメインルール |
| 警告 | `Warning` | 編成を出力しながら運用者へ知らせる不足 |
| 目的関数 | `Objective` | 複数の有効な編成から望ましいものを選ぶ優先度 |
| 固定集結主 | `RallyLeader` | 指定`Team`へ固定される`Member` |
| 代理集結主 | `SubstituteLeader` | 固定集結主不在時に指定`Team`へ置く`Member` |
| 待機 | `Standby` | 開始時刻未確定のため配置へ算入しない状態 |

目標仕様（`docs/requirements/team-building/`、ADR 0023）では、所属を固定した「隊」、リーダー、
代理リーダー、上位隊、別枠、出撃人数、応援などの用語を使います。対応の候補は要件定義書の用語表に
あり、実装Issueで導入するときにこの表へコード上の用語を追加します。特に、目標仕様の「待機」は
人数の上限のためにどの隊にも所属できなかったメンバーを指し、現行の待機（`Standby`）とは別の
概念です。現行の`Standby`は、目標仕様の別枠（参加時間未定）に当たります。`Standby`を目標仕様の
待機へ流用しません。

新しいコードで`Participant`、`RosterMember`、`Squad`などの同義語を増やしません。用語を
変更する場合は、コード、文書、入出力の影響をADRで決定します。

## ユビキタス言語: 戦闘タイミング（`battle_timing`）

日本語の用語は`docs/requirements/web-tools/`の要件定義書に合わせます。コード上の用語は、
各機能を実装するIssue（#6、#7、#29、#30）で決め、この表へ追記します。

| 日本語 | 意味 | 要件定義書 |
|---|---|---|
| 行軍秒数 | 部隊が出発してから目標へ着くまでの秒数 | `sync-start-tables.md`、`siege-timeline.md` |
| 実際秒数 | 行軍秒数に補正（到着+）を加えた秒数 | `sync-start-tables.md` |
| 同着 | 行軍秒数の異なる部隊を同時に到着させること | `sync-start-tables.md` |
| 役割 | 集結作戦での「メイン」「増援」「削り」 | `siege-timeline.md` |
| パターン | 一度に着弾させる削りの組み合わせ | `siege-timeline.md` |
| 発起／着弾／帰還 | 集結の開始、目標への到着、部隊の戻り | `siege-timeline.md` |
| 周期 | 同じパターンが次の周で再び着弾するまでの秒数 | `siege-timeline.md`、`wave-timer.md` |
| 占領時間 | 同盟が累計で占領した秒数 | `occupation-judge.md` |
| 確定まで | 勝利が確定するまでに追加で必要な占領時間 | `occupation-judge.md` |

「集結」は両方のコンテキストに現れますが、「KvKチーム編成」の固定集結主（`RallyLeader`）と、
「戦闘タイミング」の集結作戦の役割は別の概念です。モデルを共有しません。

## 戦術的モデル

### エンティティ

- `Member`: 現在は正規化した名前を識別子として扱う。将来名前変更や同名参加者が必要に
  なった時点で`MemberId`値オブジェクトを導入する

### 値オブジェクトとドメインポリシー

- `Tier`, `Availability`, `TimeSlot`, `TeamLabel`
- `EventTimeSettings`, `TeamDefinition`, `StrengthRelation`, `ObjectiveWeights`
- `TeamMaster`, `KvKRules`: 1イベントの編成ポリシーを構成する不変値

### 集約と結果型

`DynamicTeamPlan`は全時間枠の整合性をまとめて扱う編成候補です。Optimizerが候補を作り、
独立Validatorが検証します。必須条件を満たした候補だけが、検証結果と一緒に`ValidatedTeamPlan`
になります。Exporterは`ValidatedTeamPlan`だけを受け取るため、未検証の候補を誤って出力できません。

`TeamMaster`は一貫して読み込むポリシー集合です。各`Member`や`Team`へ形式的な
Repositoryを作らず、永続化の整合単位が明確なものにだけRepository境界を置きます。

### ドメインサービス

- 参加可能時間の解決と時間枠への分割
- 編成の必須条件検証と警告生成
- ソルバーへ渡す編成ポリシーの表現

CP-SATの変数や係数操作はOR-Toolsアダプターの責務です。必須条件、警告、目的関数の意味は
ドメインに残し、ソルバー固有表現をドメインモデルへ漏らしません。

## レイヤー責務

### ドメイン

外部I/Oを行わず、Python標準の値とCollectionで業務概念を表します。ドメインのテストは
Markdown、JSON、ファイルパス、OR-Toolsを必要としない形を目標とします。

### アプリケーション

ユースケース`BuildTeamPlan`はドメイン型の`Member`一覧を受け取り、Optimizer境界とValidator境界を
調整して`ValidatedTeamPlan`を返します。再試行と、上限に達したときの`BuildError`を持ちますが、
Markdownの解析・出力や、編成人数、VC条件そのものは決めません。チームマスタは、呼び出し側が
Repositoryから読み込んで`KvKRules`に渡します。

入力の解析と出力はインターフェース層が組み立てます。CLIでは`interfaces/cli/team_builder.py`の
`TeamBuilder`が、Markdown Parser、`BuildTeamPlan`、Markdown Exporterをこの順に呼び出します。
Web Interface（#21）は、同じ`BuildTeamPlan`を別の入出力で呼び出します。

### アダプターとインフラストラクチャ

- 入力側: CLI、将来のWeb UI、Markdown参加者Parser
- 出力・接続側: JSONチームマスタRepository、OR-Tools CP-SAT Optimizer
- 表示側: Markdown Exporter、将来のWeb View Model Mapper

アダプターは外部データをドメイン型へ変換し、外部形式固有の辞書、正規表現、ファイルパス、
ソルバー型を内側へ渡しません。

## パッケージ構造

```text
src/kvk_team/
  team_building/
    domain/
      member.py           参加者、Tier、参加可能時間
      schedule.py         時間枠、編成候補
      team.py             チーム
      team_master.py      チームマスタ、チーム定義、戦力関係
      rules.py            編成ルール（チームマスタを必須で受け取る）
      availability.py     参加可能時間の解決
      validation.py       必須条件の独立検証、警告、ValidatedTeamPlan
    application/
      ports.py            Optimizer、Validator、Repositoryの境界
      build_team_plan.py  最適化、検証、再試行を調整し、ValidatedTeamPlanを返すユースケース
    adapters/
      input/markdown_member_parser.py
      output/dynamic_markdown_exporter.py
      persistence/json_team_master_repository.py、team_master.json
      optimization/cp_sat_team_optimizer.py、errors.py
  battle_timing/          （各機能のIssueで追加する）
    domain/
    application/
    adapters/
  interfaces/
    cli/                  main.py、__main__.py、composition.py（既定部品の組み立て）、
                          team_builder.py（解析、ユースケース、出力の順に呼び出す）
    web/                  （#21で追加する）
```

`team_building`は上の配置へ移行済みです（ADR 0021、#28）。`battle_timing`のモジュールは各機能の
Issueで決めます。ADR 0003の移行段階の状況は次のとおりです。

1. 名前空間パッケージとドメイン型を受け取るユースケース`BuildTeamPlan`を作る（完了）
2. 外部依存のないドメインモデル、ポリシー、検証処理を移す（完了）
3. Markdown Parser、JSON、CP-SAT、表示変換、CLIをアダプターとして移す（完了）
4. `ValidatedTeamPlan`を導入し、出力境界を型で閉じる（完了）
5. 旧最上位パッケージを削除し、依存方向の自動検査を品質ゲートへ追加する（完了。
   `tests/test_dependency_direction.py`）

## 非目標

- 境界ごとのマイクロサービス化
- CQRSまたはイベントソーシング
- CRUDエンティティごとのRepository
- すべての処理を集約Methodへ押し込むこと
- DDD用語を増やすだけの抽象化

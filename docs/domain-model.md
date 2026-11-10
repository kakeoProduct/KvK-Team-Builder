# ドメインモデル

## コアドメインと境界

コアドメインは「KvKチーム編成」です。1回のKvKイベントについて、リーダー一覧から作る隊へ
参加時間が確定した`Member`の所属を固定して割り当て、時間帯ごとの出撃を所属と参加時間から計算し、
必須条件を満たした編成と運用上の警告を生成します。

境界づけられたコンテキストは次の2つです（ADR 0021）。

| コンテキスト | パッケージ | 責務 |
|---|---|---|
| KvKチーム編成 | `team_building` | 参加者を隊へ所属させ、時間帯ごとの出撃、必須条件、警告を扱う |
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
| 隊 | `TeamMembership`、番号は`int` | 所属が固定されたメンバーの集まり。リーダー一覧の番号で第1隊から数える |
| 上位隊 | `is_top_team`、`TOP_TEAM_COUNT` | 第1〜3隊。リーダーを含めて8人固定（`TOP_TEAM_SIZE`。別枠のリーダーの隊は7人）で、リーダー以外は全時間帯に参加する |
| リーダー | `TeamMembership.leader` | 隊を率いるメンバー。リーダー一覧の順が隊の番号になる |
| 所属 | `TeamMembership.members` | メンバーが属する隊。時間帯をまたいで変わらない |
| 出撃 | `Sortie` | ある時間帯に隊として出撃するメンバー。所属メンバーのうち参加している人 |
| 休止 | `ValidationCode.REST` | 所属メンバーの参加が0人になる時間帯。延長境界時刻より前は下限の不足 |
| 延長境界時刻 | `EXTENSION_BOUNDARY_MINUTES` | 24:00。人数不足を延長保留として扱い始める時刻 |
| 待機 | `TeamPlan.waiting` | 人数の上限のため、どの隊にも所属しないメンバー（FRM-033） |
| 別枠 | `TeamPlan.undecided` | 参加時間未定のため、どの隊にも入れないメンバー（FRM-060） |
| 運用者の指定 | `OperatorSpecification` | 1回の編成で運用者が渡す指定の不変な値。現在はリーダー一覧（`MemberRef`の組） |
| チームマスタ | `TeamMaster` | 戦闘時間と出撃人数の上限を持つ常設の既定値 |
| 編成候補 | `TeamPlan` | 隊ごとの所属、待機、別枠を持つ、検証前の候補 |
| 検証済み編成 | `ValidatedTeamPlan` | 必須条件を満たすことを確認した出力可能な編成と、その検証結果（警告、出撃の指標、待機、別枠）、最適性。必須条件エラーを含む検証結果からは生成できない |
| 必須条件 | `Invariant` | 違反時に編成を出力しないドメインルール |
| 警告 | `Warning` | 編成を出力しながら運用者へ知らせる不足 |
| 目的関数 | `Objective` | 複数の有効な編成から望ましいものを選ぶ優先度 |

上の表は所属固定のモデル（ADR 0034）の用語です。応援、出撃開始時刻、代理リーダー（当面置かない、
FRM-003）などの目標仕様の用語は、要件定義書の用語表にあり、実装Issueで導入するときにこの表へ
追加します。以前の固定集結主（`RallyLeader`）、代理集結主（`SubstituteLeader`）、時間帯ごとに移れる
`DynamicTeamPlan`、開始時刻未確定の`Standby`は使いません。以前の`Standby`は別枠に当たり、
待機とは別の概念です。

新しいコードで`Participant`、`RosterMember`、`Squad`などの同義語を増やしません。用語を
変更する場合は、コード、文書、入出力の影響をADRで決定します。

## ユビキタス言語: 戦闘タイミング（`battle_timing`）

日本語の用語は`docs/requirements/web-tools/`の要件定義書に合わせます。コード上の用語は、
各機能を実装するIssue（#6、#7、#29、#30）で決め、この表へ追記します。

| 日本語 | 意味 | 要件定義書 |
|---|---|---|
| 行軍秒数 | 部隊が出発してから目標へ着くまでの秒数。集結タイムライン計算とカウントダウン表では、速度ペットを採用すると`÷ (1 + ボーナス ÷ 100)`で縮める。集結タイムライン計算は縮めた秒数を四捨五入して使い、カウントダウン表は遅延秒数を加えた後に四捨五入する（実際秒数） | `sync-start-tables.md`、`sync-start-countdown.md`、`siege-timeline.md` |
| 実際秒数 | 同着の計算に使う到着までの秒数。カウントアップ表では行軍秒数に補正（到着+）を加えた秒数、カウントダウン表では行軍秒数（速度ペットを採用していれば縮めた秒数）に遅延秒数を加え、四捨五入した整数 | `sync-start-tables.md`、`sync-start-countdown.md` |
| 同着 | 行軍秒数の異なる部隊を同時に到着させること | `sync-start-tables.md`、`sync-start-countdown.md` |
| 役割 | 集結作戦での「メイン」「増援」「削り」 | `siege-timeline.md` |
| パターン | 一度に着弾させる削りと増援の組み合わせ | `siege-timeline.md` |
| 発起／着弾／帰還 | 集結の開始、目標への到着、部隊の戻り | `siege-timeline.md` |
| 周期 | 集結タイムライン計算で、1周目を繰り返すときの、ある周から次の周までの秒数。先頭のパターンの2周目と1周目の着弾の差とする。周期ウェーブタイマーでは予定を追加する間隔で、集結タイムライン計算の周期を自動で受け取るか、手で入力する | `siege-timeline.md`、`wave-timer.md` |
| 占領時間 | 同盟が累計で占領した秒数 | `occupation-judge.md` |
| 確定まで | 勝利が確定するまでに追加で必要な占領時間 | `occupation-judge.md` |

「集結」は両方のコンテキストに現れますが、「KvKチーム編成」の隊のリーダーと、
「戦闘タイミング」の集結作戦の役割は別の概念です。モデルを共有しません。

## 戦術的モデル

### エンティティ

- `Member`: 現在は正規化した名前を識別子として扱う。将来名前変更や同名参加者が必要に
  なった時点で`MemberId`値オブジェクトを導入する

### 値オブジェクトとドメインポリシー

- `Tier`, `Availability`, `TimeSlot`, `MemberRef`
- `EventTimeSettings`
- 利用者が決めた固定値: `TOP_TEAM_COUNT`, `TOP_TEAM_SIZE`, `SORTIE_FLOOR`, `EXTENSION_BOUNDARY_MINUTES`,
  `SLOT_MINUTES`（`domain/team.py`。ADR 0034）
- 現行の規則: 戦力関係`STRICTLY_STRONGER_PAIRS`, `AT_LEAST_AS_STRONG_PAIRS`（`domain/team.py`）。固定値ではなく、
  分割案の3でFRM-027へ置き換えるまで維持する
- `TeamMaster`, `KvKRules`, `OperatorSpecification`: 1イベントの編成ポリシーと運用者の指定を構成する不変値

### 集約と結果型

`TeamPlan`は隊ごとの所属、待機、別枠をまとめて扱う編成候補です。Optimizerが候補を作り、
独立Validatorが参加者一覧と運用者の指定から計算し直して検証します。必須条件を満たした候補だけが、
検証結果と一緒に`ValidatedTeamPlan`になります。Exporterは`ValidatedTeamPlan`だけを受け取るため、
未検証の候補を誤って出力できません。

Optimizerの結果は`SolvedPlan`（編成と最適性）と`ProvenInfeasible`（理由）で、アプリケーションの
境界（`application/ports.py`）に置きます。時間切れは結果にせず例外として送出します（ADR 0019）。

`TeamMaster`と`OperatorSpecification`は一貫して読み込む値の集合です。各`Member`や隊へ形式的な
Repositoryを作らず、永続化の整合単位が明確なものにだけRepository境界を置きます。

### ドメインサービス

- 参加可能時間の解決と時間枠への分割
- リーダー一覧の参加者への解決（`resolve_leaders`）
- 所属と参加時間からの出撃の計算（`sorties`）
- 編成の必須条件検証と警告生成
- ソルバーへ渡す編成ポリシーの表現

CP-SATの変数や係数操作はOR-Toolsアダプターの責務です。必須条件、警告、目的関数の意味は
ドメインに残し、ソルバー固有表現をドメインモデルへ漏らしません。

## レイヤー責務

### ドメイン

外部I/Oを行わず、Python標準の値とCollectionで業務概念を表します。ドメインのテストは
Markdown、JSON、ファイルパス、OR-Toolsを必要としない形を目標とします。

### アプリケーション

ユースケース`BuildTeamPlan`はドメイン型の`Member`一覧と`OperatorSpecification`を受け取り、
Optimizer境界とValidator境界を調整して`ValidatedTeamPlan`を返します。リーダーの解決の失敗
（`SpecificationError`）、解なしの証明（`NoValidPlanError`）、下限の不足（`LowerBoundShortfallError`、
最適性を示せなければ`ShortfallUndeterminedError`）、再試行の上限（`BuildError`）を区別しますが、
Markdownの解析・出力や、編成人数、VC条件そのものは決めません。チームマスタと運用者の指定は、
呼び出し側がRepositoryから読み込んで渡します。

入力の解析と出力はインターフェース層が組み立てます。CLIでは`interfaces/cli/team_builder.py`の
`TeamBuilder`が、Markdown Parser、`BuildTeamPlan`、Markdown Exporterをこの順に呼び出します。
Web Interface（#21）は、同じ`BuildTeamPlan`を別の入出力で呼び出します。

### アダプターとインフラストラクチャ

- 入力側: CLI、将来のWeb UI、Markdown参加者Parser
- 出力・接続側: JSONチームマスタRepository、運用者の指定（`settings.json`）Repository、OR-Tools CP-SAT Optimizer
- 表示側: Markdown Exporter、将来のWeb View Model Mapper

アダプターは外部データをドメイン型へ変換し、外部形式固有の辞書、正規表現、ファイルパス、
ソルバー型を内側へ渡しません。

## パッケージ構造

```text
src/kvk_team/
  team_building/
    domain/
      member.py           参加者、Tier、参加可能時間
      team.py             隊の番号、固定値（上位隊、出撃人数の下限、延長境界時刻、30分単位）、現行の戦力関係
      specification.py    運用者の指定、リーダーの解決
      plan.py             時間枠、所属固定の編成候補、出撃の計算
      team_master.py      チームマスタ（戦闘時間、上限）
      rules.py            編成ルール（チームマスタを必須で受け取る）
      availability.py     参加可能時間の解決
      validation.py       必須条件の独立検証、警告、ValidatedTeamPlan
    application/
      ports.py            Optimizer、Validator、Repositoryの境界、Optimizerの結果の型
      build_team_plan.py  最適化、検証、再試行を調整し、ValidatedTeamPlanを返すユースケース
    adapters/
      input/markdown_member_parser.py
      output/team_plan_markdown_exporter.py
      persistence/json_team_master_repository.py、team_master.json、
                  json_operator_settings_repository.py、settings.example.json
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

# ADR 0021: モノリポジトリの構成と2つの境界づけられたコンテキスト

- 状態: 提案中（一部をADR 0026で置き換え）
- 日付: 2026-10-17
- 置き換え: ADR 0003の「判断」のうち、唯一のコンテキストとする点と、`domain-model.md`の目標パッケージ構造。
  ADR 0013のうち、HTMLの計算をPythonへ移植しないとする点と、CIへNode.jsを追加しないとする点
- 注記: 本書の名前空間とパッケージのパスはADR 0026で改名した後の名前に、ツールの表示名は伏せる語を
  除いた表記に書き換えた。ADR 0003の目標パッケージと却下した代替案の名前（`kvk_team_builder`）も、
  伏せる語を除いた表記である。名前空間を`kvk_team`と決めたのはADR 0026である。当時の表記は旧Repositoryの
  履歴にある

## 背景

ADR 0003は「KvKチーム編成」を唯一の境界づけられたコンテキストとし、目標パッケージを
`src/kvk_team_builder/`とした。ADR 0013は`web/`の単体HTMLツールをPythonの処理対象外とし、
計算をPythonへ移植しないと決めた。

その後、Webアプリ化の計画（#1、#9）で、行軍と到着カウントダウン（#6）、占領判定（#7）、
集結タイムライン（#29）、周期ウェーブタイマー（#30）の計算をPythonのBEへ移し、React、TypeScript、Viteの
FEとDjango NinjaのAPIで提供することになった（#21）。これらは秒単位の時間計算であり、参加者を時間帯
ごとにチームへ割り当てる編成とは、用語も規則も異なる。また、FEとBEを同じRepositoryへ置く場所と、
Node.jsを品質ゲートへ加える方法が決まっていない。モノリポジトリの運用は維持する。

## 判断

### コンテキスト

境界づけられたコンテキストを次の2つとする。

| コンテキスト | パッケージ | 責務 |
|---|---|---|
| KvKチーム編成 | `team_building` | 参加可能な参加者を時間帯ごとにチームへ割り当て、必須条件と警告を扱う |
| 戦闘タイミング | `battle_timing` | 行軍秒数、到着の同期、集結タイムライン、周期、占領時間の判定を秒単位で扱う |

- コンテキストどうしは互いをimportしない。同じ語（例: 集結）を両方で使う場合も、モデルを共有せず
  各コンテキストで定義する。共有カーネルは設けない
- 両方を組み合わせる必要が生じた場合は、インターフェース層で各コンテキストのユースケースを呼び、
  ドメインどうしを直接つながない

### 名前空間とパッケージ構成

Pythonは1つの配布物のまま、名前空間を`kvk_team`とし、コンテキストをサブパッケージで分ける。
各コンテキストはADR 0003のレイヤー（`domain`、`application`、`adapters`）を持つ。

```text
/
├─ pyproject.toml                  # Pythonの配布物は1つ
├─ package.json                    # npm workspacesのルート
├─ package-lock.json
├─ src/kvk_team/
│   ├─ team_building/
│   │   ├─ domain/
│   │   ├─ application/
│   │   └─ adapters/               # Markdown、JSON、OR-Tools、永続化
│   ├─ battle_timing/
│   │   ├─ domain/
│   │   ├─ application/
│   │   └─ adapters/
│   └─ interfaces/
│       ├─ cli/                    # 編成CLI
│       └─ web/                    # Djangoプロジェクト、Django NinjaのAPI
├─ frontend/                       # React、TypeScript、Vite
│   └─ src/api/                    # OpenAPIの定義と生成した型（コミットする）
├─ web/                            # 既存の単体HTMLツール。置き換えが済んだものから削除する
├─ tests/
│   ├─ team_building/
│   ├─ battle_timing/
│   └─ interfaces/                 # RepositoryやHarnessの構造テストは従来どおり直下に置く
├─ docs/
│   ├─ requirements/               # 要件定義書（web-tools/は#32で各コンテキストへ移す）
│   ├─ adr/
│   ├─ architecture.md
│   └─ domain-model.md
└─ tools/                          # 品質ゲートなど、PythonとFEに共通の実行Script
```

- 配布名とCLI名は、公開CLIを壊さないため当面維持するとした（ADR 0026で改名し、この点を置き換えた）
- 依存方向は`interfaces -> application -> domain`、`adapters -> application / domain`とする。
  `domain`はDjango、Django Ninja、JSON、Markdown、OR-Tools、`pathlib`をimportしない

### Webのインターフェース

- Djangoプロジェクト（設定、URL、Django NinjaのRouter、FEの配信）は`interfaces/web/`に置く。
  起動Scriptの位置や設定の詳細は#21で決める
- Djangoの永続化モデルを使う場合は、そのコンテキストの`adapters/`に置き、`domain`と`application`
  から参照しない。永続化の方式とデータの境界は#2で決める
- APIはコンテキストのユースケースを呼び出すだけとし、編成ルールや時間計算の規則を持たない

### FEとNode.js

- FEは`frontend/`に置き、パッケージマネージャーはnpmとする。ルートの`package.json`でnpm workspaces
  を構成し、`package-lock.json`をコミットする
- Django NinjaのOpenAPI定義と、`openapi-typescript`で生成した型を`frontend/src/api/`へコミットする。
  品質ゲートは再生成して差分がないことを確かめる
- Node.jsのバージョンを固定し、CI（Windows、Linux）とDev Containerへ加える。`tools/check.py`から
  FEのLint、型検査、テストも実行し、品質ゲートの入口を1つに保つ
- FEにはドメインルールを複製せず、表示、入力、毎フレームのタイマー描画だけを持たせる

### 既存の`web/`

- `web/`の単体HTMLツールは、新しいアプリで同じ要件を満たしたツールから順に置き換え、その後に
  削除する（#32）。置き換えが済むまでは、Pythonの品質ゲートの対象外とするADR 0013の扱いを維持する
- `web/`の計算をPythonへ移すときは、`docs/requirements/web-tools/`の要件IDをテストの期待値にする

## 代替案

### コンテキストごとに配布物を分ける（`packages/*`、uv workspace）

コンテキストの独立性は高まるが、依存とバージョンの管理、品質ゲート、CIの構成が複数になる。
別々にデプロイする要件はなく、Render Freeの1 Serviceで運用する方針（#21）とも合わないため採用しない。

### 名前空間を`kvk_team_builder`のままにする

ADR 0003の目標と配布名に一致するが、戦闘タイミングも「team_builder」の下に置くことになり、
コンテキストの境界を名前が誤って伝えるため採用しない。

### 戦闘タイミングを編成コンテキストの一部にする

構成は単純だが、行軍秒数や周期などの用語と規則が編成のモデルへ混ざる。#6と#7で入出力も
独立しているため採用しない。

### FEとBEのRepositoryを分ける

独立してリリースできるが、APIの型と生成物の同期が難しくなる。モノリポジトリを維持する方針の
ため採用しない。

## 影響

- #28で既存の編成処理を`kvk_team.team_building`へ移し、依存方向の自動検査を品質ゲートへ
  加える。それまでは現行の技術レイヤー別パッケージと目標構造が併存する
- #29、#30、#6、#7の計算は`kvk_team.battle_timing`へ実装する
- #21でNode.jsが開発環境、CI、品質ゲートに加わり、WindowsとLinuxの両方で動くことを確かめる必要がある
- `docs/domain-model.md`と`docs/architecture.md`は2つのコンテキストを前提に書き直す

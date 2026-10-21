---
name: change-kvk-rules
description: KvKの編成ルール変更を、利用者向け契約、CP-SATモデル、独立Validator、Exporter、設定、テスト、ADRで一貫させながら実装または計画する。人数、VC、集結主、時間枠、戦力順、警告、目的関数、待機、参加者入力の変更時に使用する。
---

# KvKルールを変更する

利用者向け契約から独立検証まで、ルール変更を明示的に追跡する。Optimizerが結果を返した
ことだけを、ルールが正しい根拠にしない。

## 最初にルールを分類する

`AGENTS.md`、`docs/domain-model.md`、`README.md`と`docs/architecture.md`の関連箇所、
対象テスト、`src/kvk_team/team_building/adapters/persistence/team_master.json`を読む。依頼された動作を、次の主分類から1つ
選んで分類する。利用者から受け取ったルール文書や決定事項など、Repositoryにない出典は、受け取った
時点でGit管理外の`tmp/review-sources/`へ保存する（ADR 0024）。

- 必須条件: 違反時は出力しない
- 警告: 最善の編成を出力し、不足を運用者へ知らせる
- 目的関数: 複数の有効な編成から望ましいものを選ぶ
- 入力正規化: 参加者テキストをドメイン値へ変換するか、曖昧な入力を拒否する
- 表示のみ: 編成の有効性を変えずに出力を変更する

依頼が現在の正本と衝突する場合や複数分類をまたぐ場合は、編集前に利用者へ確認する。

`docs/domain-model.md`のユビキタス言語を使用する。ファイルを選ぶ前に、変更がドメイン、
アプリケーション、アダプターのどこに属するか決める。ドメインの意味をMarkdown、JSON、CLI、
OR-Tools固有の表現から独立させる。

## 変更先を選ぶ

- 入力記法または時刻抽出: `src/kvk_team/team_building/adapters/input/`とParserテスト
- 参加可能時間または半開区間: `src/kvk_team/team_building/domain/availability.py`と参加時間テスト
- 必須の編成制約または目的関数: `src/kvk_team/team_building/adapters/optimization/cp_sat_team_optimizer.py`
- 運用値: `src/kvk_team/team_building/adapters/persistence/team_master.json`とRepository／Model検証
- 独立した有効性と警告: `src/kvk_team/team_building/domain/validation.py`
- Markdown表現: `src/kvk_team/team_building/adapters/output/dynamic_markdown_exporter.py`
- 再試行とエラー伝播: `src/kvk_team/team_building/application/build_team_plan.py`とCLI境界

CLIや将来のUIへルールを複製しない。目標とするアプリケーションのユースケースの外側に
Markdown解析と表示を置く。チームマスタに属する運用値をPythonへ直書きしない。この
リポジトリは`docs/domain-model.md`の目標パッケージ構造へ移行中であるため、ルール変更へ
無関係なパッケージ移動を混在させない。

## 契約を先に実装する

1. 依頼された契約と最も近い境界値を示すテストを追加または更新する。
2. 必須条件では、Optimizerによる強制と、独立して作った不正PlanをValidatorが拒否する
   ことの両方をテストする。
3. 警告では、出力が成功し、対象時刻と不足内容を含むことを示す。
4. 目的関数では、任意の完全配置1つに依存せず、小さく決定的な比較をテストする。
5. Parserでは、必要に応じて許可記法、曖昧な入力、Unicode表記、時刻境界をテストする。
6. ドメインとアプリケーションへ依存が向くように、最小限の変更を実装する。
7. 利用者向け動作は`README.md`、制約または処理フローは`docs/architecture.md`へ反映する。
   ルール分類またはアーキテクチャ境界を変える場合はADRを追加する。

## 検証する

変更中は対象テストを実行し、完了前に次を実行する。

```text
python tools/check.py
```

編成または表示を変更した場合は、実際の生成結果も確認する。変更前に一度、変更後にもう一度
次を実行し、自己チェック、警告詳細、前回との差分が意図どおりかを読む。

```text
python tools/preview_output.py
```

出力は`tmp/preview/`へ書かれ、直前の出力は`*.previous.md`へ退避される。CP-SATは制限時間内の
探索結果を返すため、ルールと無関係な差分が出た場合は、差分だけを根拠に不具合と断定しない。
`--input`で運用者から受け取った参加者一覧も確認できるが、その入力と出力は`AGENTS.md`の伏せる語の規則
（ADR 0026）に従って扱う。

選んだルール分類、更新したファイル、品質ゲートの結果、生成結果の確認内容、警告または
必須エラーが残る条件を報告する。

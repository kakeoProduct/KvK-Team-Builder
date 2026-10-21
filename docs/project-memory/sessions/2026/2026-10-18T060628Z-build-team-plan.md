---
type: session
id: 2026-10-18T060628Z-build-team-plan
title: BuildTeamPlanとValidatedTeamPlanを導入（#28後半）
status: current
created_at: '2026-10-18T06:06:28Z'
base_commit: e156412989c2e207443aafffcbf97d9e5f29b17b
final_commit: e156412989c2e207443aafffcbf97d9e5f29b17b
tags:
- architecture
- ddd
- refactoring
related_paths:
- .agents/skills/change-kvk-rules/SKILL.md
- .claude/skills/change-kvk-rules/SKILL.md
- docs/architecture.md
- docs/domain-model.md
- src/kvk_team/interfaces/cli/composition.py
- src/kvk_team/interfaces/cli/main.py
- src/kvk_team/interfaces/cli/team_builder.py
- src/kvk_team/team_building/adapters/output/dynamic_markdown_exporter.py
- src/kvk_team/team_building/application/build_team_plan.py
- src/kvk_team/team_building/application/ports.py
- src/kvk_team/team_building/application/team_builder.py
- src/kvk_team/team_building/domain/validation.py
- tests/deterministic_solver.py
- tests/test_cli_composition.py
- tests/test_dependency_direction.py
- tests/test_dynamic_validator_exporter.py
- tests/test_preview_output.py
- tests/test_service.py
- tests/test_time_slot_optimizer.py
- tools/preview_output.py
---

# BuildTeamPlanとValidatedTeamPlanを導入（#28後半）

## 利用者の依頼

Issue #28後半: BuildTeamPlanとValidatedTeamPlanを導入する

## 実装結果

ValidatedTeamPlan(plan, report)をドメインへ追加し必須条件エラーを拒否。BuildTeamPlanがMember一覧からValidatedTeamPlanを返し再試行とBuildErrorを担う。Markdownの解析と出力の組み立てをinterfaces/cli/team_builder.pyへ移し、Exporterはexport(validated)のみ。default_rules()は引数なしにしてreplaceで上書き。レビュー指摘S1、S2、N1、N2、N5、N6に対応し、ADR 0003の段階1と4を完了

## 重要な判断

- 利用者が選択: ValidatedTeamPlanは編成と検証結果を包む、TeamBuilderはインターフェース層へ移す
- default_rulesのキーワード引数を列挙するとKvKRulesの既定値を二重に持つため、型を検査できるdataclasses.replaceにした
- ValidatedTeamPlanは検証結果が同じ編成のものかまでは保証しないため、BuildTeamPlanから生成する前提を文書化した（型での保証は見送り）

## 検証

- python tools/check.py: 成功（115 passed）
- 決定的設定のsample出力: 移行前とバイト一致
- 追加テストは誤った変更（警告の拒否、BuildErrorの捕捉漏れ）で失敗することを確認

## 未完了事項

- #21: BuildTeamPlanの組み立てをCLIの外へ切り出し、ValidatorとExporterの編成ルールを共通化（レビューN3、N4）
- CLI既定設定（8並列、30秒）では警告件数が実行ごとに22〜48件と変動する。別途検討

## 正本への参照

- `.agents/skills/change-kvk-rules/SKILL.md`
- `.claude/skills/change-kvk-rules/SKILL.md`
- `docs/architecture.md`
- `docs/domain-model.md`
- `src/kvk_team/interfaces/cli/composition.py`
- `src/kvk_team/interfaces/cli/main.py`
- `src/kvk_team/interfaces/cli/team_builder.py`
- `src/kvk_team/team_building/adapters/output/dynamic_markdown_exporter.py`
- `src/kvk_team/team_building/application/build_team_plan.py`
- `src/kvk_team/team_building/application/ports.py`
- `src/kvk_team/team_building/application/team_builder.py`
- `src/kvk_team/team_building/domain/validation.py`
- `tests/deterministic_solver.py`
- `tests/test_cli_composition.py`
- `tests/test_dependency_direction.py`
- `tests/test_dynamic_validator_exporter.py`
- `tests/test_preview_output.py`
- `tests/test_service.py`
- `tests/test_time_slot_optimizer.py`
- `tools/preview_output.py`

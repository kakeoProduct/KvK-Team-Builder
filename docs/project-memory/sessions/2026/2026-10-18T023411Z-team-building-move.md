---
type: session
id: 2026-10-18T023411Z-team-building-move
title: 編成処理をkvk_team.team_buildingへ移行（#28 PR1）
status: current
created_at: '2026-10-18T02:34:11Z'
base_commit: c37ac3f42a103d722f2a21ac6e5ab09a73cd3471
final_commit: c37ac3f42a103d722f2a21ac6e5ab09a73cd3471
tags:
- architecture
- ddd
- refactoring
related_paths:
- .agents/skills/change-kvk-rules/SKILL.md
- .agents/skills/review-kvk-change/SKILL.md
- .claude/skills/change-kvk-rules/SKILL.md
- .claude/skills/review-kvk-change/SKILL.md
- .github/ISSUE_TEMPLATE/bug_report.yml
- AGENTS.md
- README.md
- docs/architecture.md
- docs/domain-model.md
- pyproject.toml
- src/cli/__init__.py
- src/cli/service.py
- src/config/__init__.py
- src/exporter/__init__.py
- src/kvk_team/__init__.py
- src/kvk_team/interfaces/__init__.py
- src/kvk_team/interfaces/cli/__init__.py
- src/kvk_team/interfaces/cli/__main__.py
- src/kvk_team/interfaces/cli/composition.py
- src/kvk_team/interfaces/cli/main.py
- src/kvk_team/team_building/__init__.py
- src/kvk_team/team_building/adapters/__init__.py
- src/kvk_team/team_building/adapters/input/__init__.py
- src/kvk_team/team_building/adapters/input/markdown_member_parser.py
- src/kvk_team/team_building/adapters/optimization/__init__.py
- src/kvk_team/team_building/adapters/optimization/cp_sat_team_optimizer.py
- src/kvk_team/team_building/adapters/optimization/errors.py
- src/kvk_team/team_building/adapters/output/__init__.py
- src/kvk_team/team_building/adapters/output/dynamic_markdown_exporter.py
- src/kvk_team/team_building/adapters/persistence/__init__.py
- src/kvk_team/team_building/adapters/persistence/json_team_master_repository.py
- src/kvk_team/team_building/adapters/persistence/team_master.json
- src/kvk_team/team_building/application/__init__.py
- src/kvk_team/team_building/application/ports.py
- src/kvk_team/team_building/application/team_builder.py
- src/kvk_team/team_building/domain/__init__.py
- src/kvk_team/team_building/domain/availability.py
- src/kvk_team/team_building/domain/member.py
- src/kvk_team/team_building/domain/rules.py
- src/kvk_team/team_building/domain/schedule.py
- src/kvk_team/team_building/domain/team.py
- src/kvk_team/team_building/domain/team_master.py
- src/kvk_team/team_building/domain/validation.py
- src/models/__init__.py
- src/optimizer/__init__.py
- src/parser/__init__.py
- src/validator/__init__.py
- tests/deterministic_solver.py
- tests/test_cli.py
- tests/test_cli_composition.py
- tests/test_dependency_direction.py
- tests/test_dynamic_validator_exporter.py
- tests/test_integration.py
- tests/test_member_times.py
- tests/test_models.py
- tests/test_parser.py
- tests/test_preview_output.py
- tests/test_service.py
- tests/test_team_master_repository.py
- tests/test_time_slot_optimizer.py
- tests/test_tool_output_encoding.py
- tools/preview_output.py
---

# 編成処理をkvk_team.team_buildingへ移行（#28 PR1）

## 利用者の依頼

Issue #28: 既存の編成処理をteam_buildingコンテキストへ移す（PR1: 移動と依存方向の検査）

## 実装結果

旧トップレベルパッケージを削除し、domain、application、adapters、interfaces/cliへ移動。KvKRulesのteam_masterを必須化してDEFAULT_RULESを廃止し、JSON読み込みと既定部品の組み立てをinterfaces/cli/composition.pyへ移した。依存方向の構造テスト、CLIの起動経路・package-data・組み立てのテストを追加し、レビュー指摘S1〜S4とN1、N2、N4、N5に対応

## 重要な判断

- 利用者が選択: PRは2分割（BuildTeamPlanとValidatedTeamPlanはPR2）、CLIはpython -m（ADR 0026で改名後の表記はkvk_team）.interfaces.cliへ切替、team_master.jsonはadapters/persistence/へ
- CLIの出力は8並列・時間制限で非決定的なため、1 worker・決定的時間5.0の設定で移行前後の出力を比較した
- 旧ディレクトリに残る__pycache__だけは削除済みとみなす構造テストにした（各自の環境での誤検知を防ぐ）
- ツールをサブプロセスで起動するテストへPYTHONPATH=srcを渡した。共有のeditable installが別のworktreeを向くと、検査対象のコードが入れ替わって失敗したため

## 検証

- python tools/check.py: 成功（104 passed）
- 決定的設定のsample出力: 移行前後でバイト一致（491行）
- CLI名と`python -m`による実行（ADR 0026で改名後の表記はkvk-team-builderとkvk_team）: 終了コード0、必須条件OK

## 未完了事項

- PR2: BuildTeamPlanとValidatedTeamPlanの導入、default_rulesの型付き引数化（レビューN3）
- 共有のeditable installは元の作業ツリーへ戻した（2026-10-18）

## 正本への参照

- `.agents/skills/change-kvk-rules/SKILL.md`
- `.agents/skills/review-kvk-change/SKILL.md`
- `.claude/skills/change-kvk-rules/SKILL.md`
- `.claude/skills/review-kvk-change/SKILL.md`
- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `AGENTS.md`
- `README.md`
- `docs/architecture.md`
- `docs/domain-model.md`
- `pyproject.toml`
- `src/cli/__init__.py`
- `src/cli/service.py`
- `src/config/__init__.py`
- `src/exporter/__init__.py`
- `src/kvk_team/__init__.py`
- `src/kvk_team/interfaces/__init__.py`
- `src/kvk_team/interfaces/cli/__init__.py`
- `src/kvk_team/interfaces/cli/__main__.py`
- `src/kvk_team/interfaces/cli/composition.py`
- `src/kvk_team/interfaces/cli/main.py`
- `src/kvk_team/team_building/__init__.py`
- `src/kvk_team/team_building/adapters/__init__.py`
- `src/kvk_team/team_building/adapters/input/__init__.py`
- `src/kvk_team/team_building/adapters/input/markdown_member_parser.py`
- `src/kvk_team/team_building/adapters/optimization/__init__.py`
- `src/kvk_team/team_building/adapters/optimization/cp_sat_team_optimizer.py`
- `src/kvk_team/team_building/adapters/optimization/errors.py`
- `src/kvk_team/team_building/adapters/output/__init__.py`
- `src/kvk_team/team_building/adapters/output/dynamic_markdown_exporter.py`
- `src/kvk_team/team_building/adapters/persistence/__init__.py`
- `src/kvk_team/team_building/adapters/persistence/json_team_master_repository.py`
- `src/kvk_team/team_building/adapters/persistence/team_master.json`
- `src/kvk_team/team_building/application/__init__.py`
- `src/kvk_team/team_building/application/ports.py`
- `src/kvk_team/team_building/application/team_builder.py`
- `src/kvk_team/team_building/domain/__init__.py`
- `src/kvk_team/team_building/domain/availability.py`
- `src/kvk_team/team_building/domain/member.py`
- `src/kvk_team/team_building/domain/rules.py`
- `src/kvk_team/team_building/domain/schedule.py`
- `src/kvk_team/team_building/domain/team.py`
- `src/kvk_team/team_building/domain/team_master.py`
- `src/kvk_team/team_building/domain/validation.py`
- `src/models/__init__.py`
- `src/optimizer/__init__.py`
- `src/parser/__init__.py`
- `src/validator/__init__.py`
- `tests/deterministic_solver.py`
- `tests/test_cli.py`
- `tests/test_cli_composition.py`
- `tests/test_dependency_direction.py`
- `tests/test_dynamic_validator_exporter.py`
- `tests/test_integration.py`
- `tests/test_member_times.py`
- `tests/test_models.py`
- `tests/test_parser.py`
- `tests/test_preview_output.py`
- `tests/test_service.py`
- `tests/test_team_master_repository.py`
- `tests/test_time_slot_optimizer.py`
- `tests/test_tool_output_encoding.py`
- `tools/preview_output.py`

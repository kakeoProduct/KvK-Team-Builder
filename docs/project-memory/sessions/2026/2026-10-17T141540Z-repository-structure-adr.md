---
type: session
id: 2026-10-17T141540Z-repository-structure-adr
title: モノリポジトリの構成と2つのコンテキストをADR 0021で決定
status: current
created_at: '2026-10-17T14:15:40Z'
base_commit: 7d2e91216f93883e86b27ad57bc41850376c5735
final_commit: 7d2e91216f93883e86b27ad57bc41850376c5735
tags:
- architecture
- ddd
related_paths:
- AGENTS.md
- README.md
- docs/adr/0013-separate-web-tools-from-python-scope.md
- docs/adr/0021-repository-structure-and-contexts.md
- docs/adr/README.md
- docs/architecture.md
- docs/domain-model.md
- tests/test_repository_scope.py
---

# モノリポジトリの構成と2つのコンテキストをADR 0021で決定

## 利用者の依頼

Issue #27: リポジトリ構成とコンテキスト分割をADRで決める

## 実装結果

ADR 0021を追加し、名前空間（ADR 0026で改名後の表記はkvk_team）、コンテキストteam_buildingとbattle_timing、interfaces/{cli,web}、frontend/とnpm、生成型のコミットを決定。domain-model、architecture、AGENTS、README、ADR 0013の状態を更新し、構造テストを追加。コードは移動していない

## 重要な判断

- 名前は利用者が選択: 名前空間（ADR 0026で改名後の表記はkvk_team）、編成側team_building、当日計算側battle_timing（戦闘タイミング）
- ADR 0003は採用済みのため本文を変えず、ADR 0021から置き換え範囲を参照した。提案中のADR 0013は状態欄に一部置き換えを記録した
- Djangoの起動や永続化の詳細は#21と#2へ委ね、ADRでは配置と依存方向だけを決めた

## 検証

- python tools/check.py: 成功（91 passed）

## 未完了事項

- コミットとPR作成は未実施（利用者の指示待ち）

## 正本への参照

- `AGENTS.md`
- `README.md`
- `docs/adr/0013-separate-web-tools-from-python-scope.md`
- `docs/adr/0021-repository-structure-and-contexts.md`
- `docs/adr/README.md`
- `docs/architecture.md`
- `docs/domain-model.md`
- `tests/test_repository_scope.py`

"""動的ValidatorとMarkdown Exporterの統合テスト。"""

import pytest

from deterministic_solver import deterministic_rules
from kvk_team.interfaces.cli.composition import default_rules
from kvk_team.team_building.adapters.optimization.cp_sat_team_optimizer import (
    TimeSlotTeamOptimizer,
)
from kvk_team.team_building.adapters.output.dynamic_markdown_exporter import (
    DynamicMarkdownExporter,
)
from kvk_team.team_building.domain.member import Member, Tier
from kvk_team.team_building.domain.schedule import SlotAssignment, TimeSlot
from kvk_team.team_building.domain.team import TeamLabel
from kvk_team.team_building.domain.validation import (
    DynamicTeamValidator,
    DynamicValidationCode,
    DynamicValidationIssue,
    DynamicValidationReport,
    ValidatedTeamPlan,
)


def make_roster() -> list[Member]:
    """全時間帯の必須条件を満たす88名を生成する。"""

    rules = default_rules()
    leaders = list(rules.rally_leaders.values())
    members = [
        Member(
            name=name,
            alliance="未設定",
            tier=Tier.G8 if index < 3 else Tier.G5,
            has_vc=True,
        )
        for index, name in enumerate(leaders)
    ]
    tiers = (Tier.G8, Tier.G7, Tier.G6, Tier.G5)
    members.extend(
        Member(
            name=f"検証参加者{index:03d}",
            alliance="未設定",
            tier=tiers[index % len(tiers)],
            has_vc=True,
        )
        for index in range(88 - len(members))
    )
    return members


@pytest.fixture(scope="module")
def validated_output() -> tuple[str, DynamicValidationReport]:
    """動的編成を1回生成し、検証してMarkdownへ出力する。"""

    rules = deterministic_rules()
    members = make_roster()
    plan = TimeSlotTeamOptimizer(rules).optimize(members)
    report = DynamicTeamValidator(rules).validate(plan, members)
    markdown = DynamicMarkdownExporter(rules).export(
        ValidatedTeamPlan(plan=plan, report=report)
    )
    return markdown, report


def test_validator_accepts_complete_dynamic_plan(validated_output) -> None:
    """Optimizerの全時間帯配置を独立Validatorが受理する。"""

    _, report = validated_output

    assert report.is_valid
    assert not report.issues
    assert len(report.slot_metrics) == 88


def test_exporter_renders_initial_teams_metrics_and_self_check(
    validated_output,
) -> None:
    """初期配置、時間帯集計、自己チェックを運用文書へ含める。"""

    markdown, _ = validated_output

    assert "## A（役割A）（最大8）" in markdown
    assert "### 21:00 初期配置" in markdown
    assert "## 時間帯別チーム集計" in markdown
    assert "- 必須条件: OK" in markdown


def test_exporter_adds_time_to_validation_details() -> None:
    """検証詳細から問題が発生した時間帯を特定できる。"""

    issue = DynamicValidationIssue(
        code=DynamicValidationCode.UNDERFILLED,
        message="Kが8人未満です: 7人",
        time_slot=TimeSlot(start_minutes=23 * 60 + 30, end_minutes=24 * 60),
    )

    assert DynamicMarkdownExporter._issue_text(issue) == ("23:30: Kが8人未満です: 7人")


def test_exporter_uses_assignment_start_time_for_initial_header() -> None:
    """初期配置時刻をJSONマスタ由来のスロットへ追従させる。"""

    rules = default_rules()
    member = Member("山田", "未設定", Tier.G8, has_vc=True)
    assignment = SlotAssignment(
        team_label=TeamLabel.A,
        time_slot=TimeSlot(start_minutes=20 * 60, end_minutes=20 * 60 + 30),
        members=(member,),
    )
    definition = rules.team_master.teams_by_label[TeamLabel.A]

    markdown = DynamicMarkdownExporter(rules)._render_team(
        (assignment,),
        definition,
    )

    assert "### 20:00 初期配置" in markdown

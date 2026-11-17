"""所属固定の編成のMarkdown Exporterのテスト。"""

from kvk_team.interfaces.cli.composition import default_rules
from kvk_team.team_building.adapters.output.team_plan_markdown_exporter import (
    TeamPlanMarkdownExporter,
)
from kvk_team.team_building.domain.member import Member, Tier
from kvk_team.team_building.domain.plan import (
    Support,
    TeamMembership,
    TeamPlan,
    TimeSlot,
)
from kvk_team.team_building.domain.validation import (
    SortieMetrics,
    ValidatedTeamPlan,
    ValidationCode,
    ValidationIssue,
    ValidationReport,
)

LEADER = Member("山田", "SKY", Tier.G8, has_vc=True)
EARLY_LEAVER = Member("いろは", "SKY", Tier.G7, has_vc=False, end_time_minutes=23 * 60)
LATE_JOINER = Member(
    "さくら",
    "FOX",
    Tier.G6,
    has_vc=True,
    starts_at_21=False,
    start_time_minutes=22 * 60 + 30,
)
UNDECIDED_LEADER = Member("taro", "SUN", Tier.G8, has_vc=True, starts_at_21=False)
WAITING = Member("わんこ", "SKY", Tier.G5)
SLOT = TimeSlot(23 * 60 + 30, 24 * 60)


def _export() -> str:
    plan = TeamPlan(
        teams=(
            TeamMembership(1, LEADER, (LEADER, EARLY_LEAVER, LATE_JOINER)),
            TeamMembership(2, UNDECIDED_LEADER, ()),
        ),
        waiting=(WAITING,),
        undecided=(UNDECIDED_LEADER,),
    )
    report = ValidationReport(
        issues=(),
        warnings=(
            ValidationIssue(
                ValidationCode.UNDERFILLED, "第4隊が8人未満です: 7人", 4, SLOT
            ),
            ValidationIssue(ValidationCode.LEADER_ABSENT, "第2隊はリーダー不在です", 2),
        ),
        sortie_metrics=(
            SortieMetrics(4, SLOT, 0, 0, 0, None),
            SortieMetrics(2, SLOT, 3, 600, 3, None),
            SortieMetrics(1, SLOT, 2, 700, 1, "山田"),
        ),
        waiting=plan.waiting,
        undecided=plan.undecided,
    )
    return TeamPlanMarkdownExporter(default_rules()).export(
        ValidatedTeamPlan(plan=plan, report=report, proven_optimal=True)
    )


def test_exporter_renders_team_heading_with_leader_or_absence() -> None:
    """隊の見出しにリーダーを書き、別枠のリーダーの隊は「リーダー不在」とする（OUT-001）。"""

    markdown = _export()

    assert "## 第1隊 リーダー: 山田\n\n所属: 3人\n" in markdown
    assert "## 第2隊 リーダー不在\n\n所属: 0人\n" in markdown


def test_exporter_writes_vc_and_participation_time_only_when_partial() -> None:
    """VC可能に◇を付け、全時間参加でないメンバーにだけ参加時間を書く（OUT-002）。"""

    markdown = _export()

    assert "- 山田◇\n" in markdown
    assert "- いろは（21:00〜23:00）\n" in markdown
    assert "- さくら◇（22:30〜25:00）\n" in markdown


def test_exporter_renders_waiting_and_undecided_with_leader_note() -> None:
    """待機と別枠の人数と名前を示し、別枠のリーダーには隊を添える（FRM-033、FRM-060、OUT-009）。"""

    markdown = _export()

    assert "## 待機 1人\n\n- わんこ\n" in markdown
    assert "## 【別枠】参加時間未定 1人\n\n- taro（第2隊のリーダー）\n" in markdown


def test_exporter_renders_sortie_table_in_time_and_team_order() -> None:
    """時間帯別の出撃を時刻と隊の番号の順に並べ、不在のリーダーを「不在」、所属メンバーが
    0人の時間帯を「休止」と書く（FRM-012、FRM-048のA-06）。"""

    markdown = _export()

    first = markdown.index("| 23:30 | 第1隊 | 2 | 700 | 1 | 山田 |")
    second = markdown.index("| 23:30 | 第2隊 | 3 | 600 | 3 | 不在 |")
    fourth = markdown.index("| 23:30 | 第4隊 | 0 | 0 | 0 | 休止 |")
    assert first < second < fourth


def test_exporter_shows_self_check_and_warnings_with_time() -> None:
    """自己チェックに待機、別枠、警告の数を示し、警告に時刻を付ける（OUT-011）。"""

    markdown = _export()

    assert "- 必須条件: OK\n" in markdown
    assert "- 待機: 1人\n- 別枠: 1人\n- 警告: 2件\n" in markdown
    assert "- 23:30: 第4隊が8人未満です: 7人\n" in markdown
    assert "- 第2隊はリーダー不在です\n" in markdown


SUPPORTER = Member("ハヤテ", "SKY", Tier.G5, has_vc=True, end_time_minutes=22 * 60)
LATE_LEADER = Member(
    "ツバサ",
    "SKY",
    Tier.G5,
    has_vc=True,
    starts_at_21=False,
    start_time_minutes=22 * 60,
)
OPENING = TimeSlot(21 * 60, 21 * 60 + 30)


def _export_with_late_start(notes: tuple[str, ...] = ()) -> str:
    plan = TeamPlan(
        teams=(
            TeamMembership(5, LEADER, (LEADER,)),
            TeamMembership(6, LATE_LEADER, (LATE_LEADER, SUPPORTER), 22 * 60),
        ),
        waiting=(),
        undecided=(),
        supports=(Support(SUPPORTER, OPENING, 5),),
    )
    report = ValidationReport(
        issues=(),
        warnings=(),
        sortie_metrics=(
            SortieMetrics(5, OPENING, 2, 500, 2, "山田", support_count=1),
            SortieMetrics(6, OPENING, 0, 0, 0, None, started=False),
        ),
        waiting=(),
        undecided=(),
    )
    return TeamPlanMarkdownExporter(default_rules()).export(
        ValidatedTeamPlan(plan=plan, report=report, proven_optimal=True, notes=notes)
    )


def test_exporter_shows_sortie_start_and_supports() -> None:
    """遅れて出撃する隊の出撃開始時刻と、出撃開始前の「応援→第○隊」を示す（FRM-041、FRM-042）。"""

    markdown = _export_with_late_start()

    assert (
        "## 第6隊 リーダー: ツバサ\n\n出撃開始: 22:00（遅れて出撃）\n所属: 2人\n"
        in (markdown)
    )
    assert "| 21:00 | ハヤテ | 第6隊 | 応援→第5隊 |" in markdown
    assert "| 21:00 | 第5隊 | 2（応援1） | 500 | 2 | 山田 |" in markdown
    assert "| 21:00 | 第6隊 | - | - | - | 出撃開始前 |" in markdown


def test_exporter_writes_notes_only_when_present() -> None:
    """回答の扱いの注記を「注記:」の行で示し、注記がなければ節を出さない（OUT-007）。"""

    with_notes = _export_with_late_start(("第7隊 21:00への回答は使いませんでした",))
    without_notes = _export_with_late_start()

    assert "## 注記\n\n- 注記: 第7隊 21:00への回答は使いませんでした\n" in with_notes
    assert "## 注記" not in without_notes
    assert "## 注記" not in _export()
    assert "## 応援" not in _export()

"""編成の記録（PlanRecord）の不変条件と、今回の参加者一覧との照合を検証する（DAT-010、FRM-071）。

名前は架空である。
"""

from datetime import datetime, timedelta, timezone

import pytest

from kvk_team.team_building.domain.member import Member, Tier
from kvk_team.team_building.domain.plan import (
    Support,
    TeamMembership,
    TeamPlan,
    TimeSlot,
)
from kvk_team.team_building.domain.plan_record import (
    PlanRecord,
    PlanRecordError,
    RecordedMember,
    RecordedTeam,
)
from kvk_team.team_building.domain.specification import (
    LateStart,
    MemberRef,
    OperatorSpecification,
    SupportRef,
)
from kvk_team.team_building.domain.validation import (
    ValidatedTeamPlan,
    ValidationReport,
)

JST = timezone(timedelta(hours=9))
CREATED_AT = datetime(2026, 1, 1, 21, 52, 30, tzinfo=JST)


def _ref(name: str) -> MemberRef:
    return MemberRef(name, "AAA")


def _team(
    number: int, leader: str, *others: str, start: int | None = None
) -> RecordedTeam:
    return RecordedTeam(
        number=number,
        leader=_ref(leader),
        members=(_ref(leader), *(_ref(name) for name in others)),
        start_minutes=start,
    )


def _record(**changes: object) -> PlanRecord:
    values: dict[str, object] = {
        "created_at": CREATED_AT,
        "teams": (_team(1, "ユウ", "カイ"), _team(2, "ミナ"), _team(3, "ソラ")),
        "supports": (),
        "waiting": (RecordedMember(_ref("レン")),),
        "undecided": (RecordedMember(_ref("サキ")),),
    }
    values.update(changes)
    return PlanRecord(**values)  # type: ignore[arg-type]


def _member(name: str) -> Member:
    return Member(name=name, alliance="AAA", tier=Tier.G8)


def test_record_from_validated_plan_keeps_membership_start_support_and_seats() -> None:
    """検証済みの編成から、所属、出撃開始時刻、応援、待機、別枠を名前と同盟で記録する。"""

    yuu, kai, mina, sora, ren, saki, nagi, riku = (
        _member(name)
        for name in ("ユウ", "カイ", "ミナ", "ソラ", "レン", "サキ", "ナギ", "リク")
    )
    plan = TeamPlan(
        teams=(
            TeamMembership(1, yuu, (yuu,)),
            TeamMembership(2, mina, (mina,)),
            TeamMembership(3, sora, (sora,)),
            TeamMembership(5, nagi, (nagi,)),
            TeamMembership(6, riku, (riku, kai), start_minutes=22 * 60),
        ),
        waiting=(ren,),
        undecided=(saki,),
        supports=(Support(kai, TimeSlot(21 * 60, 21 * 60 + 30), 5),),
    )
    report = ValidationReport((), (), (), (ren,), (saki,))
    validated = ValidatedTeamPlan(plan=plan, report=report, proven_optimal=True)

    record = PlanRecord.from_validated(validated, CREATED_AT)

    assert record == PlanRecord(
        created_at=CREATED_AT,
        teams=(
            _team(1, "ユウ"),
            _team(2, "ミナ"),
            _team(3, "ソラ"),
            _team(5, "ナギ"),
            _team(6, "リク", "カイ", start=22 * 60),
        ),
        supports=(SupportRef(_ref("カイ"), 21 * 60, 5),),
        waiting=(RecordedMember(_ref("レン")),),
        undecided=(RecordedMember(_ref("サキ")),),
    )


def test_record_keeps_destination_alliance_for_power_mode() -> None:
    """総力モードの移動先（FRM-071）を、隊と、待機・別枠のメンバーごとに持てる。"""

    record = _record(
        teams=(
            RecordedTeam(1, _ref("ユウ"), (_ref("ユウ"),), destination_alliance="AAA"),
            _team(2, "ミナ"),
            _team(3, "ソラ"),
        ),
        waiting=(RecordedMember(_ref("レン"), destination_alliance="BBB"),),
    )

    assert record.teams[0].destination_alliance == "AAA"
    assert record.waiting[0].destination_alliance == "BBB"
    assert record.undecided[0].destination_alliance is None


def test_record_counts_members_missing_from_current_roster() -> None:
    """今回の参加者一覧に名前と同盟の組で当たらない人数を数える。同盟が変わった人も数える。"""

    record = _record()
    roster = [_member(name) for name in ("ユウ", "カイ", "ミナ", "ソラ", "サキ")] + [
        Member(name="レン", alliance="BBB", tier=Tier.G8)
    ]

    assert record.unmatched_count(roster) == 1
    assert record.unmatched_count([*roster, _member("レン")]) == 0


def test_record_leader_may_be_undecided() -> None:
    """参加時間未定のリーダーは隊の所属ではなく別枠に置ける（FRM-060）。"""

    record = _record(
        teams=(
            _team(1, "ユウ"),
            _team(2, "ミナ"),
            RecordedTeam(3, _ref("サキ"), (_ref("ソラ"),)),
        )
    )

    assert record.teams[2].leader == _ref("サキ")


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (
            {"created_at": datetime(2026, 1, 1, 21, 52, 30)},
            "created_atに時差がありません",
        ),
        ({"teams": ()}, "隊がありません"),
        (
            {"teams": (_team(1, "ユウ"), _team(1, "ミナ"))},
            "第1隊が2つあります",
        ),
        (
            {"teams": (_team(0, "ユウ"),)},
            "隊の番号は1以上",
        ),
        (
            {"teams": (_team(1, "ユウ", "カイ"), _team(2, "ミナ", "カイ"))},
            "同じメンバーが第1隊の所属と第2隊の所属にいます",
        ),
        (
            {"waiting": (RecordedMember(_ref("カイ")),)},
            "同じメンバーが第1隊の所属と待機にいます",
        ),
        (
            {"teams": (RecordedTeam(1, _ref("ユウ"), (_ref("カイ"),)),)},
            "第1隊のリーダーが、その隊の所属にも別枠にもいません",
        ),
        (
            {
                "teams": (_team(1, "ユウ", "カイ"), _team(5, "ナギ")),
                "supports": (SupportRef(_ref("カイ"), 21 * 60, 5),),
            },
            "21:00の第5隊への応援のメンバーが、遅れて出撃する隊に所属していません",
        ),
        (
            {
                "teams": (_team(1, "ユウ"), _team(6, "リク", "カイ", start=22 * 60)),
                "supports": (SupportRef(_ref("カイ"), 21 * 60, 9),),
            },
            "21:00の第9隊への応援の応援先がありません",
        ),
        (
            {
                "teams": (_team(1, "ユウ"), _team(6, "リク", "カイ", start=22 * 60)),
                "supports": (SupportRef(_ref("カイ"), 21 * 60, 1),),
            },
            "21:00の第1隊への応援の応援先は応援を受けられない隊です",
        ),
        (
            {
                "teams": (
                    _team(1, "ユウ"),
                    _team(4, "ナギ"),
                    _team(6, "リク", "カイ", start=22 * 60),
                ),
                "supports": (SupportRef(_ref("カイ"), 21 * 60, 4),),
            },
            "21:00の第4隊への応援の応援先は応援を受けられない隊です",
        ),
        (
            {
                "teams": (_team(1, "ユウ"), _team(6, "リク", "カイ", start=22 * 60)),
                "supports": (SupportRef(_ref("カイ"), 21 * 60, 6),),
            },
            "21:00の第6隊への応援の応援先が、応援するメンバー自身の隊です",
        ),
        (
            {
                "teams": (
                    _team(5, "ナギ"),
                    _team(6, "リク", "カイ", start=22 * 60),
                ),
                "supports": (SupportRef(_ref("カイ"), 22 * 60, 5),),
            },
            "22:00の第5隊への応援が、出撃開始前の時間帯ではありません",
        ),
        (
            {
                "teams": (
                    _team(5, "ナギ"),
                    _team(6, "リク", "カイ", start=22 * 60),
                ),
                "supports": (
                    SupportRef(_ref("カイ"), 21 * 60, 5),
                    SupportRef(_ref("カイ"), 21 * 60, 5),
                ),
            },
            "同じメンバーの21:00の応援が2つあります",
        ),
        (
            {"teams": (_team(3, "ユウ", start=22 * 60),)},
            "第3隊は遅れて出撃できない隊です",
        ),
        (
            {
                "teams": (
                    RecordedTeam(1, _ref("サキ"), (_ref("ユウ"),)),
                    RecordedTeam(2, _ref("サキ"), (_ref("ミナ"),)),
                )
            },
            "同じメンバーが2つの隊のリーダーです",
        ),
        (
            {"waiting": (RecordedMember(_ref("レン"), destination_alliance=" "),)},
            "移動先の同盟が空です",
        ),
    ],
)
def test_record_rejects_inconsistent_values_without_names(
    changes: dict[str, object], message: str
) -> None:
    """成り立たない記録を、名前を書かずに隊、時刻、区分で示して拒否する。"""

    with pytest.raises(PlanRecordError) as error:
        _record(**changes)

    assert message in str(error.value)
    for name in ("ユウ", "カイ", "ミナ", "レン", "リク", "サキ", "ナギ"):
        assert name not in str(error.value)


def test_specification_carries_previous_plan_through_accepted_answers() -> None:
    """前回の編成は運用者の指定と1つの値で持ち、回答を受け入れても失わない（README 5章の分割案2）。"""

    specification = OperatorSpecification(
        leaders=(_ref("ユウ"), _ref("ミナ"), _ref("ソラ"), _ref("リク")),
        previous_plan=_record(),
    )

    accepted = specification.with_late_start(LateStart(4, 22 * 60))

    assert accepted.previous_plan == _record()
    assert accepted.late_starts == (LateStart(4, 22 * 60),)

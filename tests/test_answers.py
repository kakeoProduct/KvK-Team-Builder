"""運用者の回答（遅れて出撃する隊と応援先）のドメインの値と、ほかの指定で変わらない誤りのテスト。

FRM-041、FRM-042、FRM-047と、回答を確かめる手順の1（作成者の仮定A-41）を確かめる。
名前は架空で、エラーの文には名前を出さない（ADR 0026）。
"""

import pytest

from kvk_team.team_building.domain.answers import Answer, check_answers
from kvk_team.team_building.domain.member import Member, Tier
from kvk_team.team_building.domain.specification import (
    LateStart,
    MemberRef,
    OperatorSpecification,
    SpecificationError,
    SupportRef,
)
from kvk_team.team_building.domain.team import is_opening
from kvk_team.team_building.domain.team_master import EventTimeSettings

ALLIANCE = "架空同盟"
EVENT = EventTimeSettings(start_minutes=21 * 60, end_minutes=25 * 60)
H21 = 21 * 60
H2130 = H21 + 30
H22 = 22 * 60


def _member(name: str, start: int | None = H21, end: int | None = 25 * 60) -> Member:
    return Member(
        name=name,
        alliance=ALLIANCE,
        tier=Tier.G6,
        has_vc=True,
        start_time_minutes=start,
        end_time_minutes=end,
    )


def _ref(name: str) -> MemberRef:
    return MemberRef(name, ALLIANCE)


LEADERS = [_member(f"リーダー{number:02d}") for number in range(1, 11)]
# 第10隊のリーダーは22:00から来る。早く来る2人は21:00から22:00まで参加する。
LEADERS[9] = _member("リーダー10", start=H22)
EARLY = _member("ハヤテ", end=H22)
EARLY_TWO = _member("ツバサ", end=H22)
LATE_ONLY = _member("ユウキ", start=H22)
UNDECIDED = _member("ミライ", start=None, end=None)
MEMBERS = [*LEADERS, EARLY, EARLY_TWO, LATE_ONLY, UNDECIDED]
SPECIFICATION = OperatorSpecification(
    leaders=tuple(_ref(member.name) for member in LEADERS)
)


def _support(name: str, slot: int, team: int = 7) -> SupportRef:
    return SupportRef(_ref(name), slot, team)


def _early_supports(name: str = "ハヤテ", team: int = 7) -> tuple[SupportRef, ...]:
    return (_support(name, H21, team), _support(name, H2130, team))


def _answer(
    *supports: SupportRef,
    target: tuple[int, int] = (7, H21),
    team: int = 10,
    start: int = H22,
) -> Answer:
    return Answer(
        target_team=target[0],
        target_slot_start=target[1],
        late_start=LateStart(team=team, start_minutes=start, supports=supports),
    )


def _check(*answers: Answer) -> None:
    check_answers(answers, MEMBERS, SPECIFICATION, EVENT)


def test_valid_answer_passes() -> None:
    """出撃開始前に参加する時間帯すべてに応援先がある回答は通る。"""

    _check(_answer(*_early_supports()))


def test_late_start_sorts_supports_so_written_order_does_not_matter() -> None:
    """応援の書いた順によらず同じ値になる（FRM-090の性質(5)）。"""

    first = LateStart(10, H22, _early_supports())
    second = LateStart(10, H22, tuple(reversed(_early_supports())))

    assert first == second


def test_late_start_rejects_two_supports_for_same_member_and_slot() -> None:
    """1人の1つの時間帯に応援先は1つだけとする（FRM-042）。"""

    with pytest.raises(SpecificationError, match="同じメンバーの同じ時間帯"):
        LateStart(10, H22, (_support("ハヤテ", H21, 7), _support("ハヤテ", H21, 8)))


def test_specification_rejects_two_late_starts_for_same_team() -> None:
    """1つの隊の出撃開始時刻は1つだけとする。"""

    with pytest.raises(SpecificationError, match="第10隊"):
        OperatorSpecification(
            leaders=SPECIFICATION.leaders,
            late_starts=(LateStart(10, H22), LateStart(10, H22 + 30)),
        )


def test_specification_rejects_member_supporting_from_two_late_teams() -> None:
    """応援するメンバーは1つの遅れて出撃する隊に所属する（作成者の仮定A-16）。"""

    with pytest.raises(SpecificationError, match="2つの遅れて出撃する隊"):
        OperatorSpecification(
            leaders=SPECIFICATION.leaders,
            late_starts=(
                LateStart(9, H22, _early_supports(team=7)),
                LateStart(10, H22, _early_supports(team=8)),
            ),
        )


@pytest.mark.parametrize(
    ("answer", "message"),
    [
        (_answer(target=(12, H21)), "対象の隊"),
        (_answer(target=(7, H21 + 10)), "対象の時刻"),
        (_answer(target=(7, H22)), "序盤（戦闘開始からの1時間）の問いにだけ"),
        (_answer(team=2), "第1〜3隊は遅れて出撃させられません"),
        (_answer(team=11), "遅れて出撃させる隊"),
        (_answer(start=H21), "出撃開始時刻"),
        (_answer(start=25 * 60), "出撃開始時刻"),
        (_answer(start=H22 + 10), "出撃開始時刻"),
        (_answer(_support("いない人", H21)), "参加者一覧に見つかりません"),
        (_answer(_support("ミライ", H21)), "参加時間未定"),
        (_answer(*_early_supports("リーダー05")), "ほかの隊のリーダー"),
        (
            _answer(_support("ユウキ", H21), _support("ユウキ", H2130)),
            "参加していません",
        ),
        (_answer(*_early_supports(), _support("ハヤテ", H22)), "出撃開始前"),
        (_answer(*_early_supports(team=4)), "第5隊以降"),
        (_answer(*_early_supports(team=10)), "第5隊以降の、ほかの隊"),
        (_answer(*_early_supports(team=12)), "応援先の隊"),
        (_answer(_support("ハヤテ", H21)), "21:30にも参加"),
    ],
)
def test_answer_errors_that_no_other_specification_can_change(
    answer: Answer, message: str
) -> None:
    """ほかの指定で変わらない誤りは、理由を示して入力のエラーにする（FRM-047、作成者の仮定A-41）。"""

    with pytest.raises(SpecificationError, match=message) as raised:
        _check(answer)
    assert "ハヤテ" not in str(raised.value)
    assert "いない人" not in str(raised.value)


def test_late_team_leader_present_before_start_needs_support() -> None:
    """出撃開始前に参加するリーダーは隊を移れないため、応援先がなければ入力のエラーにする。"""

    early_leader = [*MEMBERS]
    early_leader[9] = _member("リーダー10")
    with pytest.raises(SpecificationError, match="第10隊のリーダー.*21:00"):
        check_answers([_answer(*_early_supports())], early_leader, SPECIFICATION, EVENT)


def test_answer_error_message_does_not_depend_on_written_order() -> None:
    """回答の書いた順によらず、同じ誤りを示す（FRM-090の性質(5)）。"""

    # 誤りを含む回答を2件にし、書いた順で確かめると先に書いた方の誤りになるようにする。
    later_target = _answer(target=(8, H21), team=2)
    earlier_target = _answer(target=(7, H21), team=11)
    messages = []
    for answers in ((later_target, earlier_target), (earlier_target, later_target)):
        with pytest.raises(SpecificationError) as raised:
            check_answers(answers, MEMBERS, SPECIFICATION, EVENT)
        messages.append(str(raised.value))
    assert messages[0] == messages[1]
    assert "第7隊 21:00への回答" in messages[0]


def test_support_error_names_time_and_target_instead_of_written_position() -> None:
    """応援の誤りは、書いた位置ではなく時刻と応援先で示す（DAT-009、ADR 0026）。

    応援は書いた順によらない並びに直して持つため、位置で示すとファイルの順と合わない。
    """

    answer = _answer(_support("ツバサ", H2130), _support("いない人", H21, team=8))

    with pytest.raises(SpecificationError) as raised:
        _check(answer)

    message = str(raised.value)
    assert "21:00の第8隊への応援" in message
    assert "番目" not in message
    assert "いない人" not in message


def test_support_error_counts_supports_with_same_time_and_target() -> None:
    """同じ時刻と応援先の応援が並ぶ場合は、その件数を添えて示す。"""

    answer = _answer(*_early_supports(), _support("いない人", H21))

    with pytest.raises(SpecificationError) as raised:
        _check(answer)

    assert "21:00の第7隊への応援（同じ時刻と応援先の2件のうちの1件）" in str(
        raised.value
    )


def test_missing_support_names_first_support_of_member() -> None:
    """応援先の欠けは、そのメンバーの最初の応援の時刻と応援先で示す（FRM-047）。"""

    with pytest.raises(SpecificationError) as raised:
        _check(_answer(_support("ハヤテ", H21, team=8)))

    message = str(raised.value)
    assert "21:00の第8隊への応援のメンバーは21:30にも参加" in message
    assert "ハヤテ" not in message


def test_opening_is_first_hour_from_battle_start() -> None:
    """序盤は戦闘開始からの1時間とする（FRM-040）。"""

    assert is_opening(H21, H21)
    assert is_opening(H2130, H21)
    assert not is_opening(H22, H21)
    assert is_opening(20 * 60 + 30, 20 * 60)
    assert not is_opening(H21, 20 * 60)

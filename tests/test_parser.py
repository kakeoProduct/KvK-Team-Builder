"""Markdown参加者解析のテスト。"""

import pytest

from kvk_team.team_building.adapters.input.markdown_member_parser import (
    MarkdownMemberParser,
    ParseError,
)
from kvk_team.team_building.domain.member import Availability, Tier


def test_parse_documented_markdown_format() -> None:
    """プロジェクト仕様の最小形式をそのまま解析できる。"""

    members = MarkdownMemberParser().parse(
        """
        同盟名:SKY

        G8:
        山田◯◇
        いろは◯◇
        """
    )

    assert [member.name for member in members] == ["山田", "いろは"]
    assert all(member.alliance == "SKY" for member in members)
    assert all(member.tier is Tier.G8 for member in members)
    assert all(member.has_vc for member in members)
    assert all(member.starts_at_21 for member in members)


def test_parse_multiple_alliances_tiers_and_metadata() -> None:
    """インラインの参加時間と除外情報を型付きの値へ変換する。"""

    members = MarkdownMemberParser().parse(
        """
        # 参加者一覧
        同盟名：SKY
        ## G7
        - Alice◇ 24時まで
        - Bob [途中参加]

        同盟:FOX
        その他:
        Carol [VC] [特殊部隊]
        """
    )

    alice, bob, carol = members
    assert alice.availability is Availability.UNTIL_24
    assert alice.has_vc
    assert bob.availability is Availability.LATE_JOIN
    assert not bob.starts_at_21
    assert carol.tier is Tier.OTHER
    assert carol.has_vc
    assert carol.special_unit


def test_reject_member_without_alliance_and_tier_context() -> None:
    """構造上の誤りでは入力行を特定する。"""

    with pytest.raises(ParseError, match=r"line 1.*同盟名"):
        MarkdownMemberParser().parse("山田◯◇")

    with pytest.raises(ParseError, match=r"line 2.*Tier"):
        MarkdownMemberParser().parse("同盟名:SKY\n山田◯◇")


def test_reject_duplicate_member_names() -> None:
    """重複した識別情報による曖昧な配置を拒否する。"""

    markdown = "同盟名:SKY\nG8:\n山田◯\n山田◯"

    with pytest.raises(ParseError, match="重複.*山田"):
        MarkdownMemberParser().parse(markdown)


def test_parse_operational_compact_format() -> None:
    """凡例、インライン一覧、下位Tier、時間区分を解析する。"""

    members = MarkdownMemberParser().parse(
        """
        同盟名:ARC
        ◯:マンスリー持ち
        △:途中抜け
        ◇:VC参加可能(聴き専可)

        最初から参加
        G6:Alice〇◇、Bob△（24時）Carol◇、Frank△(22時頃)◇
        G4以下:MonthlyOnly◯

        途中から参加
        G5:Dave◇(22時半頃～)、Eve(23-25)

        同盟名:NEW
        G5:Fresh◇
        """
    )

    assert [member.name for member in members] == [
        "Alice",
        "Bob",
        "Carol",
        "Frank",
        "MonthlyOnly",
        "Dave",
        "Eve",
        "Fresh",
    ]
    assert members[0].has_vc
    assert not members[1].has_vc
    assert members[1].availability is Availability.UNTIL_24
    assert members[1].start_time_minutes == 21 * 60
    assert members[1].end_time_minutes == 24 * 60
    assert members[2].has_vc
    assert members[3].has_vc
    assert members[3].availability is Availability.UNTIL_23
    assert members[4].tier is Tier.OTHER
    assert not members[4].has_vc
    assert all(not member.starts_at_21 for member in members[-3:-1])
    assert all(
        member.availability is Availability.LATE_JOIN for member in members[-3:-1]
    )
    assert members[-3].start_time_minutes == 22 * 60 + 30
    assert members[-3].end_time_minutes is None
    assert members[-2].start_time_minutes == 23 * 60
    assert members[-2].end_time_minutes == 25 * 60
    assert members[-1].starts_at_21


def test_uncertain_delay_note_is_not_the_same_as_unknown_start_time() -> None:
    """遅れる可能性だけでは今回の時間確定待ちへ分類しない。"""

    member = MarkdownMemberParser().parse("同盟名:999\nG6:ゆうき◇△(遅れるかも)")[0]

    assert member.starts_at_21
    assert member.start_time_minutes == 21 * 60

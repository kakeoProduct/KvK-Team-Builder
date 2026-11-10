"""ドメインモデルと固定ルールのテスト。"""

import pytest

from kvk_team.interfaces.cli.composition import default_rules
from kvk_team.team_building.domain.member import Member, Tier
from kvk_team.team_building.domain.specification import (
    MemberRef,
    OperatorSpecification,
    SpecificationError,
    resolve_leaders,
)
from kvk_team.team_building.domain.team import (
    EXTENSION_BOUNDARY_MINUTES,
    TOP_TEAM_COUNT,
    TOP_TEAM_SIZE,
    is_top_team,
    team_name,
)


def test_member_requires_name_and_alliance() -> None:
    """安定した識別情報を持たないメンバーを拒否する。"""

    with pytest.raises(ValueError, match="name"):
        Member(name=" ", alliance="SKY", tier=Tier.G8)

    with pytest.raises(ValueError, match="alliance"):
        Member(name="山田", alliance=" ", tier=Tier.G8)


def test_fixed_values_match_user_decisions() -> None:
    """利用者が決めた固定値をドメインの定数として持つ（ADR 0034）。"""

    assert (TOP_TEAM_COUNT, TOP_TEAM_SIZE) == (3, 8)
    assert EXTENSION_BOUNDARY_MINUTES == 24 * 60
    assert [is_top_team(number) for number in range(1, 5)] == [True, True, True, False]
    assert team_name(4) == "第4隊"


def test_leaders_resolve_by_name_and_alliance_in_order() -> None:
    """リーダーは名前と同盟の組で参加者一覧から探し、順が隊の番号になる（FRM-001、DAT-007）。"""

    members = [
        Member("ユウ", "BBB", Tier.G7),
        Member("ユウ", "AAA", Tier.G8),
        Member("ミナ", "BBB", Tier.G8),
        Member("ソラ", "AAA", Tier.G8),
    ]
    specification = OperatorSpecification(
        leaders=(
            MemberRef("ミナ", "BBB"),
            MemberRef("ユウ", "AAA"),
            MemberRef("ソラ", "AAA"),
        )
    )

    assert resolve_leaders(specification, members) == (
        members[2],
        members[1],
        members[3],
    )


def test_leader_matching_two_members_is_input_error() -> None:
    """名前と同盟で2人に当たるリーダーは、1人に決まらないため入力のエラーにする（FRM-076にならう）。"""

    members = [Member("ユウ", "AAA", Tier.G8), Member("ユウ", "AAA", Tier.G7)]
    specification = OperatorSpecification(
        leaders=(
            MemberRef("ユウ", "AAA"),
            MemberRef("ミナ", "BBB"),
            MemberRef("ソラ", "AAA"),
        )
    )

    with pytest.raises(
        SpecificationError, match="1番目（第1隊のリーダー）が.*2人以上に当たります"
    ):
        resolve_leaders(specification, members)


def test_tier_power_has_no_monthly_adjustment() -> None:
    """Tier値には仕様で定めた基本戦力だけを使用する。"""

    assert default_rules().tier_power == {
        Tier.G8: 400,
        Tier.G7: 300,
        Tier.G6: 200,
        Tier.G5: 100,
        Tier.OTHER: 20,
    }

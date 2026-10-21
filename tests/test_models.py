"""ドメインモデルと固定ルールのテスト。"""

import pytest

from kvk_team.interfaces.cli.composition import default_rules
from kvk_team.team_building.domain.member import Member, Tier
from kvk_team.team_building.domain.team import TeamLabel


def test_member_requires_name_and_alliance() -> None:
    """安定した識別情報を持たないメンバーを拒否する。"""

    with pytest.raises(ValueError, match="name"):
        Member(name=" ", alliance="SKY", tier=Tier.G8)

    with pytest.raises(ValueError, match="alliance"):
        Member(name="山田", alliance=" ", tier=Tier.G8)


def test_fixed_rally_leaders_match_kvk_rules() -> None:
    """JSONマスタの集結主対応をルールから参照できる。"""

    assert default_rules().rally_leaders[TeamLabel.A] == "山田"
    assert default_rules().rally_leaders[TeamLabel.K] == "翡翠"
    assert len(default_rules().rally_leaders) == 11


def test_tier_power_has_no_monthly_adjustment() -> None:
    """Tier値には仕様で定めた基本戦力だけを使用する。"""

    assert default_rules().tier_power == {
        Tier.G8: 400,
        Tier.G7: 300,
        Tier.G6: 200,
        Tier.G5: 100,
        Tier.OTHER: 20,
    }

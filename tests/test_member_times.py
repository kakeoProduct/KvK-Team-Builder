"""構造化した参加時間のテスト。"""

import pytest

from kvk_team.team_building.domain.member import Member, Tier


def test_late_member_without_clock_uses_unknown_start() -> None:
    """一般的な途中参加フラグに誤った正確な開始時刻を設定しない。"""

    member = Member(
        name="Alice",
        alliance="SKY",
        tier=Tier.G5,
        starts_at_21=False,
    )

    assert member.start_time_minutes is None


def test_member_rejects_non_positive_participation_window() -> None:
    """構造化した時間範囲では終了時刻が開始時刻より後になる。"""

    with pytest.raises(ValueError, match="end time"):
        Member(
            name="Alice",
            alliance="SKY",
            tier=Tier.G5,
            start_time_minutes=23 * 60,
            end_time_minutes=22 * 60,
        )

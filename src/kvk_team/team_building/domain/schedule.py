"""時間帯別チーム編成のドメインモデル。"""

from dataclasses import dataclass

from kvk_team.team_building.domain.member import Member
from kvk_team.team_building.domain.team import TeamLabel


@dataclass(frozen=True, slots=True)
class TimeSlot:
    """開始時刻を含み終了時刻を含まない時間区間。"""

    start_minutes: int
    end_minutes: int


@dataclass(frozen=True, slots=True)
class SlotAssignment:
    """1つの時間スロットにおける1チームの配置。"""

    team_label: TeamLabel
    time_slot: TimeSlot
    members: tuple[Member, ...]

    def member_names(self) -> tuple[str, ...]:
        """配置されたメンバー名を返す。"""

        return tuple(member.name for member in self.members)


@dataclass(frozen=True, slots=True)
class DynamicTeamPlan:
    """確定配置と時間未定の待機メンバーを持つ動的編成結果。"""

    assignments: tuple[SlotAssignment, ...]
    standby_members: tuple[Member, ...]

    def assignments_for_team(
        self,
        team_label: TeamLabel,
    ) -> tuple[SlotAssignment, ...]:
        """指定チームの配置を時間順で返す。"""

        return tuple(
            assignment
            for assignment in self.assignments
            if assignment.team_label is team_label
        )

    def assignment_at(
        self,
        team_label: TeamLabel,
        start_minutes: int,
    ) -> SlotAssignment:
        """指定チーム・開始時刻の配置を返す。"""

        for assignment in self.assignments:
            if (
                assignment.team_label is team_label
                and assignment.time_slot.start_minutes == start_minutes
            ):
                return assignment
        raise KeyError((team_label, start_minutes))

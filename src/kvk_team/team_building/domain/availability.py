"""参加時間を時間スロットへ解決する。"""

from dataclasses import dataclass

from kvk_team.team_building.domain.member import (
    MINUTES_PER_HOUR,
    Availability,
    Member,
)
from kvk_team.team_building.domain.team_master import EventTimeSettings


@dataclass(frozen=True, slots=True)
class ResolvedAvailability:
    """イベント範囲内で確定した1人の参加時間。"""

    member: Member
    start_minutes: int
    end_minutes: int

    def covers(self, slot_start: int, slot_end: int) -> bool:
        """指定スロット全体へ参加できるかを返す。"""

        return self.start_minutes <= slot_start and self.end_minutes >= slot_end


@dataclass(frozen=True, slots=True)
class AvailabilityPartition:
    """時間確定メンバーと時間未定メンバーの分割結果。"""

    confirmed: tuple[ResolvedAvailability, ...]
    standby: tuple[Member, ...]


@dataclass(slots=True)
class AvailabilityResolver:
    """Memberの時間情報をイベント時間へ正規化する。"""

    event_time: EventTimeSettings

    def partition(self, members: list[Member]) -> AvailabilityPartition:
        """開始時刻が確定しているメンバーだけをスロット配置対象にする。"""

        confirmed: list[ResolvedAvailability] = []
        standby: list[Member] = []
        for member in members:
            resolved = self._resolve(member)
            if resolved is None:
                standby.append(member)
            else:
                confirmed.append(resolved)
        return AvailabilityPartition(tuple(confirmed), tuple(standby))

    def _resolve(self, member: Member) -> ResolvedAvailability | None:
        """1人の参加時間を解決し、開始未定ならNoneを返す。"""

        if member.start_time_minutes is None:
            return None
        inferred_end = self._infer_end(member)
        start = max(member.start_time_minutes, self.event_time.start_minutes)
        end = min(inferred_end, self.event_time.end_minutes)
        if start >= end:
            return None
        return ResolvedAvailability(member, start, end)

    def _infer_end(self, member: Member) -> int:
        """明示終了時刻がない場合に参加優先度から終了時刻を補完する。"""

        if member.end_time_minutes is not None:
            return member.end_time_minutes
        end_by_availability = {
            Availability.UNTIL_23: 23 * MINUTES_PER_HOUR,
            Availability.UNTIL_24: 24 * MINUTES_PER_HOUR,
            Availability.UNTIL_25: 25 * MINUTES_PER_HOUR,
        }
        return end_by_availability.get(
            member.availability,
            self.event_time.end_minutes,
        )

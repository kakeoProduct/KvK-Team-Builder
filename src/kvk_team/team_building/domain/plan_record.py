"""編成の記録。出力した編成を、次の実行へ前回の編成として渡すための不変な値（DAT-010）。

前回の編成からの移動の数（FRM-071、FRM-037の⑦）に要る値だけを、メンバーを名前と同盟の組
（`MemberRef`、DAT-007）で指して持つ。所属、出撃開始時刻、応援、待機、別枠と、総力モードの移動先
（隊と、待機・別枠のメンバーごと。旧Q-122）である。この版では移動の数を比べず、読み込みと今回の
参加者一覧との照合だけに使う（ADR 0036）。

個人名がエラーから不具合報告へ漏れないよう（ADR 0026）、エラーの文には名前を書かず、隊、時刻、
区分で示す。
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime

from kvk_team.team_building.domain.member import Member
from kvk_team.team_building.domain.specification import MemberRef, SupportRef
from kvk_team.team_building.domain.team import (
    can_receive_support,
    can_start_late,
    team_name,
)
from kvk_team.team_building.domain.validation import ValidatedTeamPlan, format_clock


class PlanRecordError(ValueError):
    """編成の記録が成り立たない場合に送出する。"""


@dataclass(frozen=True, slots=True)
class RecordedTeam:
    """記録した1つの隊。

    `members`は時間帯をまたいで変わらない所属で、参加時間が確定したリーダーを含む。参加時間未定の
    リーダーは別枠に置く（FRM-060）。
    """

    number: int
    leader: MemberRef
    members: tuple[MemberRef, ...]
    start_minutes: int | None = None
    """出撃開始時刻（FRM-041）。Noneは戦闘開始から出撃する隊を表す。"""
    destination_alliance: str | None = None
    """総力モードの隊の移動先の同盟（FRM-071）。通常モードではNone。"""


@dataclass(frozen=True, slots=True)
class RecordedMember:
    """記録した、隊に所属しないメンバー（待機か別枠）。"""

    member: MemberRef
    destination_alliance: str | None = None
    """総力モードの移動先の同盟（FRM-071、旧Q-122）。通常モードではNone。"""


@dataclass(frozen=True, slots=True)
class PlanRecord:
    """出力した編成の記録。次の実行では前回の編成として受け取る。

    `created_at`は実行の時刻（出力のフォルダ名と同じ時刻）で、時差を持つ（DAT-002）。
    """

    created_at: datetime
    teams: tuple[RecordedTeam, ...]
    supports: tuple[SupportRef, ...] = ()
    """出撃開始前の応援（FRM-042）。"""
    waiting: tuple[RecordedMember, ...] = ()
    undecided: tuple[RecordedMember, ...] = ()

    def __post_init__(self) -> None:
        """成り立たない記録を拒否する。"""

        if self.created_at.utcoffset() is None:
            raise PlanRecordError("created_atに時差がありません")
        self._check_teams()
        self._check_placements()
        self._check_leaders()
        self._check_supports()
        self._check_destinations()

    @classmethod
    def from_validated(
        cls, validated: ValidatedTeamPlan, created_at: datetime
    ) -> "PlanRecord":
        """検証済みの編成を記録にする。総力モードの移動先は、総力モードを加える分割案の7で書く。"""

        plan = validated.plan
        return cls(
            created_at=created_at,
            teams=tuple(
                RecordedTeam(
                    number=team.number,
                    leader=_ref(team.leader),
                    members=tuple(_ref(member) for member in team.members),
                    start_minutes=team.start_minutes,
                )
                for team in plan.teams
            ),
            supports=tuple(
                SupportRef(
                    member=_ref(support.member),
                    slot_start_minutes=support.time_slot.start_minutes,
                    team=support.team_number,
                )
                for support in plan.supports
            ),
            waiting=tuple(RecordedMember(_ref(member)) for member in plan.waiting),
            undecided=tuple(RecordedMember(_ref(member)) for member in plan.undecided),
        )

    def members(self) -> Iterator[MemberRef]:
        """記録したすべてのメンバー（隊の所属、待機、別枠）を返す。"""

        for team in self.teams:
            yield from team.members
        for seat in (*self.waiting, *self.undecided):
            yield seat.member

    def unmatched_count(self, members: Sequence[Member]) -> int:
        """今回の参加者一覧に、名前と同盟の組で当たらないメンバーの人数を返す。

        同盟が変わった人も当たらない人に数える。今回の参加者一覧で増えた人は数えない。
        """

        current = {MemberRef(member.name, member.alliance) for member in members}
        return sum(ref not in current for ref in self.members())

    def _check_teams(self) -> None:
        if not self.teams:
            raise PlanRecordError("隊がありません")
        numbers = [team.number for team in self.teams]
        invalid = [number for number in numbers if number < 1]
        if invalid:
            raise PlanRecordError("隊の番号は1以上で書いてください")
        repeated = sorted({number for number in numbers if numbers.count(number) > 1})
        if repeated:
            raise PlanRecordError(
                "、".join(team_name(number) for number in repeated) + "が2つあります"
            )

    def _placements(self) -> Iterator[tuple[MemberRef, str]]:
        for team in self.teams:
            for member in team.members:
                yield member, f"{team_name(team.number)}の所属"
        for seat in self.waiting:
            yield seat.member, "待機"
        for seat in self.undecided:
            yield seat.member, "別枠"

    def _check_placements(self) -> None:
        seen: dict[MemberRef, str] = {}
        for member, place in self._placements():
            if member in seen:
                raise PlanRecordError(f"同じメンバーが{seen[member]}と{place}にいます")
            seen[member] = place

    def _check_leaders(self) -> None:
        undecided = {seat.member for seat in self.undecided}
        leaders = [team.leader for team in self.teams]
        if len(set(leaders)) != len(leaders):
            raise PlanRecordError("同じメンバーが2つの隊のリーダーです")
        for team in self.teams:
            if team.start_minutes is not None and not can_start_late(team.number):
                raise PlanRecordError(
                    f"{team_name(team.number)}は遅れて出撃できない隊です"
                )
            if team.leader not in team.members and team.leader not in undecided:
                raise PlanRecordError(
                    f"{team_name(team.number)}のリーダーが、その隊の所属にも別枠にもいません"
                )

    def _check_supports(self) -> None:
        teams = {team.number: team for team in self.teams}
        seen: set[tuple[MemberRef, int]] = set()
        for support in self.supports:
            where = (
                f"{format_clock(support.slot_start_minutes)}の"
                f"{team_name(support.team)}への応援"
            )
            if support.team not in teams:
                raise PlanRecordError(f"{where}の応援先がありません")
            if not can_receive_support(support.team):
                raise PlanRecordError(f"{where}の応援先は応援を受けられない隊です")
            own = next(
                (team for team in self.teams if support.member in team.members),
                None,
            )
            if own is None or own.start_minutes is None:
                raise PlanRecordError(
                    f"{where}のメンバーが、遅れて出撃する隊に所属していません"
                )
            if own.number == support.team:
                raise PlanRecordError(
                    f"{where}の応援先が、応援するメンバー自身の隊です"
                )
            if support.slot_start_minutes >= own.start_minutes:
                raise PlanRecordError(f"{where}が、出撃開始前の時間帯ではありません")
            key = (support.member, support.slot_start_minutes)
            if key in seen:
                raise PlanRecordError(
                    "同じメンバーの"
                    f"{format_clock(support.slot_start_minutes)}の応援が2つあります"
                )
            seen.add(key)

    def _check_destinations(self) -> None:
        destinations = [
            *(team.destination_alliance for team in self.teams),
            *(seat.destination_alliance for seat in (*self.waiting, *self.undecided)),
        ]
        if any(
            destination is not None and not destination.strip()
            for destination in destinations
        ):
            raise PlanRecordError("移動先の同盟が空です")


def _ref(member: Member) -> MemberRef:
    return MemberRef(member.name, member.alliance)

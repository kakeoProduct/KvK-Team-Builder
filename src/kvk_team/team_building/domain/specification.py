"""運用者の指定を1つの不変な値として表す。

運用者の指定はOptimizerとValidatorへ同じ値として渡す（要件定義書の分割案の2）。
リーダー一覧と、回答から受け入れた遅れて出撃する隊と応援先（ADR 0035）を持つ。前回の編成などは
要件のあるIssueで加える。

個人名がエラーから不具合報告へ漏れないよう（ADR 0026）、エラーの文には名前を書かず、
指定の位置（リーダー一覧の何番目か）で示す。
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from kvk_team.team_building.domain.member import Member
from kvk_team.team_building.domain.team import TOP_TEAM_COUNT, team_name


class SpecificationError(ValueError):
    """運用者の指定が参加者一覧やほかの指定と成り立たない場合に送出する。"""


@dataclass(frozen=True, slots=True)
class MemberRef:
    """参加者一覧の名前と同盟の組でメンバーを指す（DAT-007）。"""

    name: str
    alliance: str

    def __post_init__(self) -> None:
        """空の名前や同盟でメンバーを指す指定を拒否する。"""

        if not self.name.strip():
            raise ValueError("メンバーの名前が空です")
        if not self.alliance.strip():
            raise ValueError("メンバーの同盟が空です")


def leader_position(number: int) -> str:
    """リーダー一覧の位置を、エラーで示す書き方にする。"""

    return f"リーダー一覧の{number}番目（{team_name(number)}のリーダー）"


@dataclass(frozen=True, slots=True)
class SupportRef:
    """遅れて出撃する隊のメンバーが、出撃開始前の1つの時間帯に応援する隊（FRM-042）。

    応援先はメンバーごと、時間帯ごとに運用者が選ぶ。応援を指定したメンバーは、その遅れて出撃する
    隊に所属する（作成者の仮定A-16）。
    """

    member: MemberRef
    slot_start_minutes: int
    team: int

    def sort_key(self) -> tuple[int, str, str, int]:
        """書いた順によらない並びの鍵を返す（FRM-090の性質(5)）。"""

        return (
            self.slot_start_minutes,
            self.member.name,
            self.member.alliance,
            self.team,
        )


@dataclass(frozen=True, slots=True)
class LateStart:
    """遅れて出撃する隊と出撃開始時刻、出撃開始前の応援先（FRM-041、FRM-042）。

    `supports`は書いた順によらない並びに直して持つ。1人の1つの時間帯に応援先は1つだけとする。
    """

    team: int
    start_minutes: int
    supports: tuple[SupportRef, ...] = ()

    def __post_init__(self) -> None:
        """応援を並べ直し、同じメンバーの同じ時間帯の重複を拒否する。"""

        ordered = tuple(sorted(self.supports, key=SupportRef.sort_key))
        object.__setattr__(self, "supports", ordered)
        keys = [(item.member, item.slot_start_minutes) for item in ordered]
        if len(set(keys)) != len(keys):
            raise SpecificationError(
                f"{team_name(self.team)}の応援に、同じメンバーの同じ時間帯が2つあります"
            )

    def sort_key(self) -> tuple[object, ...]:
        """書いた順によらない並びの鍵を返す。"""

        return (
            self.team,
            self.start_minutes,
            tuple(item.sort_key() for item in self.supports),
        )

    @property
    def supporters(self) -> frozenset[MemberRef]:
        """応援するメンバーを返す。"""

        return frozenset(item.member for item in self.supports)


@dataclass(frozen=True, slots=True)
class OperatorSpecification:
    """1回の編成で運用者が渡した指定。

    `leaders`はリーダー一覧で、並び順が隊の番号になる（FRM-001、FRM-006）。
    上位隊の3隊を作れないため、リーダーが3人未満の一覧は入力のエラーとする（作成者の仮定A-37）。
    `late_starts`は、回答から受け入れた遅れて出撃する隊と応援先（FRM-041、FRM-042）で、
    隊の番号の順に並べ直して持つ。
    """

    leaders: tuple[MemberRef, ...]
    late_starts: tuple[LateStart, ...] = ()

    def __post_init__(self) -> None:
        """隊を作れないリーダー一覧と、同時に成り立たない遅れて出撃する隊を拒否する。"""

        self._check_leaders()
        ordered = tuple(sorted(self.late_starts, key=LateStart.sort_key))
        object.__setattr__(self, "late_starts", ordered)
        teams = [late.team for late in ordered]
        repeated = sorted({team for team in teams if teams.count(team) > 1})
        if repeated:
            raise SpecificationError(
                "、".join(team_name(team) for team in repeated)
                + "の出撃開始時刻が2つあります"
            )
        supporters = [ref for late in ordered for ref in late.supporters]
        if len(set(supporters)) != len(supporters):
            raise SpecificationError(
                "同じメンバーが2つの遅れて出撃する隊から応援します"
            )

    def late_start(self, team: int) -> LateStart | None:
        """隊の遅れて出撃する指定を返す。なければNoneを返す。"""

        return next((late for late in self.late_starts if late.team == team), None)

    def with_late_start(self, late_start: LateStart) -> "OperatorSpecification":
        """遅れて出撃する隊を1つ加えた指定を返す。成り立たなければ`SpecificationError`を送出する。"""

        return OperatorSpecification(
            leaders=self.leaders, late_starts=(*self.late_starts, late_start)
        )

    def _check_leaders(self) -> None:
        """隊を作れないリーダー一覧を拒否する。"""

        if len(self.leaders) < TOP_TEAM_COUNT:
            raise SpecificationError(
                f"リーダーは上位隊の{TOP_TEAM_COUNT}人以上を指定してください"
                f"（{len(self.leaders)}人です）"
            )
        positions: defaultdict[MemberRef, list[int]] = defaultdict(list)
        for number, leader in enumerate(self.leaders, start=1):
            positions[leader].append(number)
        duplicates = [numbers for numbers in positions.values() if len(numbers) > 1]
        if duplicates:
            described = "、".join(
                "と".join(f"{number}番目" for number in numbers)
                for numbers in duplicates
            )
            raise SpecificationError(f"リーダー一覧の{described}が同じメンバーです")

    @property
    def team_count(self) -> int:
        """隊の数を返す。リーダーの人数と同じ（FRM-001）。"""

        return len(self.leaders)


def resolve_member(ref: MemberRef, members: Sequence[Member], where: str) -> Member:
    """名前と同盟の組に当たる参加者を1人返す。1人に決まらなければ入力のエラーにする。

    `where`は指定の位置を示す書き方で、エラーの文に名前の代わりに使う。
    """

    matches = [
        member
        for member in members
        if member.name == ref.name and member.alliance == ref.alliance
    ]
    if not matches:
        raise SpecificationError(
            f"{where}が、名前と同盟の組で参加者一覧に見つかりません"
        )
    if len(matches) > 1:
        raise SpecificationError(
            f"{where}が、名前と同盟の組で参加者一覧の2人以上に当たります"
        )
    return matches[0]


def resolve_leaders(
    specification: OperatorSpecification,
    members: Sequence[Member],
) -> tuple[Member, ...]:
    """リーダー一覧を隊の番号順の参加者へ解決する。"""

    return tuple(
        resolve_member(ref, members, leader_position(number))
        for number, ref in enumerate(specification.leaders, start=1)
    )

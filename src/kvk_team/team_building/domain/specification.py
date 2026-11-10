"""運用者の指定を1つの不変な値として表す。

運用者の指定はOptimizerとValidatorへ同じ値として渡す（要件定義書の分割案の2）。
このIssueではリーダー一覧だけを持ち、応援先、遅れて出撃する隊、前回の編成などは
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
class OperatorSpecification:
    """1回の編成で運用者が渡した指定。

    `leaders`はリーダー一覧で、並び順が隊の番号になる（FRM-001、FRM-006）。
    上位隊の3隊を作れないため、リーダーが3人未満の一覧は入力のエラーとする（作成者の仮定A-37）。
    """

    leaders: tuple[MemberRef, ...]

    def __post_init__(self) -> None:
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

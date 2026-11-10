"""運用者の回答と、ほかの指定によって変わらない誤りの確認（FRM-047、FRM-090、作成者の仮定A-41）。

回答は、番号付きの質問（FRM-075）の対象の（隊、時間帯）と、指定そのもの（遅れて出撃する隊、
出撃開始時刻、応援先）を持つ。質問の番号は書かない。アプリは回答を覚えず、運用者が同じファイルへ
足していく（作成者の仮定A-41）。

個人名がエラーから漏れないよう（ADR 0026）、エラーの文には名前を書かず、回答の対象と、
応援の時刻と応援先で示す。書いた順の位置は使わず、書いた順によらず同じ文にする（FRM-090の性質(5)）。
"""

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from kvk_team.team_building.domain.availability import (
    AvailabilityResolver,
    ResolvedAvailability,
)
from kvk_team.team_building.domain.member import Member
from kvk_team.team_building.domain.specification import (
    LateStart,
    OperatorSpecification,
    SpecificationError,
    resolve_leaders,
    resolve_member,
)
from kvk_team.team_building.domain.team import (
    FIRST_SUPPORTED_TEAM,
    SLOT_MINUTES,
    TOP_TEAM_COUNT,
    can_receive_support,
    can_start_late,
    is_opening,
    team_name,
)
from kvk_team.team_building.domain.team_master import EventTimeSettings
from kvk_team.team_building.domain.validation import format_clock


@dataclass(frozen=True, slots=True)
class Answer:
    """番号付きの質問の1つの対象への回答。

    `target_team`と`target_slot_start`は問いの対象の（隊、時間帯）、`late_start`は遅れて出撃させる
    隊と出撃開始時刻、応援先（FRM-041、FRM-042）。この版の回答は遅れて出撃させる案だけで、
    隊数を減らす（FRM-005）と明示して許す（FRM-046）は分割案の3と4で加える。
    """

    target_team: int
    target_slot_start: int
    late_start: LateStart

    def sort_key(self) -> tuple[object, ...]:
        """受け入れを確かめる順の鍵を返す。対象の隊の番号、時刻の順とする（作成者の仮定A-41）。"""

        return (self.target_team, self.target_slot_start, self.late_start.sort_key())

    def describe(self) -> str:
        """名前を含まない、回答を示す書き方を返す。"""

        late = self.late_start
        return (
            f"{team_name(self.target_team)} {format_clock(self.target_slot_start)}への回答"
            f"（{team_name(late.team)}を{format_clock(late.start_minutes)}から出撃）"
        )


def ordered_answers(answers: Iterable[Answer]) -> tuple[Answer, ...]:
    """同じ回答をまとめ、受け入れを確かめる順に並べて返す。"""

    return tuple(sorted(set(answers), key=Answer.sort_key))


def check_answers(
    answers: Iterable[Answer],
    members: Sequence[Member],
    specification: OperatorSpecification,
    event_time: EventTimeSettings,
) -> None:
    """ほかの指定によって変わらない誤りを、理由とともに`SpecificationError`で送出する。

    ほかの回答や最適化の結果に頼る確認（応援先が出撃中か、上限に空きがあるか、回答どうしが
    同時に成り立つか）はしない。それらはアプリケーションが受け入れを確かめるときに扱う。
    """

    source = list(members)
    partition = AvailabilityResolver(event_time).partition(source)
    confirmed = {item.member: item for item in partition.confirmed}
    leaders = resolve_leaders(specification, source)
    checker = _AnswerChecker(
        team_count=specification.team_count,
        slot_starts=frozenset(event_time.slot_starts),
        battle_start=event_time.start_minutes,
        members=source,
        confirmed=confirmed,
        leaders=leaders,
    )
    for answer in ordered_answers(answers):
        checker.check(answer)


@dataclass(frozen=True, slots=True)
class _AnswerChecker:
    """1件の回答を、参加者一覧、リーダー一覧、戦闘時間だけで確かめる。"""

    team_count: int
    slot_starts: frozenset[int]
    battle_start: int
    members: list[Member]
    confirmed: dict[Member, ResolvedAvailability]
    leaders: tuple[Member, ...]

    def check(self, answer: Answer) -> None:
        """1件の回答の誤りを送出する。"""

        where = answer.describe()
        late = answer.late_start
        self._check_team(answer.target_team, f"{where}: 対象の隊")
        if answer.target_slot_start not in self.slot_starts:
            raise SpecificationError(
                f"{where}: 対象の時刻は戦闘時間の中の{SLOT_MINUTES}分の区切りにしてください"
            )
        if not is_opening(answer.target_slot_start, self.battle_start):
            raise SpecificationError(
                f"{where}: 遅れて出撃させる回答は、序盤（戦闘開始からの1時間）の問いにだけ"
                "書けます。序盤以外の問いには、この版では回答できません（FRM-041）"
            )
        self._check_team(late.team, f"{where}: 遅れて出撃させる隊")
        if not can_start_late(late.team):
            raise SpecificationError(
                f"{where}: 第1〜{TOP_TEAM_COUNT}隊は遅れて出撃させられません（FRM-041）"
            )
        if (
            late.start_minutes not in self.slot_starts
            or late.start_minutes == self.battle_start
        ):
            raise SpecificationError(
                f"{where}: 出撃開始時刻は、戦闘開始より後で戦闘終了より前の"
                f"{SLOT_MINUTES}分の区切りにしてください"
            )
        covered: dict[Member, set[int]] = {}
        described: dict[Member, str] = {}
        same_place = Counter(
            (support.slot_start_minutes, support.team) for support in late.supports
        )
        for support in late.supports:
            # 応援は書いた順によらない並びに直して持つため、位置ではなく時刻と応援先で示す。
            support_where = (
                f"{where}の{format_clock(support.slot_start_minutes)}の"
                f"{team_name(support.team)}への応援"
            )
            count = same_place[support.slot_start_minutes, support.team]
            if count > 1:
                support_where += f"（同じ時刻と応援先の{count}件のうちの1件）"
            member = resolve_member(support.member, self.members, support_where)
            availability = self.confirmed.get(member)
            if availability is None:
                raise SpecificationError(
                    f"{support_where}のメンバーは参加時間未定のため、応援に出せません"
                )
            if member in self.leaders and self.leaders.index(member) + 1 != late.team:
                raise SpecificationError(
                    f"{support_where}のメンバーはほかの隊のリーダーのため、"
                    f"{team_name(late.team)}に所属できません"
                )
            slot = support.slot_start_minutes
            if slot not in self.slot_starts or slot >= late.start_minutes:
                raise SpecificationError(
                    f"{support_where}の時刻は、{team_name(late.team)}の出撃開始前の"
                    "時間帯にしてください"
                )
            if not availability.covers(slot, slot + SLOT_MINUTES):
                raise SpecificationError(
                    f"{support_where}のメンバーは{format_clock(slot)}に参加していません"
                )
            self._check_team(support.team, f"{support_where}: 応援先の隊")
            if not can_receive_support(support.team) or support.team == late.team:
                raise SpecificationError(
                    f"{support_where}: 応援先は第{FIRST_SUPPORTED_TEAM}隊以降の、ほかの隊に"
                    "してください（FRM-042）"
                )
            covered.setdefault(member, set()).add(slot)
            described.setdefault(member, support_where)
        for member, slots in covered.items():
            missing = self._uncovered_slots(member, slots, late)
            if missing:
                raise SpecificationError(
                    f"{described[member]}のメンバーは{format_clock(missing[0])}にも"
                    "参加しているため、その時間帯の応援先が要ります（FRM-047）"
                )
        leader = self.leaders[late.team - 1]
        if leader in self.confirmed and leader not in covered:
            missing = self._uncovered_slots(leader, set(), late)
            if missing:
                raise SpecificationError(
                    f"{where}: {team_name(late.team)}のリーダーは{format_clock(missing[0])}に"
                    "参加しているため、その時間帯の応援先が要ります（FRM-047）"
                )

    def _uncovered_slots(
        self, member: Member, covered: set[int], late: LateStart
    ) -> list[int]:
        """出撃開始前に参加しているのに応援先のない時間帯を返す。"""

        availability = self.confirmed[member]
        return sorted(
            slot
            for slot in self.slot_starts
            if slot < late.start_minutes
            and slot not in covered
            and availability.covers(slot, slot + SLOT_MINUTES)
        )

    def _check_team(self, number: int, where: str) -> None:
        """隊の番号がリーダー一覧の範囲にあるかを確かめる。"""

        if not 1 <= number <= self.team_count:
            raise SpecificationError(f"{where}は第1〜{self.team_count}隊にしてください")

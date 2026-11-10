"""所属固定の編成を、参加者一覧と運用者の指定に照らして独立に検証する。

ValidatorはOptimizerを信用せず、参加時間、リーダー、出撃を参加者一覧から計算し直す。
遅れて出撃する隊と応援は、運用者の指定と一致するかと、FRM-042の条件そのものを別に確かめる（FRM-047）。
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from kvk_team.team_building.domain.availability import (
    AvailabilityResolver,
    ResolvedAvailability,
)
from kvk_team.team_building.domain.member import MINUTES_PER_HOUR, Member
from kvk_team.team_building.domain.plan import (
    Sortie,
    TeamMembership,
    TeamPlan,
    TimeSlot,
    sorties,
)
from kvk_team.team_building.domain.rules import KvKRules
from kvk_team.team_building.domain.specification import (
    OperatorSpecification,
    SpecificationError,
    resolve_leaders,
    resolve_member,
)
from kvk_team.team_building.domain.team import (
    AT_LEAST_AS_STRONG_PAIRS,
    EXTENSION_BOUNDARY_MINUTES,
    FIRST_SUPPORTED_TEAM,
    SORTIE_FLOOR,
    STRICTLY_STRONGER_PAIRS,
    TOP_TEAM_SIZE,
    can_receive_support,
    can_start_late,
    is_top_team,
    team_name,
)


class ValidationCode(str, Enum):
    """検証結果の機械処理用識別子。"""

    DUPLICATE = "duplicate"
    UNASSIGNED = "unassigned"
    UNEXPECTED = "unexpected"
    TEAMS = "teams"
    LEADER = "leader"
    CAPACITY = "capacity"
    TOP_TEAM_SIZE = "top_team_size"
    TOP_TEAM_ALWAYS = "top_team_always"
    """上位隊のリーダー以外の所属メンバーが全時間帯に参加しない（FRM-020〜FRM-022）。"""
    VC_REQUIRED = "vc_required"
    POWER_ORDER = "power_order"
    REST = "rest"
    """延長境界時刻より前の休止（FRM-048）。下限の不足で、選択肢はIssue 3と4で示す。"""
    UNDERFILLED = "underfilled"
    LEADER_ABSENT = "leader_absent"
    LATE_START = "late_start"
    """遅れて出撃させられない隊か、出撃開始時刻が戦闘時間の区切りにない（FRM-041、FRM-047）。"""
    SUPPORT = "support"
    """応援がFRM-042の条件を満たさないか、出撃開始前の参加に応援先がない（FRM-047）。"""
    SPECIFICATION_MISMATCH = "specification_mismatch"
    """出撃開始時刻か応援先が運用者の指定と違う（FRM-047）。"""


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """隊と時間帯を特定できる検証結果1件。"""

    code: ValidationCode
    message: str
    team_number: int | None = None
    time_slot: TimeSlot | None = None


@dataclass(frozen=True, slots=True)
class SortieMetrics:
    """1つの隊の1つの時間帯の運用指標（FRM-012）。"""

    team_number: int
    time_slot: TimeSlot
    member_count: int
    """出撃人数。応援するメンバーを含む（FRM-011、FRM-042）。"""
    power: int
    vc_count: int
    leader_name: str | None
    started: bool = True
    """出撃開始以降か。出撃開始前の時間帯は人数などを算出しない（FRM-012）。"""
    support_count: int = 0
    """出撃人数のうち、応援に来たメンバーの人数。"""


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """編成のエラー、警告、出撃の指標、待機と別枠のメンバー。"""

    issues: tuple[ValidationIssue, ...]
    warnings: tuple[ValidationIssue, ...]
    sortie_metrics: tuple[SortieMetrics, ...]
    waiting: tuple[Member, ...]
    undecided: tuple[Member, ...]

    @property
    def is_valid(self) -> bool:
        """必須条件のエラーがないかを返す。"""

        return not self.issues

    @property
    def shortfalls(self) -> tuple[ValidationIssue, ...]:
        """必須条件のエラーのうち、出撃人数の下限の不足だけを返す。"""

        return tuple(
            issue for issue in self.issues if issue.code is ValidationCode.REST
        )

    @property
    def has_only_shortfalls(self) -> bool:
        """必須条件のエラーがあり、すべて下限の不足かを返す。"""

        return bool(self.issues) and len(self.shortfalls) == len(self.issues)


def format_clock(minutes: int) -> str:
    """分単位の時刻を`HH:MM`へ変換する。24時以降は24:30の形にする。"""

    hour, minute = divmod(minutes, MINUTES_PER_HOUR)
    return f"{hour:02d}:{minute:02d}"


@dataclass(slots=True)
class TeamPlanValidator:
    """所属、リーダー、上位隊、上限、休止を検証する。"""

    rules: KvKRules

    def validate(
        self,
        plan: TeamPlan,
        source_members: Sequence[Member],
        specification: OperatorSpecification,
    ) -> ValidationReport:
        """編成を参加者一覧と運用者の指定に照らして検証する。"""

        partition = AvailabilityResolver(self.rules.team_master.event_time).partition(
            list(source_members)
        )
        issues: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []
        issues.extend(
            self._validate_placement(
                plan,
                source_members,
                {item.member for item in partition.confirmed},
                set(partition.undecided),
            )
        )
        slots = self.rules.time_slots
        always_present = {
            item.member
            for item in partition.confirmed
            if all(item.covers(slot.start_minutes, slot.end_minutes) for slot in slots)
        }
        issues.extend(self._validate_teams(plan, source_members, specification))

        sortie_list = sorties(plan, partition.confirmed, self.rules.time_slots)
        leaders = {membership.number: membership.leader for membership in plan.teams}
        metrics: list[SortieMetrics] = []
        for sortie in sortie_list:
            sortie_issues, sortie_warnings = self._validate_sortie(sortie)
            issues.extend(sortie_issues)
            warnings.extend(sortie_warnings)
            leader = leaders.get(sortie.team_number)
            metrics.append(
                SortieMetrics(
                    team_number=sortie.team_number,
                    time_slot=sortie.time_slot,
                    member_count=sortie.head_count,
                    power=self._power(sortie),
                    vc_count=sum(member.has_vc for member in sortie.sortie_members),
                    leader_name=(
                        leader.name
                        if leader is not None and sortie.leader_present
                        else None
                    ),
                    started=sortie.started,
                    support_count=len(sortie.supporters),
                )
            )
        issues.extend(self._validate_top_team_membership(plan, always_present))
        issues.extend(self._validate_strength(sortie_list))
        issues.extend(self._validate_late_starts(plan))
        issues.extend(
            self._validate_against_specification(plan, source_members, specification)
        )
        confirmed = {item.member: item for item in partition.confirmed}
        issues.extend(self._validate_supports(plan, confirmed, sortie_list))
        return ValidationReport(
            issues=tuple(issues),
            warnings=tuple(warnings),
            sortie_metrics=tuple(metrics),
            waiting=plan.waiting,
            undecided=plan.undecided,
        )

    @staticmethod
    def _validate_placement(
        plan: TeamPlan,
        source_members: Sequence[Member],
        confirmed: set[Member],
        undecided: set[Member],
    ) -> list[ValidationIssue]:
        """全員がちょうど1か所に置かれ、別枠が参加時間未定のメンバーと一致するかを確かめる。"""

        placed_in_team = [
            member for membership in plan.teams for member in membership.members
        ]
        everyone = [*placed_in_team, *plan.waiting, *plan.undecided]
        issues: list[ValidationIssue] = []
        duplicates = sorted(
            member.name for member, count in Counter(everyone).items() if count > 1
        )
        if duplicates:
            issues.append(
                ValidationIssue(
                    ValidationCode.DUPLICATE, "重複した所属: " + "、".join(duplicates)
                )
            )
        unknown = sorted(member.name for member in set(everyone) - set(source_members))
        if unknown:
            issues.append(
                ValidationIssue(
                    ValidationCode.UNEXPECTED,
                    "参加者一覧にいないメンバー: " + "、".join(unknown),
                )
            )
        unassigned = sorted(
            member.name
            for member in confirmed - set(placed_in_team) - set(plan.waiting)
        )
        if unassigned:
            issues.append(
                ValidationIssue(
                    ValidationCode.UNASSIGNED,
                    "隊にも待機にもいない参加者: " + "、".join(unassigned),
                )
            )
        misplaced_undecided = sorted(
            member.name
            for member in undecided & (set(placed_in_team) | set(plan.waiting))
        )
        if misplaced_undecided:
            issues.append(
                ValidationIssue(
                    ValidationCode.UNEXPECTED,
                    "参加時間未定なのに隊か待機にいるメンバー: "
                    + "、".join(misplaced_undecided),
                )
            )
        missing_undecided = sorted(
            member.name for member in undecided - set(plan.undecided)
        )
        wrong_undecided = sorted(
            member.name for member in set(plan.undecided) - undecided
        )
        if missing_undecided:
            issues.append(
                ValidationIssue(
                    ValidationCode.UNASSIGNED,
                    "別枠にいない参加時間未定のメンバー: "
                    + "、".join(missing_undecided),
                )
            )
        if wrong_undecided:
            issues.append(
                ValidationIssue(
                    ValidationCode.UNEXPECTED,
                    "参加時間が確定しているのに別枠にいるメンバー: "
                    + "、".join(wrong_undecided),
                )
            )
        return issues

    @staticmethod
    def _validate_teams(
        plan: TeamPlan,
        source_members: Sequence[Member],
        specification: OperatorSpecification,
    ) -> list[ValidationIssue]:
        """隊の数と番号、リーダーとその所属を確かめる（FRM-001、FRM-002）。"""

        expected_numbers = tuple(range(1, specification.team_count + 1))
        actual_numbers = tuple(team.number for team in plan.teams)
        if actual_numbers != expected_numbers:
            return [
                ValidationIssue(
                    ValidationCode.TEAMS,
                    f"隊はリーダーの人数の{specification.team_count}隊を番号順に"
                    "持つ必要があります",
                )
            ]
        try:
            leaders = resolve_leaders(specification, source_members)
        except SpecificationError as error:
            return [ValidationIssue(ValidationCode.LEADER, str(error))]
        issues: list[ValidationIssue] = []
        for membership, leader in zip(plan.teams, leaders, strict=True):
            name = team_name(membership.number)
            if membership.leader != leader:
                issues.append(
                    ValidationIssue(
                        ValidationCode.LEADER,
                        f"{name}のリーダーがリーダー一覧の{membership.number}番目と違います",
                        membership.number,
                    )
                )
            elif leader not in membership.members and leader not in plan.undecided:
                issues.append(
                    ValidationIssue(
                        ValidationCode.LEADER,
                        f"{name}のリーダーが自分の隊に所属していません",
                        membership.number,
                    )
                )
        return issues

    def _validate_sortie(
        self,
        sortie: Sortie,
    ) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
        """1つの出撃の人数と休止を確かめる。"""

        issues: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []
        if not sortie.started:
            return issues, warnings
        number = sortie.team_number
        name = team_name(number)
        count = sortie.head_count
        slot = sortie.time_slot
        if is_top_team(number):
            expected = TOP_TEAM_SIZE if sortie.leader_present else TOP_TEAM_SIZE - 1
            if count != expected:
                issues.append(
                    ValidationIssue(
                        ValidationCode.TOP_TEAM_SIZE,
                        f"{name}は{expected}人で出撃する必要があります: {count}人",
                        number,
                        slot,
                    )
                )
            elif not sortie.leader_present:
                warnings.append(
                    ValidationIssue(
                        ValidationCode.LEADER_ABSENT,
                        f"{name}はリーダー不在のため{count}人で出撃します",
                        number,
                        slot,
                    )
                )
            return issues, warnings

        if count > self.rules.member_cap:
            issues.append(
                ValidationIssue(
                    ValidationCode.CAPACITY,
                    f"{name}が上限の{self.rules.member_cap}人を超えています: {count}人",
                    number,
                    slot,
                )
            )
        if not sortie.members:
            # 休止は所属メンバーの参加で判定し、応援を含めない（FRM-048）。休止中の隊を
            # 応援先にした編成は、応援の確認で拒否する。
            rest = ValidationIssue(
                ValidationCode.REST,
                f"{name}は所属メンバーが参加しておらず休止になります",
                number,
                slot,
            )
            if slot.start_minutes < EXTENSION_BOUNDARY_MINUTES:
                issues.append(rest)
            else:
                warnings.append(rest)
            return issues, warnings
        if count < SORTIE_FLOOR:
            warnings.append(
                ValidationIssue(
                    ValidationCode.UNDERFILLED,
                    f"{name}が{SORTIE_FLOOR}人未満です: {count}人",
                    number,
                    slot,
                )
            )
        if not sortie.leader_present:
            warnings.append(
                ValidationIssue(
                    ValidationCode.LEADER_ABSENT,
                    f"{name}はリーダー不在です",
                    number,
                    slot,
                )
            )
        return issues, warnings

    @staticmethod
    def _validate_top_team_membership(
        plan: TeamPlan,
        always_present: set[Member],
    ) -> list[ValidationIssue]:
        """上位隊の所属人数、常時稼働、VCを確かめる（FRM-020〜FRM-022）。

        所属はリーダーを含めて8人（別枠のリーダーの隊は7人）とし、リーダー以外は全時間帯に
        参加する人に限る。時間帯ごとの人数だけでは、途中で抜ける人と途中から来る人の
        入れ替わりを見逃すため、所属そのものを確かめる。
        """

        issues: list[ValidationIssue] = []
        for membership in plan.teams:
            if not is_top_team(membership.number):
                continue
            name = team_name(membership.number)
            expected = (
                TOP_TEAM_SIZE if membership.leader_is_member else TOP_TEAM_SIZE - 1
            )
            if len(membership.members) != expected:
                issues.append(
                    ValidationIssue(
                        ValidationCode.TOP_TEAM_SIZE,
                        f"{name}の所属は{expected}人にする必要があります: "
                        f"{len(membership.members)}人",
                        membership.number,
                    )
                )
            not_always = [
                member.name
                for member in membership.members
                if member != membership.leader and member not in always_present
            ]
            if not_always:
                issues.append(
                    ValidationIssue(
                        ValidationCode.TOP_TEAM_ALWAYS,
                        f"{name}に全時間帯に参加しないメンバーがいます: "
                        + "、".join(not_always),
                        membership.number,
                    )
                )
            non_vc = [member.name for member in membership.members if not member.has_vc]
            if non_vc:
                issues.append(
                    ValidationIssue(
                        ValidationCode.VC_REQUIRED,
                        f"{name}のVC不可メンバー: " + "、".join(non_vc),
                        membership.number,
                    )
                )
        return issues

    def _power(self, sortie: Sortie) -> int:
        """出撃メンバーのTier戦力の合計を返す。"""

        return sum(
            self.rules.tier_power[member.tier] for member in sortie.sortie_members
        )

    def _validate_late_starts(self, plan: TeamPlan) -> list[ValidationIssue]:
        """遅れて出撃する隊と出撃開始時刻がFRM-041、FRM-047の条件を満たすかを確かめる。

        運用者の指定なしに遅れて出撃してよいFIXの隊（FRM-048）は、FIXの指定（分割案の5）で加える。
        """

        event = self.rules.team_master.event_time
        slot_starts = {slot.start_minutes for slot in self.rules.time_slots}
        issues: list[ValidationIssue] = []
        for membership in plan.teams:
            start = membership.start_minutes
            if start is None:
                continue
            name = team_name(membership.number)
            if not can_start_late(membership.number):
                issues.append(
                    ValidationIssue(
                        ValidationCode.LATE_START,
                        f"{name}は遅れて出撃させられません（FRM-041）",
                        membership.number,
                    )
                )
            if start not in slot_starts or start == event.start_minutes:
                issues.append(
                    ValidationIssue(
                        ValidationCode.LATE_START,
                        f"{name}の出撃開始時刻{format_clock(start)}は、戦闘開始より後で"
                        "戦闘終了より前の時間帯の区切りにしてください",
                        membership.number,
                    )
                )
        return issues

    @staticmethod
    def _validate_against_specification(
        plan: TeamPlan,
        source_members: Sequence[Member],
        specification: OperatorSpecification,
    ) -> list[ValidationIssue]:
        """出撃開始時刻と応援先が運用者の指定と一致するかを確かめる（FRM-047）。"""

        issues: list[ValidationIssue] = []
        for membership in plan.teams:
            late = specification.late_start(membership.number)
            expected = None if late is None else late.start_minutes
            if membership.start_minutes != expected:
                issues.append(
                    ValidationIssue(
                        ValidationCode.SPECIFICATION_MISMATCH,
                        f"{team_name(membership.number)}の出撃開始時刻が"
                        "運用者の指定と違います",
                        membership.number,
                    )
                )
        # 応援するメンバーは、指定した遅れて出撃する隊に所属する（作成者の仮定A-16）。
        # このため（メンバー、時刻、応援先）に加え、所属する隊も指定と比べる。
        try:
            expected_supports = {
                (
                    resolve_member(
                        ref.member,
                        source_members,
                        f"{team_name(late.team)}の"
                        f"{format_clock(ref.slot_start_minutes)}の"
                        f"{team_name(ref.team)}への応援",
                    ),
                    ref.slot_start_minutes,
                    ref.team,
                    late.team,
                )
                for late in specification.late_starts
                for ref in late.supports
            }
        except SpecificationError as error:
            issues.append(
                ValidationIssue(ValidationCode.SPECIFICATION_MISMATCH, str(error))
            )
            return issues
        team_of = {
            member: membership.number
            for membership in plan.teams
            for member in membership.members
        }
        actual_supports = {
            (
                support.member,
                support.time_slot.start_minutes,
                support.team_number,
                team_of.get(support.member),
            )
            for support in plan.supports
        }
        if actual_supports != expected_supports:
            issues.append(
                ValidationIssue(
                    ValidationCode.SPECIFICATION_MISMATCH,
                    "応援が運用者の指定と違います",
                )
            )
        return issues

    def _validate_supports(
        self,
        plan: TeamPlan,
        confirmed: dict[Member, ResolvedAvailability],
        sortie_list: Sequence[Sortie],
    ) -> list[ValidationIssue]:
        """応援がFRM-042の条件を満たし、出撃開始前の参加に応援先があるかを確かめる（FRM-047）。

        応援先の上限は、応援を含めた出撃人数として`_validate_sortie`で確かめる。
        """

        issues: list[ValidationIssue] = []
        team_of = {
            member: membership
            for membership in plan.teams
            for member in membership.members
        }
        memberships = {membership.number: membership for membership in plan.teams}
        sortie_by_key = {
            (sortie.team_number, sortie.time_slot): sortie for sortie in sortie_list
        }
        repeated = Counter(
            (support.member, support.time_slot) for support in plan.supports
        )
        for (member, slot), count in repeated.items():
            if count > 1:
                issues.append(
                    ValidationIssue(
                        ValidationCode.SUPPORT,
                        f"{member.name}に同じ時間帯の応援先が2つ以上あります",
                        time_slot=slot,
                    )
                )
        slots = set(self.rules.time_slots)
        for support in plan.supports:
            if support.time_slot not in slots:
                issues.append(
                    ValidationIssue(
                        ValidationCode.SUPPORT,
                        f"{support.member.name}の応援の時間帯が、戦闘時間の時間帯の区切りに"
                        "ありません",
                        support.team_number,
                    )
                )
                continue
            issues.extend(
                _SupportCheck(memberships, confirmed, sortie_by_key).check(
                    support.member,
                    support.time_slot,
                    support.team_number,
                    team_of.get(support.member),
                )
            )
        supported = {(support.member, support.time_slot) for support in plan.supports}
        for membership in plan.teams:
            if membership.start_minutes is None:
                continue
            for member in membership.members:
                availability = confirmed.get(member)
                if availability is None:
                    continue
                for slot in self.rules.time_slots:
                    if (
                        not membership.has_started(slot)
                        and availability.covers(slot.start_minutes, slot.end_minutes)
                        and (member, slot) not in supported
                    ):
                        issues.append(
                            ValidationIssue(
                                ValidationCode.SUPPORT,
                                f"{team_name(membership.number)}の{member.name}は"
                                "出撃開始前に参加しているため、応援先が要ります",
                                membership.number,
                                slot,
                            )
                        )
        return issues

    def _validate_strength(
        self,
        sortie_list: Sequence[Sortie],
    ) -> list[ValidationIssue]:
        """上位隊の戦力関係を時間帯ごとに確かめる。"""

        power = {
            (sortie.team_number, sortie.time_slot): self._power(sortie)
            for sortie in sortie_list
        }
        slots = sorted(
            {sortie.time_slot for sortie in sortie_list},
            key=lambda slot: slot.start_minutes,
        )
        relations = [
            *((pair, ">") for pair in STRICTLY_STRONGER_PAIRS),
            *((pair, ">=") for pair in AT_LEAST_AS_STRONG_PAIRS),
        ]
        issues: list[ValidationIssue] = []
        for slot in slots:
            for (stronger, weaker), operator in relations:
                if (stronger, slot) not in power or (weaker, slot) not in power:
                    continue
                left = power[stronger, slot]
                right = power[weaker, slot]
                valid = left > right if operator == ">" else left >= right
                if not valid:
                    issues.append(
                        ValidationIssue(
                            ValidationCode.POWER_ORDER,
                            f"{team_name(stronger)}:{left} {operator} "
                            f"{team_name(weaker)}:{right}を満たしていません",
                            time_slot=slot,
                        )
                    )
        return issues


@dataclass(frozen=True, slots=True)
class _SupportCheck:
    """1件の応援がFRM-042の条件を満たすかを確かめる。"""

    memberships: dict[int, TeamMembership]
    confirmed: dict[Member, ResolvedAvailability]
    sortie_by_key: dict[tuple[int, TimeSlot], Sortie]

    def check(
        self,
        member: Member,
        slot: TimeSlot,
        target: int,
        source: TeamMembership | None,
    ) -> list[ValidationIssue]:
        """応援する人、時間帯、応援先を確かめる。"""

        issues: list[ValidationIssue] = []
        if source is None or source.has_started(slot):
            issues.append(
                ValidationIssue(
                    ValidationCode.SUPPORT,
                    f"{member.name}の応援は、遅れて出撃する隊の出撃開始前の"
                    "所属メンバーによるものではありません",
                    time_slot=slot,
                )
            )
        availability = self.confirmed.get(member)
        if availability is None or not availability.covers(
            slot.start_minutes, slot.end_minutes
        ):
            issues.append(
                ValidationIssue(
                    ValidationCode.SUPPORT,
                    f"{member.name}はこの時間帯に参加していないため応援できません",
                    time_slot=slot,
                )
            )
        destination = self.memberships.get(target)
        if (
            destination is None
            or not can_receive_support(target)
            or (source is not None and source.number == target)
        ):
            issues.append(
                ValidationIssue(
                    ValidationCode.SUPPORT,
                    f"{member.name}の応援先は第{FIRST_SUPPORTED_TEAM}隊以降の、"
                    "ほかの隊にしてください（FRM-042）",
                    time_slot=slot,
                )
            )
            return issues
        if not destination.has_started(slot):
            issues.append(
                ValidationIssue(
                    ValidationCode.SUPPORT,
                    f"応援先の{team_name(target)}は出撃開始前です",
                    target,
                    slot,
                )
            )
        elif not self.sortie_by_key[target, slot].members:
            issues.append(
                ValidationIssue(
                    ValidationCode.SUPPORT,
                    f"応援先の{team_name(target)}は休止中です（FRM-048）",
                    target,
                    slot,
                )
            )
        return issues


@dataclass(frozen=True, slots=True)
class ValidatedTeamPlan:
    """必須条件を満たすと検証した、出力可能な編成。

    必須条件エラーを含む検証結果からは生成できない。Exporterはこの型だけを受け取り、
    未検証の編成候補を誤って出力できないようにする。

    型が保証するのは「検証結果に必須条件エラーがない」ことだけで、検証結果が同じ編成のもので
    あることは保証しない。生成は`BuildTeamPlan`がValidatorの結果から行い、ほかの経路で作らない。
    """

    plan: TeamPlan
    report: ValidationReport
    proven_optimal: bool
    """探索の制限内に最適な編成だと示せたか。FRM-049の警告に使う（Issue 3）。

    既定値を持たせない。最適性を知らない経路が省略して「示せた」と主張しないようにする。
    """
    notes: tuple[str, ...] = ()
    """運用者への注記（OUT-007）。使わなかった回答、受け入れなかった回答を示す（FRM-090の性質(3)）。"""

    def __post_init__(self) -> None:
        """必須条件エラーを含む検証結果を拒否する。"""

        if not self.report.is_valid:
            messages = "; ".join(issue.message for issue in self.report.issues)
            raise ValueError(
                f"必須条件を満たさない編成は検証済みにできません: {messages}"
            )

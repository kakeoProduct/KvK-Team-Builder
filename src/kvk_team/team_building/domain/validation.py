"""時間帯別チーム編成を入力参加者とJSONマスタに照らして検証する。"""

from collections import Counter
from dataclasses import dataclass
from enum import Enum

from kvk_team.team_building.domain.availability import AvailabilityResolver
from kvk_team.team_building.domain.member import Member
from kvk_team.team_building.domain.rules import KvKRules
from kvk_team.team_building.domain.schedule import DynamicTeamPlan, TimeSlot
from kvk_team.team_building.domain.team import TeamLabel
from kvk_team.team_building.domain.team_master import (
    StrengthOperator,
    TeamDefinition,
)


class DynamicValidationCode(str, Enum):
    """時間帯別検証エラーの機械処理用識別子。"""

    DUPLICATE = "duplicate"
    UNASSIGNED = "unassigned"
    UNEXPECTED = "unexpected"
    CAPACITY = "capacity"
    UNDERFILLED = "underfilled"
    VC_REQUIRED = "vc_required"
    RALLY_LEADER = "rally_leader"
    POWER_ORDER = "power_order"


@dataclass(frozen=True, slots=True)
class DynamicValidationIssue:
    """時間・チームを特定できる検証結果1件。"""

    code: DynamicValidationCode
    message: str
    team_label: TeamLabel | None = None
    time_slot: TimeSlot | None = None


@dataclass(frozen=True, slots=True)
class DynamicSlotMetrics:
    """1チーム・1時間帯の運用指標。"""

    team_label: TeamLabel
    time_slot: TimeSlot
    member_count: int
    power: int
    vc_count: int
    leader_name: str | None


@dataclass(frozen=True, slots=True)
class DynamicValidationReport:
    """時間帯別編成のエラー、警告、指標、待機メンバー。"""

    issues: tuple[DynamicValidationIssue, ...]
    warnings: tuple[DynamicValidationIssue, ...]
    slot_metrics: tuple[DynamicSlotMetrics, ...]
    standby_members: tuple[Member, ...]

    @property
    def is_valid(self) -> bool:
        """必須条件のエラーがないかを返す。"""

        return not self.issues


@dataclass(slots=True)
class DynamicTeamValidator:
    """全時間帯の重複、人数、VC、集結主、戦力を検証する。"""

    rules: KvKRules

    def validate(
        self,
        plan: DynamicTeamPlan,
        source_members: list[Member],
    ) -> DynamicValidationReport:
        """動的編成を入力参加者およびチームマスタと照合する。"""

        master = self.rules.team_master
        partition = AvailabilityResolver(master.event_time).partition(source_members)
        confirmed_by_name = {
            availability.member.name: availability
            for availability in partition.confirmed
        }
        issues: list[DynamicValidationIssue] = []
        warnings: list[DynamicValidationIssue] = []
        metrics: list[DynamicSlotMetrics] = []

        for slot_start in master.event_time.slot_starts:
            slot = TimeSlot(slot_start, slot_start + master.event_time.slot_minutes)
            assignments = {
                label: plan.assignment_at(label, slot_start)
                for label in master.team_labels
            }
            active_names = {
                name
                for name, availability in confirmed_by_name.items()
                if availability.covers(slot.start_minutes, slot.end_minutes)
            }
            assigned_names = [
                member.name
                for assignment in assignments.values()
                for member in assignment.members
            ]
            issues.extend(
                self._validate_assignment_integrity(
                    slot,
                    active_names,
                    assigned_names,
                )
            )

            metrics_by_label: dict[TeamLabel, DynamicSlotMetrics] = {}
            for label, assignment in assignments.items():
                definition = master.teams_by_label[label]
                team_issues, team_warnings = self._validate_team(
                    assignment.members,
                    definition,
                    active_names,
                    slot,
                )
                issues.extend(team_issues)
                warnings.extend(team_warnings)
                leader_name = self._active_leader_name(definition, active_names)
                metric = DynamicSlotMetrics(
                    team_label=label,
                    time_slot=slot,
                    member_count=len(assignment.members),
                    power=sum(
                        self.rules.tier_power[member.tier]
                        for member in assignment.members
                    ),
                    vc_count=sum(member.has_vc for member in assignment.members),
                    leader_name=leader_name,
                )
                metrics.append(metric)
                metrics_by_label[label] = metric
            issues.extend(self._validate_strength(metrics_by_label, slot))

        return DynamicValidationReport(
            issues=tuple(issues),
            warnings=tuple(warnings),
            slot_metrics=tuple(metrics),
            standby_members=partition.standby,
        )

    @staticmethod
    def _validate_assignment_integrity(
        slot: TimeSlot,
        active_names: set[str],
        assigned_names: list[str],
    ) -> list[DynamicValidationIssue]:
        """1時間帯の重複、未配置、参加時間外配置を検出する。"""

        issues: list[DynamicValidationIssue] = []
        counts = Counter(assigned_names)
        duplicates = sorted(name for name, count in counts.items() if count > 1)
        if duplicates:
            issues.append(
                DynamicValidationIssue(
                    DynamicValidationCode.DUPLICATE,
                    "重複配置: " + ", ".join(duplicates),
                    time_slot=slot,
                )
            )
        unassigned = sorted(active_names - set(assigned_names))
        if unassigned:
            issues.append(
                DynamicValidationIssue(
                    DynamicValidationCode.UNASSIGNED,
                    "確定参加者の未配置: " + ", ".join(unassigned),
                    time_slot=slot,
                )
            )
        unexpected = sorted(set(assigned_names) - active_names)
        if unexpected:
            issues.append(
                DynamicValidationIssue(
                    DynamicValidationCode.UNEXPECTED,
                    "参加時間外の配置: " + ", ".join(unexpected),
                    time_slot=slot,
                )
            )
        return issues

    def _validate_team(
        self,
        members: tuple[Member, ...],
        definition: TeamDefinition,
        active_names: set[str],
        slot: TimeSlot,
    ) -> tuple[list[DynamicValidationIssue], list[DynamicValidationIssue]]:
        """1チームの人数、VC、集結主または代理を検証する。"""

        issues: list[DynamicValidationIssue] = []
        warnings: list[DynamicValidationIssue] = []
        count = len(members)
        if count > definition.maximum_members:
            issues.append(
                DynamicValidationIssue(
                    DynamicValidationCode.CAPACITY,
                    f"{definition.label.value}が最大人数を超えています: {count}人",
                    definition.label,
                    slot,
                )
            )
        if definition.minimum_members == definition.maximum_members:
            if count != definition.minimum_members:
                issues.append(
                    DynamicValidationIssue(
                        DynamicValidationCode.CAPACITY,
                        f"{definition.label.value}は{definition.minimum_members}人固定です",
                        definition.label,
                        slot,
                    )
                )
        elif count < definition.minimum_members:
            warnings.append(
                DynamicValidationIssue(
                    DynamicValidationCode.UNDERFILLED,
                    f"{definition.label.value}が"
                    f"{definition.minimum_members}人未満です: {count}人",
                    definition.label,
                    slot,
                )
            )
        if definition.vc_required:
            non_vc = [member.name for member in members if not member.has_vc]
            if non_vc:
                issues.append(
                    DynamicValidationIssue(
                        DynamicValidationCode.VC_REQUIRED,
                        "VC不可メンバー: " + ", ".join(non_vc),
                        definition.label,
                        slot,
                    )
                )

        expected_leader = self._active_leader_name(definition, active_names)
        if expected_leader is None:
            warnings.append(
                DynamicValidationIssue(
                    DynamicValidationCode.RALLY_LEADER,
                    f"{definition.label.value}は集結主の到着待ちです",
                    definition.label,
                    slot,
                )
            )
        elif expected_leader not in {member.name for member in members}:
            issues.append(
                DynamicValidationIssue(
                    DynamicValidationCode.RALLY_LEADER,
                    f"{definition.label.value}に集結主{expected_leader}がいません",
                    definition.label,
                    slot,
                )
            )
        return issues, warnings

    @staticmethod
    def _active_leader_name(
        definition: TeamDefinition,
        active_names: set[str],
    ) -> str | None:
        """参加中の固定集結主、または先頭の代理集結主を返す。"""

        if definition.rally_leader in active_names:
            return definition.rally_leader
        return next(
            (name for name in definition.substitute_leaders if name in active_names),
            None,
        )

    def _validate_strength(
        self,
        metrics: dict[TeamLabel, DynamicSlotMetrics],
        slot: TimeSlot,
    ) -> list[DynamicValidationIssue]:
        """JSONマスタの戦力関係を1時間帯について検証する。"""

        issues: list[DynamicValidationIssue] = []
        for relation in self.rules.team_master.strength_relations:
            stronger = metrics[relation.stronger].power
            weaker = metrics[relation.weaker].power
            valid = (
                stronger > weaker
                if relation.operator is StrengthOperator.GREATER_THAN
                else stronger >= weaker
            )
            if not valid:
                issues.append(
                    DynamicValidationIssue(
                        DynamicValidationCode.POWER_ORDER,
                        f"{relation.stronger.value}:{stronger} "
                        f"{relation.operator.value} "
                        f"{relation.weaker.value}:{weaker}を満たしていません",
                        time_slot=slot,
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

    plan: DynamicTeamPlan
    report: DynamicValidationReport

    def __post_init__(self) -> None:
        """必須条件エラーを含む検証結果を拒否する。"""

        if not self.report.is_valid:
            messages = "; ".join(issue.message for issue in self.report.issues)
            raise ValueError(
                f"必須条件を満たさない編成は検証済みにできません: {messages}"
            )

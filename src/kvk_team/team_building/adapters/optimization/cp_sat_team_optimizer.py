"""時間スロットごとの動的チーム編成を行うCP-SAT Optimizer。"""

from collections import Counter
from dataclasses import dataclass

from ortools.sat.python import cp_model

from kvk_team.team_building.adapters.optimization.errors import (
    InfeasibleRosterError,
    OptimizationError,
    OptimizationTimeoutError,
)
from kvk_team.team_building.domain.availability import (
    AvailabilityResolver,
    ResolvedAvailability,
)
from kvk_team.team_building.domain.member import Member
from kvk_team.team_building.domain.rules import KvKRules
from kvk_team.team_building.domain.schedule import (
    DynamicTeamPlan,
    SlotAssignment,
    TimeSlot,
)
from kvk_team.team_building.domain.team_master import (
    StrengthOperator,
    TeamDefinition,
)

AssignmentKey = tuple[int, int, int]


@dataclass(slots=True)
class TimeSlotTeamOptimizer:
    """参加可能時間ごとに配置し、交代回数を最小化する。"""

    rules: KvKRules

    def optimize(self, members: list[Member]) -> DynamicTeamPlan:
        """確定参加者の動的配置と時間未定者の待機一覧を返す。"""

        self._validate_members(members)
        master = self.rules.team_master
        partition = AvailabilityResolver(master.event_time).partition(members)
        slots = tuple(
            TimeSlot(start, start + master.event_time.slot_minutes)
            for start in master.event_time.slot_starts
        )
        active_indexes = self._active_member_indexes(partition.confirmed, slots)
        self._validate_priority_vc_supply(partition.confirmed, slots, active_indexes)

        model = cp_model.CpModel()
        assignments = self._create_assignment_variables(
            model,
            partition.confirmed,
            slots,
            active_indexes,
        )
        team_counts = self._add_assignment_and_capacity_constraints(
            model,
            partition.confirmed,
            slots,
            active_indexes,
            assignments,
        )
        team_power = self._add_vc_leader_and_power_constraints(
            model,
            partition.confirmed,
            slots,
            active_indexes,
            assignments,
        )
        objective = self._build_objective(
            model,
            partition.confirmed,
            slots,
            active_indexes,
            assignments,
            team_counts,
            team_power,
        )
        model.maximize(objective)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.rules.maximum_optimization_seconds
        if self.rules.maximum_deterministic_time is not None:
            solver.parameters.max_deterministic_time = (
                self.rules.maximum_deterministic_time
            )
        solver.parameters.num_search_workers = self.rules.solver_worker_count
        solver.parameters.random_seed = self.rules.solver_random_seed
        status = solver.solve(model)
        self._raise_for_unsolved_status(status)
        return self._extract_plan(
            solver,
            partition.confirmed,
            partition.standby,
            slots,
            active_indexes,
            assignments,
        )

    def _raise_for_unsolved_status(self, status: int) -> None:
        """解なし、時間切れ、モデル不正を区別して利用者向けの例外へ変換する。"""

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return
        if status == cp_model.INFEASIBLE:
            raise InfeasibleRosterError(
                "全時間帯の必須条件を満たす編成は存在しません。"
                "参加者、VC、参加時間、チーム人数を見直してください"
            )
        if status == cp_model.UNKNOWN:
            limit = f"{self.rules.maximum_optimization_seconds:g}秒"
            if self.rules.maximum_deterministic_time is not None:
                limit += f"、決定的時間{self.rules.maximum_deterministic_time:g}"
            raise OptimizationTimeoutError(
                f"制限時間（{limit}）内に必須条件を満たす編成が見つかりませんでした。"
                "時間切れのため、編成が存在しないとは確定していません。"
                "負荷の低い環境で再実行するか、制限時間を延ばしてください"
            )
        raise OptimizationError(
            f"最適化モデルを解けませんでした（CP-SAT status: {status}）"
        )

    @staticmethod
    def _validate_members(members: list[Member]) -> None:
        """時間帯別モデル作成前に名前の重複を拒否する。"""

        duplicates = sorted(
            name
            for name, count in Counter(member.name for member in members).items()
            if count > 1
        )
        if duplicates:
            raise OptimizationError(
                "参加者名が重複しています: " + ", ".join(duplicates)
            )

    @staticmethod
    def _active_member_indexes(
        members: tuple[ResolvedAvailability, ...],
        slots: tuple[TimeSlot, ...],
    ) -> dict[int, tuple[int, ...]]:
        """各時間スロットへ完全参加できるメンバーのIndexを返す。"""

        return {
            slot_index: tuple(
                member_index
                for member_index, availability in enumerate(members)
                if availability.covers(slot.start_minutes, slot.end_minutes)
            )
            for slot_index, slot in enumerate(slots)
        }

    def _validate_priority_vc_supply(
        self,
        members: tuple[ResolvedAvailability, ...],
        slots: tuple[TimeSlot, ...],
        active_indexes: dict[int, tuple[int, ...]],
    ) -> None:
        """A〜Cの固定人数を満たすVC参加者数を時間帯ごとに確認する。"""

        required_vc = sum(
            self.rules.team_master.teams_by_label[label].minimum_members
            for label in self.rules.team_master.vc_required_teams
        )
        for slot_index, slot in enumerate(slots):
            actual_vc = sum(
                members[index].member.has_vc for index in active_indexes[slot_index]
            )
            if actual_vc < required_vc:
                raise OptimizationError(
                    f"{slot.start_minutes // 60:02d}:"
                    f"{slot.start_minutes % 60:02d}のVC参加者が不足しています: "
                    f"{actual_vc}人（必要: {required_vc}人）"
                )

    def _create_assignment_variables(
        self,
        model: cp_model.CpModel,
        members: tuple[ResolvedAvailability, ...],
        slots: tuple[TimeSlot, ...],
        active_indexes: dict[int, tuple[int, ...]],
    ) -> dict[AssignmentKey, cp_model.IntVar]:
        """参加可能なメンバー・チーム・時間の組だけBool変数を生成する。"""

        labels = self.rules.team_master.team_labels
        return {
            (member_index, team_index, slot_index): model.new_bool_var(
                f"m_{member_index}_t_{label.value}_s_{slot_index}"
            )
            for slot_index in range(len(slots))
            for member_index in active_indexes[slot_index]
            for team_index, label in enumerate(labels)
        }

    def _add_assignment_and_capacity_constraints(
        self,
        model: cp_model.CpModel,
        members: tuple[ResolvedAvailability, ...],
        slots: tuple[TimeSlot, ...],
        active_indexes: dict[int, tuple[int, ...]],
        assignments: dict[AssignmentKey, cp_model.IntVar],
    ) -> dict[tuple[int, int], cp_model.IntVar]:
        """重複禁止とチーム別の時間帯人数上限を追加する。"""

        labels = self.rules.team_master.team_labels
        team_counts: dict[tuple[int, int], cp_model.IntVar] = {}
        for slot_index in range(len(slots)):
            for member_index in active_indexes[slot_index]:
                model.add_exactly_one(
                    assignments[member_index, team_index, slot_index]
                    for team_index in range(len(labels))
                )

            for team_index, label in enumerate(labels):
                definition = self.rules.team_master.teams_by_label[label]
                count = model.new_int_var(
                    0,
                    definition.maximum_members,
                    f"count_{label.value}_{slot_index}",
                )
                model.add(
                    count
                    == sum(
                        assignments[member_index, team_index, slot_index]
                        for member_index in active_indexes[slot_index]
                    )
                )
                model.add(count <= definition.maximum_members)
                if definition.minimum_members == definition.maximum_members:
                    model.add(count == definition.minimum_members)
                team_counts[team_index, slot_index] = count
        return team_counts

    def _add_vc_leader_and_power_constraints(
        self,
        model: cp_model.CpModel,
        members: tuple[ResolvedAvailability, ...],
        slots: tuple[TimeSlot, ...],
        active_indexes: dict[int, tuple[int, ...]],
        assignments: dict[AssignmentKey, cp_model.IntVar],
    ) -> dict[tuple[int, int], cp_model.IntVar]:
        """VC、集結主、代理集結主、時間帯別戦力関係を追加する。"""

        labels = self.rules.team_master.team_labels
        maximum_power = max(
            definition.maximum_members for definition in self.rules.team_master.teams
        ) * max(self.rules.tier_power.values())
        team_power: dict[tuple[int, int], cp_model.IntVar] = {}
        for slot_index in range(len(slots)):
            active_by_name = {
                members[index].member.name: index
                for index in active_indexes[slot_index]
            }
            for team_index, label in enumerate(labels):
                definition = self.rules.team_master.teams_by_label[label]
                if definition.vc_required:
                    for member_index in active_indexes[slot_index]:
                        if not members[member_index].member.has_vc:
                            model.add(
                                assignments[member_index, team_index, slot_index] == 0
                            )
                self._fix_available_leader(
                    model,
                    definition,
                    active_by_name,
                    team_index,
                    slot_index,
                    assignments,
                )
                power = model.new_int_var(
                    0,
                    maximum_power,
                    f"power_{label.value}_{slot_index}",
                )
                model.add(
                    power
                    == sum(
                        assignments[member_index, team_index, slot_index]
                        * self.rules.tier_power[members[member_index].member.tier]
                        for member_index in active_indexes[slot_index]
                    )
                )
                team_power[team_index, slot_index] = power

            for relation in self.rules.team_master.strength_relations:
                stronger_index = labels.index(relation.stronger)
                weaker_index = labels.index(relation.weaker)
                stronger = team_power[stronger_index, slot_index]
                weaker = team_power[weaker_index, slot_index]
                if relation.operator is StrengthOperator.GREATER_THAN:
                    model.add(stronger > weaker)
                else:
                    model.add(stronger >= weaker)
        return team_power

    @staticmethod
    def _fix_available_leader(
        model: cp_model.CpModel,
        definition: TeamDefinition,
        active_by_name: dict[str, int],
        team_index: int,
        slot_index: int,
        assignments: dict[AssignmentKey, cp_model.IntVar],
    ) -> None:
        """固定集結主を優先し、不在時は最初の参加可能な代理を固定する。"""

        leader_index = active_by_name.get(definition.rally_leader)
        if leader_index is not None:
            model.add(assignments[leader_index, team_index, slot_index] == 1)
            return
        for substitute in definition.substitute_leaders:
            substitute_index = active_by_name.get(substitute)
            if substitute_index is not None:
                model.add(assignments[substitute_index, team_index, slot_index] == 1)
                return

    def _build_objective(
        self,
        model: cp_model.CpModel,
        members: tuple[ResolvedAvailability, ...],
        slots: tuple[TimeSlot, ...],
        active_indexes: dict[int, tuple[int, ...]],
        assignments: dict[AssignmentKey, cp_model.IntVar],
        team_counts: dict[tuple[int, int], cp_model.IntVar],
        team_power: dict[tuple[int, int], cp_model.IntVar],
    ) -> cp_model.LinearExpr:
        """不足、9人目、チーム移動を抑えつつ優先戦力を高める。"""

        weights = self.rules.objective_weights
        labels = self.rules.team_master.team_labels
        underfilled: list[cp_model.IntVar] = []
        ninth_members: list[cp_model.IntVar] = []
        for team_index, label in enumerate(labels):
            definition = self.rules.team_master.teams_by_label[label]
            for slot_index in range(len(slots)):
                count = team_counts[team_index, slot_index]
                shortage = model.new_int_var(
                    0,
                    definition.minimum_members,
                    f"shortage_{label.value}_{slot_index}",
                )
                model.add(shortage >= definition.minimum_members - count)
                underfilled.append(shortage)
                if definition.maximum_members > definition.minimum_members:
                    extra = model.new_int_var(
                        0,
                        definition.maximum_members - definition.minimum_members,
                        f"extra_{label.value}_{slot_index}",
                    )
                    model.add(extra >= count - definition.minimum_members)
                    ninth_members.append(extra)

        changes = self._team_change_variables(
            model,
            members,
            slots,
            active_indexes,
            assignments,
        )
        priority_indexes = [
            labels.index(label) for label in self.rules.team_master.vc_required_teams
        ]
        priority_power = sum(
            team_power[team_index, slot_index]
            * (len(priority_indexes) - priority_indexes.index(team_index))
            for team_index in priority_indexes
            for slot_index in range(len(slots))
        )
        return (
            weights.priority_power * priority_power
            - weights.underfilled_team * sum(underfilled)
            - weights.member_team_change * sum(changes)
            - weights.ninth_member * sum(ninth_members)
        )

    def _team_change_variables(
        self,
        model: cp_model.CpModel,
        members: tuple[ResolvedAvailability, ...],
        slots: tuple[TimeSlot, ...],
        active_indexes: dict[int, tuple[int, ...]],
        assignments: dict[AssignmentKey, cp_model.IntVar],
    ) -> list[cp_model.IntVar]:
        """連続参加中に所属チームが変わったかを表す変数を生成する。"""

        labels = self.rules.team_master.team_labels
        changes: list[cp_model.IntVar] = []
        for member_index in range(len(members)):
            for slot_index in range(1, len(slots)):
                if (
                    member_index not in active_indexes[slot_index - 1]
                    or member_index not in active_indexes[slot_index]
                ):
                    continue
                changed = model.new_bool_var(f"changed_{member_index}_{slot_index}")
                for team_index in range(len(labels)):
                    previous = assignments[member_index, team_index, slot_index - 1]
                    current = assignments[member_index, team_index, slot_index]
                    model.add(previous - current <= changed)
                    model.add(current - previous <= changed)
                changes.append(changed)
        return changes

    def _extract_plan(
        self,
        solver: cp_model.CpSolver,
        members: tuple[ResolvedAvailability, ...],
        standby: tuple[Member, ...],
        slots: tuple[TimeSlot, ...],
        active_indexes: dict[int, tuple[int, ...]],
        assignments: dict[AssignmentKey, cp_model.IntVar],
    ) -> DynamicTeamPlan:
        """Solverの値を時間帯別の不変ドメインモデルへ変換する。"""

        labels = self.rules.team_master.team_labels
        slot_assignments: list[SlotAssignment] = []
        for team_index, label in enumerate(labels):
            definition = self.rules.team_master.teams_by_label[label]
            for slot_index, slot in enumerate(slots):
                assigned = [
                    members[member_index].member
                    for member_index in active_indexes[slot_index]
                    if solver.value(assignments[member_index, team_index, slot_index])
                ]
                assigned.sort(
                    key=lambda member: (
                        member.name != definition.rally_leader,
                        member.name not in definition.substitute_leaders,
                        -self.rules.tier_power[member.tier],
                        member.name.casefold(),
                    )
                )
                slot_assignments.append(SlotAssignment(label, slot, tuple(assigned)))
        return DynamicTeamPlan(tuple(slot_assignments), standby)

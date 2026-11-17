"""所属固定の編成を行うCP-SAT Optimizer。

メンバーごとに所属する隊か待機を1つ選び、時間帯ごとの出撃は所属と参加時間から決まる。
目的は次の順の辞書式で比べる（Issue 3でFRM-037の指標へ置き換える）。

1. 延長境界時刻より前の休止の（隊、時間帯）の数（下限の不足。0でなければ出力しない）
2. 延長境界時刻より前で、出撃人数が下限の基本（8人）に足りない人数の2乗の和
3. 延長境界時刻以降の休止の（隊、時間帯）の数
4. 延長境界時刻以降で、下限の基本に足りない人数の2乗の和
5. 待機の人数
6. 上位隊の戦力（大きいほどよい）

遅れて出撃する隊は、出撃開始前の時間帯を人数、休止、上限の対象にしない。応援するメンバーは
その遅れて出撃する隊に所属させ（作成者の仮定A-16）、応援先の出撃人数と上限に数える。応援先は
応援を受ける時間帯に所属メンバーが1人以上参加する（休止中でない。FRM-042、FRM-048）。
応援先のない出撃開始前の参加者は、遅れて出撃する隊に入れない（FRM-047）。

2と4は隊の人数を均すための暫定の指標である。FRM-031の「8人未満の（隊、時間帯）の数」は、
6人以下を禁じるFRM-039と組で入れないと、少数の隊を捨てて残りを8人にそろえる編成を選ぶ。
足りない人数の合計は配り方によらず同じ値になり、人数を均せない。このためIssue 3で
FRM-031とFRM-039を同時に入れるまで、2乗の和を使う（ADR 0034）。
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from kvk_team.team_building.adapters.optimization.errors import (
    OptimizationError,
    OptimizationTimeoutError,
)
from kvk_team.team_building.application.ports import (
    OptimizationOutcome,
    ProvenInfeasible,
    ShortfallKey,
    SolvedPlan,
)
from kvk_team.team_building.domain.availability import (
    AvailabilityResolver,
    ResolvedAvailability,
)
from kvk_team.team_building.domain.member import Member
from kvk_team.team_building.domain.plan import (
    Support,
    TeamMembership,
    TeamPlan,
    TimeSlot,
)
from kvk_team.team_building.domain.rules import KvKRules
from kvk_team.team_building.domain.specification import (
    OperatorSpecification,
    resolve_leaders,
    resolve_member,
)
from kvk_team.team_building.domain.team import (
    AT_LEAST_AS_STRONG_PAIRS,
    EXTENSION_BOUNDARY_MINUTES,
    SORTIE_FLOOR,
    STRICTLY_STRONGER_PAIRS,
    TOP_TEAM_COUNT,
    TOP_TEAM_SIZE,
    can_receive_support,
    is_top_team,
    team_name,
)
from kvk_team.team_building.domain.validation import format_clock


@dataclass(frozen=True, slots=True)
class _LatePlan:
    """運用者の指定から作る、出撃開始時刻と応援（確定参加者の番号で持つ）。"""

    starts: dict[int, int]
    """隊の番号と出撃開始時刻。"""
    supports: tuple[tuple[int, TimeSlot, int, int], ...]
    """（確定参加者の番号, 時間帯, 応援先, 所属する遅れて出撃する隊）。"""

    def has_started(self, number: int, slot: TimeSlot) -> bool:
        """隊が時間帯に出撃開始以降かを返す。"""

        start = self.starts.get(number)
        return start is None or slot.start_minutes >= start

    def support_count(self, number: int, slot: TimeSlot) -> int:
        """隊が時間帯に受ける応援の人数を返す。"""

        return sum(
            1
            for _, support_slot, target, _ in self.supports
            if target == number and support_slot == slot
        )


@dataclass(frozen=True, slots=True)
class _Model:
    """1回の最適化で使うCP-SATの変数。"""

    model: cp_model.CpModel
    membership: dict[tuple[int, int], cp_model.IntVar]
    """（メンバーの番号, 隊の番号）の所属。"""
    waiting: dict[int, cp_model.IntVar]


_Term = tuple[int, cp_model.IntVar, int]
"""目的の項。（係数, 変数, 変数の上限）。"""


@dataclass(slots=True)
class _Levels:
    """目的の段ごとの項。"""

    rest_before: list[_Term] = field(default_factory=list)
    under_before: list[_Term] = field(default_factory=list)
    rest_after: list[_Term] = field(default_factory=list)
    under_after: list[_Term] = field(default_factory=list)
    top_power: list[_Term] = field(default_factory=list)


@dataclass(slots=True)
class MembershipOptimizer:
    """リーダー一覧から隊を作り、確定参加者を隊か待機へ割り当てる。"""

    rules: KvKRules

    def optimize(
        self,
        members: Sequence[Member],
        specification: OperatorSpecification,
        allowed_shortfalls: frozenset[ShortfallKey] | None = None,
    ) -> OptimizationOutcome:
        """所属固定の編成を返す。必須条件を満たせないと証明した場合は理由を返す。

        `allowed_shortfalls`を渡した場合は、延長境界時刻より前の休止をその（隊、時間帯）に限る
        （回答の受け入れの確認。作成者の仮定A-41）。
        """

        source = list(members)
        self._validate_members(source)
        leaders = resolve_leaders(specification, source)
        partition = AvailabilityResolver(self.rules.team_master.event_time).partition(
            source
        )
        confirmed = partition.confirmed
        slots = self.rules.time_slots
        team_numbers = tuple(range(1, specification.team_count + 1))
        leader_index = {
            number: next(
                (
                    index
                    for index, availability in enumerate(confirmed)
                    if availability.member == leader
                ),
                None,
            )
            for number, leader in zip(team_numbers, leaders, strict=True)
        }
        reason = self._top_team_supply_shortage(confirmed, leader_index, slots)
        if reason is not None:
            return ProvenInfeasible(reason)
        late_or_reason = self._late_plan(specification, source, confirmed, slots)
        if isinstance(late_or_reason, str):
            return ProvenInfeasible(late_or_reason)
        late = late_or_reason

        variables = self._create_variables(confirmed, team_numbers, leader_index)
        self._add_late_start_constraints(variables, confirmed, late, slots)
        levels = self._add_sortie_constraints(
            variables,
            confirmed,
            team_numbers,
            leader_index,
            slots,
            late,
            allowed_shortfalls,
        )
        waiting = [(1, variable, 1) for variable in variables.waiting.values()]
        self._set_lexicographic_objective(
            variables.model,
            [
                (levels.rest_before, False),
                (levels.under_before, False),
                (levels.rest_after, False),
                (levels.under_after, False),
                (waiting, False),
                (levels.top_power, True),
            ],
        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.rules.maximum_optimization_seconds
        if self.rules.maximum_deterministic_time is not None:
            solver.parameters.max_deterministic_time = (
                self.rules.maximum_deterministic_time
            )
        solver.parameters.num_search_workers = self.rules.solver_worker_count
        solver.parameters.random_seed = self.rules.solver_random_seed
        status = solver.solve(variables.model)
        if status == cp_model.INFEASIBLE:
            if allowed_shortfalls is not None:
                return ProvenInfeasible(
                    "応援するメンバーを遅れて出撃する隊に所属させたうえで、上位隊の人数、VC、"
                    "戦力関係、応援先の上限と出撃、休止を許した隊と時間帯の外に休止がないことを、"
                    "すべて満たす編成は存在しません"
                )
            if late.starts:
                return ProvenInfeasible(
                    "遅れて出撃する隊と応援先の指定のもとで、上位隊の人数、VC、戦力関係、"
                    "応援先の上限と出撃を全時間帯で満たす編成は存在しません。"
                    "回答か参加者一覧、リーダー一覧を見直してください"
                )
            return ProvenInfeasible(
                "上位隊の人数、VC、戦力関係を全時間帯で満たす編成は存在しません。"
                "参加者、VC、参加時間、リーダー一覧を見直してください"
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
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise OptimizationError(
                f"最適化モデルを解けませんでした（CP-SAT status: {status}）"
            )
        plan = self._extract_plan(
            solver,
            variables,
            source,
            confirmed,
            partition.undecided,
            team_numbers,
            leaders,
            late,
        )
        return SolvedPlan(plan=plan, proven_optimal=status == cp_model.OPTIMAL)

    @staticmethod
    def _late_plan(
        specification: OperatorSpecification,
        source: list[Member],
        confirmed: tuple[ResolvedAvailability, ...],
        slots: tuple[TimeSlot, ...],
    ) -> _LatePlan | str:
        """遅れて出撃する隊と応援を、確定参加者の番号へ解決する。成り立たなければ理由を返す。

        ほかの指定によって変わらない誤りは、アプリケーションが最適化の前に入力のエラーにする
        （`domain.answers.check_answers`）。ここでは、応援先がほかの遅れて出撃する隊の出撃開始前に
        当たるかなど、指定どうしの組み合わせで決まることを確かめる。
        """

        starts = {late.team: late.start_minutes for late in specification.late_starts}
        index_of = {item.member: index for index, item in enumerate(confirmed)}
        slot_by_start = {slot.start_minutes: slot for slot in slots}
        supports: list[tuple[int, TimeSlot, int, int]] = []
        for late in specification.late_starts:
            for ref in late.supports:
                # 応援は並べ直して持つため、書いた位置ではなく時刻と応援先で示す。
                where = (
                    f"{team_name(late.team)}の{format_clock(ref.slot_start_minutes)}の"
                    f"{team_name(ref.team)}への応援"
                )
                member = resolve_member(ref.member, source, where)
                index = index_of.get(member)
                slot = slot_by_start.get(ref.slot_start_minutes)
                if index is None or slot is None:
                    return f"{where}のメンバーか時間帯が、確定した参加時間にありません"
                if not can_receive_support(ref.team) or ref.team == late.team:
                    return (
                        f"{where}の応援先の{team_name(ref.team)}は応援を受けられません"
                    )
                target_start = starts.get(ref.team)
                if target_start is not None and slot.start_minutes < target_start:
                    return (
                        f"{where}の応援先の{team_name(ref.team)}は、"
                        f"{format_clock(slot.start_minutes)}に出撃開始前です"
                    )
                supports.append((index, slot, ref.team, late.team))
        return _LatePlan(starts=starts, supports=tuple(supports))

    @staticmethod
    def _add_late_start_constraints(
        variables: _Model,
        confirmed: tuple[ResolvedAvailability, ...],
        late: _LatePlan,
        slots: tuple[TimeSlot, ...],
    ) -> None:
        """応援するメンバーを遅れて出撃する隊に所属させ、応援先のない出撃開始前の参加者を入れない。"""

        model = variables.model
        supporters: dict[int, set[int]] = {}
        for index, _, _, source_team in late.supports:
            supporters.setdefault(source_team, set()).add(index)
            model.add(variables.membership[index, source_team] == 1)
        for number in late.starts:
            pre_start = [slot for slot in slots if not late.has_started(number, slot)]
            for index, availability in enumerate(confirmed):
                if index in supporters.get(number, set()):
                    continue
                if any(
                    availability.covers(slot.start_minutes, slot.end_minutes)
                    for slot in pre_start
                ):
                    model.add(variables.membership[index, number] == 0)

    @staticmethod
    def _validate_members(members: list[Member]) -> None:
        """名前の重複を拒否する。出力と照合が名前で行われるため。"""

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
    def _top_team_supply_shortage(
        confirmed: tuple[ResolvedAvailability, ...],
        leader_index: dict[int, int | None],
        slots: tuple[TimeSlot, ...],
    ) -> str | None:
        """上位隊に必要な、常時参加でVC可能なメンバーの不足を理由として返す。"""

        top_leaders = {
            index
            for number, index in leader_index.items()
            if is_top_team(number) and index is not None
        }
        for number in range(1, TOP_TEAM_COUNT + 1):
            index = leader_index[number]
            if index is not None and not confirmed[index].member.has_vc:
                return (
                    f"第{number}隊のリーダーがVC不可のため、上位隊の条件を満たせません。"
                    "リーダー一覧の順か参加者一覧を見直してください"
                )
        other_leaders = {
            index for index in leader_index.values() if index is not None
        } - top_leaders
        required = TOP_TEAM_COUNT * (TOP_TEAM_SIZE - 1)
        available = sum(
            1
            for index, availability in enumerate(confirmed)
            if index not in top_leaders
            and index not in other_leaders
            and availability.member.has_vc
            and all(
                availability.covers(slot.start_minutes, slot.end_minutes)
                for slot in slots
            )
        )
        if available < required:
            return (
                "上位隊に必要な、全時間帯に参加しVC可能なメンバーが不足しています: "
                f"{available}人（必要: {required}人）"
            )
        return None

    @staticmethod
    def _create_variables(
        confirmed: tuple[ResolvedAvailability, ...],
        team_numbers: tuple[int, ...],
        leader_index: dict[int, int | None],
    ) -> _Model:
        """所属と待機の変数を作り、1人1か所とリーダーの所属を加える。"""

        model = cp_model.CpModel()
        membership = {
            (index, number): model.new_bool_var(f"m{index}_t{number}")
            for index in range(len(confirmed))
            for number in team_numbers
        }
        waiting = {
            index: model.new_bool_var(f"wait{index}") for index in range(len(confirmed))
        }
        for index in range(len(confirmed)):
            model.add_exactly_one(
                [
                    *(membership[index, number] for number in team_numbers),
                    waiting[index],
                ]
            )
        for number, leader in leader_index.items():
            if leader is not None:
                model.add(membership[leader, number] == 1)
        return _Model(model, membership, waiting)

    def _add_sortie_constraints(
        self,
        variables: _Model,
        confirmed: tuple[ResolvedAvailability, ...],
        team_numbers: tuple[int, ...],
        leader_index: dict[int, int | None],
        slots: tuple[TimeSlot, ...],
        late: _LatePlan,
        allowed_shortfalls: frozenset[ShortfallKey] | None,
    ) -> _Levels:
        """時間帯ごとの出撃人数、上位隊、上限、戦力の制約を加え、目的の段の項を返す。"""

        model = variables.model
        membership = variables.membership
        present = {
            slot: tuple(
                index
                for index, availability in enumerate(confirmed)
                if availability.covers(slot.start_minutes, slot.end_minutes)
            )
            for slot in slots
        }
        levels = _Levels()
        for number in team_numbers:
            if is_top_team(number):
                # 上位隊はVC可能で全時間帯に参加する人だけを所属させる（例外はリーダー）。
                # 時間帯ごとの人数だけでは、途中で抜ける人と途中から来る人の入れ替わりを許す。
                for index, availability in enumerate(confirmed):
                    always = all(
                        availability.covers(slot.start_minutes, slot.end_minutes)
                        for slot in slots
                    )
                    is_leader = index == leader_index[number]
                    if not availability.member.has_vc or not (always or is_leader):
                        model.add(membership[index, number] == 0)
            for slot in slots:
                if not late.has_started(number, slot):
                    continue
                count = sum(membership[index, number] for index in present[slot])
                if is_top_team(number):
                    leader = leader_index[number]
                    leader_present = leader is not None and leader in present[slot]
                    model.add(
                        count
                        == (TOP_TEAM_SIZE if leader_present else TOP_TEAM_SIZE - 1)
                    )
                    continue
                support = late.support_count(number, slot)
                model.add(count + support <= self.rules.member_cap)
                # 休止は所属メンバーの参加で判定し、応援を含めない（FRM-048）。応援を受ける隊は
                # 休止中であってはならない（FRM-042）。
                rest = model.new_bool_var(f"rest_t{number}_{slot.start_minutes}")
                model.add(count + rest >= 1)
                if support:
                    model.add(count >= 1)
                shortage = model.new_int_var(
                    0, SORTIE_FLOOR, f"shortage_t{number}_{slot.start_minutes}"
                )
                model.add(count + support + shortage >= SORTIE_FLOOR)
                squared = model.new_int_var(
                    0, SORTIE_FLOOR**2, f"shortage_sq_t{number}_{slot.start_minutes}"
                )
                model.add_multiplication_equality(squared, [shortage, shortage])
                if slot.start_minutes < EXTENSION_BOUNDARY_MINUTES:
                    if (
                        allowed_shortfalls is not None
                        and (number, slot.start_minutes) not in allowed_shortfalls
                    ):
                        model.add(rest == 0)
                    levels.rest_before.append((1, rest, 1))
                    levels.under_before.append((1, squared, SORTIE_FLOOR**2))
                else:
                    levels.rest_after.append((1, rest, 1))
                    levels.under_after.append((1, squared, SORTIE_FLOOR**2))

        maximum_power = TOP_TEAM_SIZE * max(self.rules.tier_power.values())
        for slot in slots:
            power: dict[int, cp_model.IntVar] = {}
            for number in team_numbers:
                if not is_top_team(number):
                    continue
                variable = model.new_int_var(
                    0, maximum_power, f"power_t{number}_{slot.start_minutes}"
                )
                model.add(
                    variable
                    == sum(
                        membership[index, number]
                        * self.rules.tier_power[confirmed[index].member.tier]
                        for index in present[slot]
                    )
                )
                power[number] = variable
                levels.top_power.append(
                    (TOP_TEAM_COUNT + 1 - number, variable, maximum_power)
                )
            for stronger, weaker in STRICTLY_STRONGER_PAIRS:
                model.add(power[stronger] > power[weaker])
            for stronger, weaker in AT_LEAST_AS_STRONG_PAIRS:
                model.add(power[stronger] >= power[weaker])

        return levels

    @staticmethod
    def _set_lexicographic_objective(
        model: cp_model.CpModel,
        levels: list[tuple[list[_Term], bool]],
    ) -> None:
        """段の順に上位を優先する重みで、1つの最小化の目的へまとめる。

        各段の重みは、それより下の段の取り得る幅の合計より大きくし、上位の段を下位の段のために
        犠牲にしない。最大化する段は符号を反転して最小化する。
        """

        weight = 1
        terms: list[tuple[int, cp_model.IntVar]] = []
        for level_terms, maximize in reversed(levels):
            span = 0
            for coefficient, variable, upper in level_terms:
                span += coefficient * upper
                terms.append(((-1 if maximize else 1) * weight * coefficient, variable))
            weight *= span + 1
        model.minimize(sum(coefficient * variable for coefficient, variable in terms))

    @staticmethod
    def _extract_plan(
        solver: cp_model.CpSolver,
        variables: _Model,
        source: list[Member],
        confirmed: tuple[ResolvedAvailability, ...],
        undecided: tuple[Member, ...],
        team_numbers: tuple[int, ...],
        leaders: tuple[Member, ...],
        late: _LatePlan,
    ) -> TeamPlan:
        """Solverの値を所属固定の編成へ変換する。並びは参加者一覧の順で決める。

        出撃開始時刻と応援は運用者の指定から写す。Validatorが指定との一致を確かめる（FRM-047）。
        """

        order = {member: position for position, member in enumerate(source)}
        teams: list[TeamMembership] = []
        for number, leader in zip(team_numbers, leaders, strict=True):
            assigned = sorted(
                (
                    availability.member
                    for index, availability in enumerate(confirmed)
                    if solver.value(variables.membership[index, number])
                ),
                key=lambda member: (member != leader, order[member]),
            )
            teams.append(
                TeamMembership(number, leader, tuple(assigned), late.starts.get(number))
            )
        waiting = tuple(
            sorted(
                (
                    availability.member
                    for index, availability in enumerate(confirmed)
                    if solver.value(variables.waiting[index])
                ),
                key=lambda member: order[member],
            )
        )
        supports = tuple(
            sorted(
                (
                    Support(confirmed[index].member, slot, target)
                    for index, slot, target, _ in late.supports
                ),
                key=lambda support: (
                    support.time_slot.start_minutes,
                    support.team_number,
                    order[support.member],
                ),
            )
        )
        return TeamPlan(
            teams=tuple(teams),
            waiting=waiting,
            undecided=undecided,
            supports=supports,
        )

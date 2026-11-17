"""回答を確かめる手順のテストで共有する、架空の世界のOptimizerとValidator。

CP-SATを使わず、受け入れた遅れて出撃する隊の組から下限の不足（休止）の（隊、時間帯）を決める。
回答を確かめる手順（作成者の仮定A-41）とFRM-090の性質を、最適化の挙動から切り離して確かめる。
名前は架空である。

不足は遅らせた隊の組だけで決まり、応援には左右されない。応援の並びと名前の解決は
`tests/test_answers.py`とCLIの統合テストで確かめる。第4隊と第5隊を遅らせる回答と、応援を持つ回答の生成は、
選択肢を列挙する分割案の4で、選択肢から回答を作るときに加える。
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from kvk_team.interfaces.cli.composition import default_rules
from kvk_team.team_building.application.build_team_plan import BuildTeamPlan
from kvk_team.team_building.application.ports import (
    OptimizationOutcome,
    ProvenInfeasible,
    SolvedPlan,
)
from kvk_team.team_building.domain.answers import Answer
from kvk_team.team_building.domain.member import Member, Tier
from kvk_team.team_building.domain.plan import TeamPlan, TimeSlot
from kvk_team.team_building.domain.specification import (
    LateStart,
    MemberRef,
    OperatorSpecification,
)
from kvk_team.team_building.domain.validation import (
    ValidationCode,
    ValidationIssue,
    ValidationReport,
)

RULES = default_rules()
EVENT = RULES.team_master.event_time
ALLIANCE = "架空同盟"
H21 = EVENT.start_minutes
H2130 = H21 + 30
H22 = H21 + 60
H23 = H21 + 120
LATE_TEAMS = (6, 7, 8, 9, 10)
"""遅れて出撃させてよい隊。リーダーが23:00から来るため、23:00までの出撃開始時刻を応援なしで書ける。"""
TEAM_COUNT = 10

Key = tuple[int, int]


def _leader(number: int) -> Member:
    start = H23 if number in LATE_TEAMS else H21
    return Member(
        name=f"リーダー{number:02d}",
        alliance=ALLIANCE,
        tier=Tier.G8,
        has_vc=True,
        start_time_minutes=start,
        end_time_minutes=EVENT.end_minutes,
    )


EARLY_MEMBERS = tuple(
    Member(
        name=f"序盤だけ{index}",
        alliance=ALLIANCE,
        tier=Tier.G5,
        has_vc=True,
        start_time_minutes=H21,
        end_time_minutes=H22,
    )
    for index in (1, 2)
)
"""21:00から22:00まで参加し、22:00から出撃する隊の応援に書けるメンバー。"""
LEADERS = [_leader(number) for number in range(1, TEAM_COUNT + 1)]
MEMBERS = [*LEADERS, *EARLY_MEMBERS]
SPECIFICATION = OperatorSpecification(
    leaders=tuple(MemberRef(member.name, ALLIANCE) for member in LEADERS)
)


def answer(target: Key, team: int, start: int = H22) -> Answer:
    """対象の（隊、時間帯）へ、隊を遅らせる回答を作る。"""

    return Answer(target[0], target[1], LateStart(team, start))


def _encode(keys: frozenset[Key]) -> Member:
    """不足の組を編成へ持たせるため、名前に書いた架空のメンバーを作る。"""

    text = ",".join(f"{team}@{start}" for team, start in sorted(keys))
    return Member(name=f"不足[{text}]", alliance=ALLIANCE, tier=Tier.G5, has_vc=False)


def _decode(plan: TeamPlan) -> frozenset[Key]:
    name = plan.waiting[0].name
    text = name[len("不足[") : -1]
    if not text:
        return frozenset()
    return frozenset(
        (int(team), int(start))
        for team, start in (item.split("@") for item in text.split(","))
    )


@dataclass(frozen=True)
class World:
    """受け入れた遅れて出撃する隊から、下限の不足を決める架空の世界。"""

    base: frozenset[Key]
    """回答なしの下限の不足。"""
    resolves: Mapping[int, frozenset[Key]] = field(default_factory=dict)
    """隊を遅らせるとなくなる不足。遅らせた隊自身の出撃開始前の時間帯は、ここに書かなくてもなくなる。"""
    creates: Mapping[int, frozenset[Key]] = field(default_factory=dict)
    """隊を遅らせると新しく生まれる不足。"""
    conflicts: frozenset[frozenset[int]] = frozenset()
    """同時に遅らせると成り立たない隊の組。"""
    infeasible: bool = False
    optimal_without_answers: bool = True
    optimal_with_answers: bool = True
    unproven: frozenset[frozenset[int]] = frozenset()
    """最適性を示せない、遅らせた隊の組。"""

    def shortfalls(self, specification: OperatorSpecification) -> frozenset[Key]:
        keys = set(self.base)
        for late in specification.late_starts:
            keys -= self.resolves.get(late.team, frozenset())
            keys -= {
                (team, start)
                for team, start in keys
                if team == late.team and start < late.start_minutes
            }
            keys |= self.creates.get(late.team, frozenset())
        return frozenset(keys)


@dataclass
class WorldOptimizer:
    """架空の世界から編成を返し、呼び出しを記録する。"""

    world: World
    calls: list[tuple[frozenset[int], frozenset[Key] | None]] = field(
        default_factory=list
    )
    solved: list[tuple[frozenset[Key] | None, frozenset[Key], bool]] = field(
        default_factory=list
    )
    """解ありで返した（許した組、不足、最適性）。回答を確かめる手順の性質テストで使う。"""

    def optimize(
        self,
        members: Sequence[Member],
        specification: OperatorSpecification,
        allowed_shortfalls: frozenset[Key] | None = None,
    ) -> OptimizationOutcome:
        teams = frozenset(late.team for late in specification.late_starts)
        self.calls.append((teams, allowed_shortfalls))
        if self.world.infeasible:
            return ProvenInfeasible("架空の世界には編成がありません")
        if any(pair <= teams for pair in self.world.conflicts):
            return ProvenInfeasible("同時に遅らせられない隊があります")
        keys = self.world.shortfalls(specification)
        if allowed_shortfalls is not None and not keys <= allowed_shortfalls:
            return ProvenInfeasible("休止を新しく生みます")
        plan = TeamPlan(teams=(), waiting=(_encode(keys),), undecided=())
        optimal = (
            self.world.optimal_with_answers
            if teams
            else self.world.optimal_without_answers
        ) and teams not in self.world.unproven
        self.solved.append((allowed_shortfalls, keys, optimal))
        return SolvedPlan(plan=plan, proven_optimal=optimal)


@dataclass
class WorldValidator:
    """編成に持たせた不足を、休止の必須条件エラーとして返す。"""

    def validate(
        self,
        plan: TeamPlan,
        source_members: Sequence[Member],
        specification: OperatorSpecification,
    ) -> ValidationReport:
        issues = tuple(
            ValidationIssue(
                ValidationCode.REST,
                f"第{team}隊は所属メンバーが参加しておらず休止になります",
                team,
                TimeSlot(start, start + 30),
            )
            for team, start in sorted(_decode(plan))
        )
        return ValidationReport(issues, (), (), plan.waiting, ())


def use_case(world: World) -> tuple[BuildTeamPlan, WorldOptimizer]:
    """架空の世界で回答を確かめるユースケースを作る。"""

    optimizer = WorldOptimizer(world)
    return (
        BuildTeamPlan(rules=RULES, optimizer=optimizer, validator=WorldValidator()),
        optimizer,
    )


def run(world: World, answers: Sequence[Answer]) -> object:
    """ユースケースを実行し、編成か送出した例外を返す。"""

    build, _ = use_case(world)
    try:
        return build.execute(MEMBERS, SPECIFICATION, answers)
    except Exception as error:  # noqa: BLE001 - 結果として比べるため例外も値にする
        return error

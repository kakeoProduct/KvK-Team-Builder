"""編成ユースケース、検証済み編成、CLIの組み立てのワークフローテスト。"""

from collections.abc import Sequence
from dataclasses import dataclass, field, replace

import pytest

from kvk_team.interfaces.cli.composition import default_rules
from kvk_team.interfaces.cli.team_builder import TeamBuilder
from kvk_team.team_building.application.build_team_plan import (
    BuildError,
    BuildTeamPlan,
    LowerBoundShortfallError,
    NoValidPlanError,
    ShortfallUndeterminedError,
)
from kvk_team.team_building.application.ports import (
    OptimizationOutcome,
    ProvenInfeasible,
    SolvedPlan,
)
from kvk_team.team_building.domain.member import Member, Tier
from kvk_team.team_building.domain.plan import TeamPlan, TimeSlot
from kvk_team.team_building.domain.specification import (
    MemberRef,
    OperatorSpecification,
    SpecificationError,
)
from kvk_team.team_building.domain.validation import (
    ValidatedTeamPlan,
    ValidationCode,
    ValidationIssue,
    ValidationReport,
)

LEADERS = tuple(
    Member(f"リーダー{index}", "未設定", Tier.G8, has_vc=True) for index in range(1, 4)
)
MEMBERS = list(LEADERS)
SPECIFICATION = OperatorSpecification(
    leaders=tuple(MemberRef(member.name, member.alliance) for member in LEADERS)
)
WAITING = Member("いろは", "未設定", Tier.G7, has_vc=True)


@dataclass
class FakeParser:
    """調整処理のテスト用に既知のメンバーを返す。"""

    members: list[Member]

    def parse(self, markdown: str) -> list[Member]:
        """テスト用Markdownを無視して既知のメンバーを返す。"""

        return list(self.members)


@dataclass
class SequencedOptimizer:
    """試行ごとに異なる結果を返し、受け取った参加者と指定を記録する。"""

    outcomes: list[OptimizationOutcome]
    received: list[tuple[list[Member], OperatorSpecification]] = field(
        default_factory=list
    )

    @property
    def call_count(self) -> int:
        """呼び出し回数を返す。"""

        return len(self.received)

    def optimize(
        self,
        members: Sequence[Member],
        specification: OperatorSpecification,
        allowed_shortfalls: frozenset[tuple[int, int]] | None = None,
    ) -> OptimizationOutcome:
        """呼び出しを記録して、次の結果を返す。"""

        self.received.append((list(members), specification))
        return self.outcomes[min(self.call_count - 1, len(self.outcomes) - 1)]


@dataclass
class SequencedValidator:
    """再試行後の成功を再現するため、検証結果を順番に返す。"""

    reports: list[ValidationReport]
    received: list[tuple[TeamPlan, list[Member], OperatorSpecification]] = field(
        default_factory=list
    )

    @property
    def call_count(self) -> int:
        """呼び出し回数を返す。"""

        return len(self.received)

    def validate(
        self,
        plan: TeamPlan,
        source_members: Sequence[Member],
        specification: OperatorSpecification,
    ) -> ValidationReport:
        """受け取った候補、参加者、指定を記録して、次の検証結果を返す。"""

        self.received.append((plan, list(source_members), specification))
        return self.reports[min(self.call_count - 1, len(self.reports) - 1)]


@dataclass
class RecordingExporter:
    """受け取った検証済み編成を記録し、固定文字列を返す。"""

    received: ValidatedTeamPlan | None = None

    def export(self, validated: ValidatedTeamPlan) -> str:
        """検証済み編成を記録して固定文字列を返す。"""

        self.received = validated
        return "exported\n"


@dataclass
class FixedBuildTeamPlan:
    """CLIの組み立てを検証するため、既知の検証済み編成を返す。"""

    validated: ValidatedTeamPlan
    received: tuple[list[Member], OperatorSpecification] | None = None

    def execute(
        self,
        members: Sequence[Member],
        specification: OperatorSpecification,
        answers: Sequence[object] = (),
    ) -> ValidatedTeamPlan:
        """受け取った参加者と指定を記録して既知の検証済み編成を返す。"""

        self.received = (list(members), specification)
        return self.validated


@dataclass
class FailingBuildTeamPlan:
    """再試行の上限に達したユースケースを再現する。"""

    def execute(
        self,
        members: Sequence[Member],
        specification: OperatorSpecification,
        answers: Sequence[object] = (),
    ) -> ValidatedTeamPlan:
        """常にBuildErrorを送出する。"""

        raise BuildError("3回の再配置後も検証NGです: 人数NG")


def _plan(*waiting: Member) -> TeamPlan:
    return TeamPlan(teams=(), waiting=waiting, undecided=())


def _solved(plan: TeamPlan | None = None, proven_optimal: bool = True) -> SolvedPlan:
    return SolvedPlan(plan=plan or _plan(), proven_optimal=proven_optimal)


def _report(
    issues: tuple[ValidationIssue, ...] = (),
    warnings: tuple[ValidationIssue, ...] = (),
) -> ValidationReport:
    return ValidationReport(issues, warnings, (), (), ())


def _invalid(message: str = "人数NG") -> ValidationReport:
    return _report((ValidationIssue(ValidationCode.CAPACITY, message),))


def _rest(number: int = 4, start: int = 21 * 60) -> ValidationIssue:
    return ValidationIssue(
        ValidationCode.REST,
        f"第{number}隊は所属メンバーが参加しておらず休止になります",
        number,
        TimeSlot(start, start + 30),
    )


def _warning_only() -> ValidationReport:
    return _report(
        warnings=(
            ValidationIssue(ValidationCode.UNDERFILLED, "第11隊が8人未満です: 7人"),
        )
    )


def _use_case(
    optimizer: SequencedOptimizer,
    validator: SequencedValidator,
    attempts: int = 3,
) -> BuildTeamPlan:
    return BuildTeamPlan(
        rules=replace(default_rules(), maximum_validation_attempts=attempts),
        optimizer=optimizer,
        validator=validator,
    )


def test_validated_team_plan_rejects_report_with_invariant_errors() -> None:
    """必須条件エラーを含む検証結果は、元の指摘を添えて拒否する。"""

    with pytest.raises(ValueError, match="必須条件.*人数NG"):
        ValidatedTeamPlan(plan=_plan(), report=_invalid(), proven_optimal=True)
    valid = _report()
    assert (
        ValidatedTeamPlan(plan=_plan(), report=valid, proven_optimal=True).report
        is valid
    )


def test_validated_team_plan_accepts_warnings() -> None:
    """第4隊以降の8人未満などの警告は、検証済み編成の妨げにならない。"""

    assert ValidatedTeamPlan(
        plan=_plan(), report=_warning_only(), proven_optimal=True
    ).report.warnings


def test_use_case_retries_and_returns_the_accepted_candidate() -> None:
    """拒否された候補は再最適化し、検証OKになった試行の候補を返す。"""

    first, second = _plan(), _plan(WAITING)
    optimizer = SequencedOptimizer([_solved(first), _solved(second)])
    valid = _report()
    validator = SequencedValidator([_invalid(), valid])

    validated = _use_case(optimizer, validator).execute(MEMBERS, SPECIFICATION)

    assert validated.plan is second
    assert validated.report is valid
    assert optimizer.received == [(MEMBERS, SPECIFICATION), (MEMBERS, SPECIFICATION)]
    assert validator.received == [
        (first, MEMBERS, SPECIFICATION),
        (second, MEMBERS, SPECIFICATION),
    ]


def test_use_case_returns_warning_only_result_without_retry() -> None:
    """警告だけの検証結果は成功として扱い、再試行しない。"""

    optimizer = SequencedOptimizer([_solved()])
    validator = SequencedValidator([_warning_only()])

    validated = _use_case(optimizer, validator).execute(MEMBERS, SPECIFICATION)

    assert len(validated.report.warnings) == 1
    assert optimizer.call_count == 1


def test_use_case_keeps_whether_optimality_was_proven() -> None:
    """最適だと示せなかった編成も出力でき、そのことを検証済み編成に残す（FRM-049で使う）。"""

    optimizer = SequencedOptimizer([_solved(proven_optimal=False)])

    validated = _use_case(optimizer, SequencedValidator([_report()])).execute(
        MEMBERS, SPECIFICATION
    )

    assert validated.proven_optimal is False


def test_use_case_raises_with_last_report_after_attempt_limit() -> None:
    """NGが続く結果を返さず、上限回数と最後の検証結果の指摘を伝える。"""

    optimizer = SequencedOptimizer([_solved()])
    validator = SequencedValidator([_invalid("初回の人数NG"), _invalid("VCなし")])

    with pytest.raises(BuildError, match="2回.*VCなし") as error_info:
        _use_case(optimizer, validator, attempts=2).execute(MEMBERS, SPECIFICATION)
    assert "初回の人数NG" not in str(error_info.value)
    assert optimizer.call_count == 2
    assert validator.call_count == 2


def test_use_case_reports_proven_infeasibility_with_reason_without_retry() -> None:
    """解がないと証明した結果は、理由を示して止め、検証も再試行もしない。"""

    optimizer = SequencedOptimizer(
        [ProvenInfeasible("VC可能なメンバーが不足しています")]
    )
    validator = SequencedValidator([_report()])

    with pytest.raises(NoValidPlanError, match="VC可能なメンバーが不足"):
        _use_case(optimizer, validator).execute(MEMBERS, SPECIFICATION)
    assert optimizer.call_count == 1
    assert validator.call_count == 0


def test_use_case_stops_with_reason_when_shortfall_is_proven() -> None:
    """最適な編成でも延長境界時刻より前の休止が残る場合は、隊と時刻を示して止める。

    選択肢はIssue 3と4で加えるため、ここでは示さない。
    """

    optimizer = SequencedOptimizer([_solved()])
    validator = SequencedValidator(
        [_report((_rest(4, 21 * 60), _rest(4, 21 * 60 + 30)))]
    )

    with pytest.raises(LowerBoundShortfallError) as raised:
        _use_case(optimizer, validator).execute(MEMBERS, SPECIFICATION)

    message = str(raised.value)
    assert "- 21:00: 第4隊は所属メンバーが参加しておらず休止になります" in message
    assert "- 21:30: 第4隊" in message
    assert len(raised.value.shortfalls) == 2
    assert optimizer.call_count == 1


def test_use_case_treats_unproven_shortfall_as_timeout() -> None:
    """最適だと示せない編成の休止は、避けられるか分からないため時間切れのエラーとする（FRM-090(6)）。"""

    optimizer = SequencedOptimizer([_solved(proven_optimal=False)])
    validator = SequencedValidator([_report((_rest(),))])

    with pytest.raises(ShortfallUndeterminedError, match="時間切れ"):
        _use_case(optimizer, validator).execute(MEMBERS, SPECIFICATION)
    assert optimizer.call_count == 1


def test_use_case_retries_when_shortfall_is_mixed_with_other_errors() -> None:
    """下限の不足とほかの必須条件エラーが混ざる候補は、Optimizerの誤りとして再試行する。"""

    optimizer = SequencedOptimizer([_solved()])
    mixed = _report((_rest(), ValidationIssue(ValidationCode.CAPACITY, "上限NG")))
    validator = SequencedValidator([mixed, _report()])

    validated = _use_case(optimizer, validator).execute(MEMBERS, SPECIFICATION)

    assert validated.report.is_valid
    assert optimizer.call_count == 2


def test_use_case_rejects_leader_missing_from_roster_before_optimizing() -> None:
    """リーダーが参加者一覧にいなければ、最適化の前に入力のエラーにする（FRM-047）。"""

    optimizer = SequencedOptimizer([_solved()])
    specification = OperatorSpecification(
        leaders=(*SPECIFICATION.leaders[:2], MemberRef("いない人", "未設定"))
    )

    with pytest.raises(SpecificationError, match="3番目.*見つかりません"):
        _use_case(optimizer, SequencedValidator([_report()])).execute(
            MEMBERS, specification
        )
    assert optimizer.call_count == 0


def test_cli_team_builder_parses_runs_use_case_and_exports_validated_plan() -> None:
    """CLIの組み立ては、解析結果と指定をユースケースへ渡し、検証済み編成だけを出力する。"""

    validated = ValidatedTeamPlan(plan=_plan(), report=_report(), proven_optimal=True)
    use_case = FixedBuildTeamPlan(validated)
    exporter = RecordingExporter()
    builder = TeamBuilder(
        parser=FakeParser(MEMBERS),
        build_team_plan=use_case,
        exporter=exporter,
    )

    assert builder.build("source", SPECIFICATION) == "exported\n"
    assert use_case.received == (MEMBERS, SPECIFICATION)
    assert exporter.received is validated


def test_cli_team_builder_does_not_export_when_use_case_fails() -> None:
    """ユースケースが失敗したら、例外を伝えて出力しない。"""

    exporter = RecordingExporter()
    builder = TeamBuilder(
        parser=FakeParser(MEMBERS),
        build_team_plan=FailingBuildTeamPlan(),
        exporter=exporter,
    )

    with pytest.raises(BuildError, match="検証NG"):
        builder.build("source", SPECIFICATION)
    assert exporter.received is None

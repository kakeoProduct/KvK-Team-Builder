"""編成ユースケース、検証済み編成、CLIの組み立てのワークフローテスト。"""

from collections.abc import Sequence
from dataclasses import dataclass, field, replace

import pytest

from kvk_team.interfaces.cli.composition import default_rules
from kvk_team.interfaces.cli.team_builder import TeamBuilder
from kvk_team.team_building.application.build_team_plan import (
    BuildError,
    BuildTeamPlan,
)
from kvk_team.team_building.domain.member import Member, Tier
from kvk_team.team_building.domain.schedule import DynamicTeamPlan
from kvk_team.team_building.domain.validation import (
    DynamicValidationCode,
    DynamicValidationIssue,
    DynamicValidationReport,
    ValidatedTeamPlan,
)

MEMBER = Member("山田", "未設定", Tier.G8, has_vc=True)
STANDBY = Member("いろは", "未設定", Tier.G7, has_vc=True)


@dataclass
class FakeParser:
    """調整処理のテスト用に既知のメンバー1人を返す。"""

    member: Member

    def parse(self, markdown: str) -> list[Member]:
        """テスト用Markdownを無視して既知のメンバーを返す。"""

        return [self.member]


@dataclass
class SequencedOptimizer:
    """試行ごとに異なる編成候補を返し、受け取った参加者を記録する。"""

    plans: list[DynamicTeamPlan]
    received: list[list[Member]] = field(default_factory=list)

    @property
    def call_count(self) -> int:
        """呼び出し回数を返す。"""

        return len(self.received)

    def optimize(self, members: list[Member]) -> DynamicTeamPlan:
        """呼び出しを記録して、次の編成候補を返す。"""

        self.received.append(list(members))
        return self.plans[min(self.call_count - 1, len(self.plans) - 1)]


@dataclass
class SequencedValidator:
    """再試行後の成功を再現するため、検証結果を順番に返す。"""

    reports: list[DynamicValidationReport]
    received: list[tuple[DynamicTeamPlan, list[Member]]] = field(default_factory=list)

    @property
    def call_count(self) -> int:
        """呼び出し回数を返す。"""

        return len(self.received)

    def validate(
        self,
        plan: DynamicTeamPlan,
        source_members: list[Member],
    ) -> DynamicValidationReport:
        """受け取った候補と参加者を記録して、次の検証結果を返す。"""

        self.received.append((plan, list(source_members)))
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
    received: list[Member] | None = None

    def execute(self, members: Sequence[Member]) -> ValidatedTeamPlan:
        """受け取った参加者を記録して既知の検証済み編成を返す。"""

        self.received = list(members)
        return self.validated


@dataclass
class FailingBuildTeamPlan:
    """再試行の上限に達したユースケースを再現する。"""

    def execute(self, members: Sequence[Member]) -> ValidatedTeamPlan:
        """常にBuildErrorを送出する。"""

        raise BuildError("3回の再配置後も検証NGです: 人数NG")


def _plan(*standby: Member) -> DynamicTeamPlan:
    return DynamicTeamPlan(assignments=(), standby_members=standby)


def _issue(message: str) -> DynamicValidationIssue:
    return DynamicValidationIssue(DynamicValidationCode.CAPACITY, message)


def _invalid(message: str = "人数NG") -> DynamicValidationReport:
    return DynamicValidationReport((_issue(message),), (), (), ())


def _valid() -> DynamicValidationReport:
    return DynamicValidationReport((), (), (), ())


def _warning_only() -> DynamicValidationReport:
    warning = DynamicValidationIssue(
        DynamicValidationCode.UNDERFILLED,
        "Kが8人未満です: 7人",
    )
    return DynamicValidationReport((), (warning,), (), ())


def _use_case(
    optimizer: SequencedOptimizer,
    validator: SequencedValidator,
    attempts: int,
) -> BuildTeamPlan:
    return BuildTeamPlan(
        rules=replace(default_rules(), maximum_validation_attempts=attempts),
        optimizer=optimizer,
        validator=validator,
    )


def test_validated_team_plan_rejects_report_with_invariant_errors() -> None:
    """必須条件エラーを含む検証結果は、元の指摘を添えて拒否する。"""

    with pytest.raises(ValueError, match="必須条件.*人数NG"):
        ValidatedTeamPlan(plan=_plan(), report=_invalid())
    valid = _valid()
    assert ValidatedTeamPlan(plan=_plan(), report=valid).report is valid


def test_validated_team_plan_accepts_warnings() -> None:
    """D〜Kの8人未満などの警告は、検証済み編成の妨げにならない。"""

    report = _warning_only()

    assert ValidatedTeamPlan(plan=_plan(), report=report).report.warnings


def test_use_case_retries_and_returns_the_accepted_candidate() -> None:
    """拒否された候補は再最適化し、検証OKになった試行の候補を返す。"""

    first, second = _plan(), _plan(STANDBY)
    optimizer = SequencedOptimizer([first, second])
    valid = _valid()
    validator = SequencedValidator([_invalid(), valid])

    validated = _use_case(optimizer, validator, attempts=3).execute([MEMBER])

    assert validated.plan is second
    assert validated.report is valid
    assert optimizer.call_count == 2
    assert validator.call_count == 2
    assert optimizer.received == [[MEMBER], [MEMBER]]
    assert validator.received == [(first, [MEMBER]), (second, [MEMBER])]


def test_use_case_returns_warning_only_result_without_retry() -> None:
    """警告だけの検証結果は成功として扱い、再試行しない。"""

    optimizer = SequencedOptimizer([_plan()])
    validator = SequencedValidator([_warning_only()])

    validated = _use_case(optimizer, validator, attempts=3).execute([MEMBER])

    assert len(validated.report.warnings) == 1
    assert optimizer.call_count == 1


def test_use_case_raises_with_last_report_after_attempt_limit() -> None:
    """NGが続く結果を返さず、上限回数と最後の検証結果の指摘を伝える。"""

    optimizer = SequencedOptimizer([_plan()])
    validator = SequencedValidator([_invalid("初回の人数NG"), _invalid("VCなし")])

    with pytest.raises(BuildError, match="2回.*VCなし") as error_info:
        _use_case(optimizer, validator, attempts=2).execute([MEMBER])
    assert "初回の人数NG" not in str(error_info.value)
    assert optimizer.call_count == 2
    assert validator.call_count == 2


def test_cli_team_builder_parses_runs_use_case_and_exports_validated_plan() -> None:
    """CLIの組み立ては、解析結果をユースケースへ渡し、検証済み編成だけを出力する。"""

    validated = ValidatedTeamPlan(plan=_plan(), report=_valid())
    use_case = FixedBuildTeamPlan(validated)
    exporter = RecordingExporter()
    builder = TeamBuilder(
        parser=FakeParser(MEMBER),
        build_team_plan=use_case,
        exporter=exporter,
    )

    assert builder.build("source") == "exported\n"
    assert use_case.received == [MEMBER]
    assert exporter.received is validated


def test_cli_team_builder_does_not_export_when_use_case_fails() -> None:
    """ユースケースが失敗したら、例外を伝えて出力しない。"""

    exporter = RecordingExporter()
    builder = TeamBuilder(
        parser=FakeParser(MEMBER),
        build_team_plan=FailingBuildTeamPlan(),
        exporter=exporter,
    )

    with pytest.raises(BuildError, match="検証NG"):
        builder.build("source")
    assert exporter.received is None

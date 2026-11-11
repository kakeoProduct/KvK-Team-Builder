"""参加者Markdownを解析し、編成ユースケースを実行して、検証済み編成をMarkdownと編成の記録で出力する。"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from kvk_team.team_building.domain.answers import Answer
from kvk_team.team_building.domain.member import Member
from kvk_team.team_building.domain.plan_record import PlanRecord
from kvk_team.team_building.domain.specification import OperatorSpecification
from kvk_team.team_building.domain.validation import ValidatedTeamPlan


class ParserPort(Protocol):
    """参加者MarkdownをMemberへ変換する境界。"""

    def parse(self, markdown: str) -> list[Member]:
        """参加者Markdownを解析する。"""


class BuildTeamPlanPort(Protocol):
    """参加者と運用者の指定から検証済み編成を作るユースケースの境界。"""

    def execute(
        self,
        members: Sequence[Member],
        specification: OperatorSpecification,
        answers: Sequence[Answer] = (),
    ) -> ValidatedTeamPlan:
        """検証済み編成を返す。"""


class ExporterPort(Protocol):
    """検証済み編成を出力形式へ変換する境界。"""

    def export(self, validated: ValidatedTeamPlan) -> str:
        """検証済み編成を出力する。"""


@dataclass(frozen=True, slots=True)
class TeamBuildResult:
    """1回の編成の出力。編成のMarkdownと、次の実行の前回の編成になる編成の記録（DAT-010）。"""

    markdown: str
    record: PlanRecord
    previous_unmatched: int | None
    """前回の編成のうち、今回の参加者一覧に名前と同盟の組で当たらない人数。前回の編成がなければNone。"""


@dataclass(frozen=True, slots=True)
class TeamBuilder:
    """CLI向けに、解析、編成ユースケース、出力をこの順に呼び出す。

    編成ルールや検証の判断は持たない。ユースケースが返した検証済み編成だけを出力し、記録する。
    """

    parser: ParserPort
    build_team_plan: BuildTeamPlanPort
    exporter: ExporterPort

    def build(
        self,
        markdown: str,
        specification: OperatorSpecification,
        answers: Sequence[Answer] = (),
        *,
        created_at: datetime,
    ) -> TeamBuildResult:
        """参加者Markdownから、検証済みの所属固定の編成のMarkdownと記録を返す。

        `created_at`は時差付きの実行の時刻（フォルダ名と同じ時刻）で、編成の記録に書く（DAT-002）。
        """

        members = self.parser.parse(markdown)
        validated = self.build_team_plan.execute(members, specification, answers)
        previous = specification.previous_plan
        return TeamBuildResult(
            markdown=self.exporter.export(validated),
            record=PlanRecord.from_validated(validated, created_at),
            previous_unmatched=(
                None if previous is None else previous.unmatched_count(members)
            ),
        )

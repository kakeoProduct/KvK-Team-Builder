"""参加者Markdownを解析し、編成ユースケースを実行して、検証済み編成をMarkdownで出力する。"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from kvk_team.team_building.domain.member import Member
from kvk_team.team_building.domain.validation import ValidatedTeamPlan


class ParserPort(Protocol):
    """参加者MarkdownをMemberへ変換する境界。"""

    def parse(self, markdown: str) -> list[Member]:
        """参加者Markdownを解析する。"""


class BuildTeamPlanPort(Protocol):
    """参加者から検証済み編成を作るユースケースの境界。"""

    def execute(self, members: Sequence[Member]) -> ValidatedTeamPlan:
        """検証済み編成を返す。"""


class ExporterPort(Protocol):
    """検証済み編成を出力形式へ変換する境界。"""

    def export(self, validated: ValidatedTeamPlan) -> str:
        """検証済み編成を出力する。"""


@dataclass(frozen=True, slots=True)
class TeamBuilder:
    """CLI向けに、解析、編成ユースケース、出力をこの順に呼び出す。

    編成ルールや検証の判断は持たない。ユースケースが返した検証済み編成だけを出力する。
    """

    parser: ParserPort
    build_team_plan: BuildTeamPlanPort
    exporter: ExporterPort

    def build(self, markdown: str) -> str:
        """参加者Markdownから、検証済みの時間帯別編成Markdownを返す。"""

        members = self.parser.parse(markdown)
        validated = self.build_team_plan.execute(members)
        return self.exporter.export(validated)

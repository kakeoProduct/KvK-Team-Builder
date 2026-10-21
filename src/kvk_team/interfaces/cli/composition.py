"""CLIで使う既定の編成ルールと部品を組み立てる。"""

from pathlib import Path

from kvk_team.interfaces.cli.team_builder import TeamBuilder
from kvk_team.team_building.adapters.input.markdown_member_parser import (
    MarkdownMemberParser,
)
from kvk_team.team_building.adapters.optimization.cp_sat_team_optimizer import (
    TimeSlotTeamOptimizer,
)
from kvk_team.team_building.adapters.output.dynamic_markdown_exporter import (
    DynamicMarkdownExporter,
)
from kvk_team.team_building.adapters.persistence.json_team_master_repository import (  # noqa: E501
    JsonTeamMasterRepository,
    load_default_team_master,
)
from kvk_team.team_building.application.build_team_plan import BuildTeamPlan
from kvk_team.team_building.domain.rules import KvKRules
from kvk_team.team_building.domain.validation import DynamicTeamValidator


def default_rules(team_master_path: Path | None = None) -> KvKRules:
    """JSONチームマスタを使う既定の編成ルールを返す。

    パスを省略すると同梱のマスタを使う。運用中の本物のマスタはGit管理外に置き、パスで渡す。
    値を変える場合は、`dataclasses.replace(default_rules(), ...)`で型を検査しながら上書きする。
    """

    team_master = (
        load_default_team_master()
        if team_master_path is None
        else JsonTeamMasterRepository(team_master_path).load()
    )
    return KvKRules(team_master=team_master)


def create_team_builder(rules: KvKRules | None = None) -> TeamBuilder:
    """同じ編成ルールを共有する既定の部品で、CLI向けのTeamBuilderを組み立てる。"""

    resolved = rules if rules is not None else default_rules()
    return TeamBuilder(
        parser=MarkdownMemberParser(),
        build_team_plan=BuildTeamPlan(
            rules=resolved,
            optimizer=TimeSlotTeamOptimizer(resolved),
            validator=DynamicTeamValidator(resolved),
        ),
        exporter=DynamicMarkdownExporter(resolved),
    )

"""CLIで使う既定の編成ルール、運用者の指定、部品を組み立てる。"""

from pathlib import Path

from kvk_team.interfaces.cli.team_builder import TeamBuilder
from kvk_team.team_building.adapters.input.markdown_member_parser import (
    MarkdownMemberParser,
)
from kvk_team.team_building.adapters.optimization.cp_sat_team_optimizer import (
    MembershipOptimizer,
)
from kvk_team.team_building.adapters.output.team_plan_markdown_exporter import (
    TeamPlanMarkdownExporter,
)
from kvk_team.team_building.adapters.persistence.json_answers_repository import (
    JsonAnswersRepository,
)
from kvk_team.team_building.adapters.persistence.json_operator_settings_repository import (  # noqa: E501
    JsonOperatorSettingsRepository,
    default_settings_path,
)
from kvk_team.team_building.adapters.persistence.json_team_master_repository import (  # noqa: E501
    JsonTeamMasterRepository,
    load_default_team_master,
)
from kvk_team.team_building.application.build_team_plan import BuildTeamPlan
from kvk_team.team_building.domain.answers import Answer
from kvk_team.team_building.domain.rules import KvKRules
from kvk_team.team_building.domain.specification import OperatorSpecification
from kvk_team.team_building.domain.validation import TeamPlanValidator


def default_rules(team_master_path: Path | None = None) -> KvKRules:
    """JSONチームマスタを使う既定の編成ルールを返す。

    パスを省略すると同梱のマスタを使う。値を変える場合は、
    `dataclasses.replace(default_rules(), ...)`で型を検査しながら上書きする。
    """

    team_master = (
        load_default_team_master()
        if team_master_path is None
        else JsonTeamMasterRepository(team_master_path).load()
    )
    return KvKRules(team_master=team_master)


def default_specification(settings_path: Path | None = None) -> OperatorSpecification:
    """運用者の指定（`settings.json`）を返す。

    パスを省略すると同梱の架空の例（サンプルの参加者一覧のリーダー）を使う。本物の指定は
    個人名を含むため、イベントのフォルダ（Git管理外）に置いてパスで渡す（DAT-001、DAT-007）。
    """

    path = default_settings_path() if settings_path is None else settings_path
    return JsonOperatorSettingsRepository(path).load()


def load_answers(answers_path: Path | None) -> tuple[Answer, ...]:
    """運用者の回答（`answers.json`、DAT-009）を返す。パスを省略すれば回答なしとする。

    回答は個人名を含むため、イベントのフォルダ（Git管理外）に置いてパスで渡す（DAT-001）。
    """

    if answers_path is None:
        return ()
    return JsonAnswersRepository(answers_path).load()


def create_team_builder(rules: KvKRules | None = None) -> TeamBuilder:
    """同じ編成ルールを共有する既定の部品で、CLI向けのTeamBuilderを組み立てる。"""

    resolved = rules if rules is not None else default_rules()
    return TeamBuilder(
        parser=MarkdownMemberParser(),
        build_team_plan=BuildTeamPlan(
            rules=resolved,
            optimizer=MembershipOptimizer(resolved),
            validator=TeamPlanValidator(resolved),
        ),
        exporter=TeamPlanMarkdownExporter(resolved),
    )

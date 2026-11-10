"""KvKチームMarkdownを生成するCLIエントリーポイント。

終了コード（ADR 0035）:

- 0: 編成を出力した
- 2: 入力のエラー（ファイル、参加者一覧、チームマスタ、運用者の指定、回答）と、必須条件を満たす編成が
  ないことの証明
- 3: 運用者の回答が要る。番号付きの質問（FRM-075）を標準エラーへ出し、出力を書かない
- 4: 時間切れ。探索の制限内に結果を確定できなかった
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from kvk_team.interfaces.cli.composition import (
    create_team_builder,
    default_rules,
    default_specification,
    load_answers,
)
from kvk_team.interfaces.cli.team_builder import TeamBuilder
from kvk_team.team_building.adapters.input.markdown_member_parser import ParseError
from kvk_team.team_building.adapters.optimization.errors import OptimizationError
from kvk_team.team_building.adapters.output.shortfall_question_text import (
    render_questions,
)
from kvk_team.team_building.adapters.persistence.json_answers_repository import (
    AnswersLoadError,
)
from kvk_team.team_building.adapters.persistence.json_operator_settings_repository import (  # noqa: E501
    OperatorSettingsLoadError,
)
from kvk_team.team_building.adapters.persistence.json_team_master_repository import (
    TeamMasterLoadError,
)
from kvk_team.team_building.application.build_team_plan import (
    BuildError,
    LowerBoundShortfallError,
)
from kvk_team.team_building.application.ports import SearchTimeoutError
from kvk_team.team_building.domain.specification import SpecificationError

EXIT_INPUT_ERROR = 2
"""入力のエラーと、必須条件を満たす編成がないことの証明。"""
EXIT_ANSWER_REQUIRED = 3
"""運用者の回答が要る（番号付きの質問を示した）。"""
EXIT_TIMEOUT = 4
"""時間切れ。"""


def create_argument_parser() -> argparse.ArgumentParser:
    """コマンドライン引数Parserを生成する。"""

    parser = argparse.ArgumentParser(
        description="KvK参加者一覧からチーム編成を生成します。"
    )
    parser.add_argument("input", type=Path, help="参加者一覧Markdownのパス")
    parser.add_argument("output", type=Path, help="出力Markdownのパス")
    parser.add_argument(
        "--team-master",
        type=Path,
        default=None,
        help="チームマスタJSON（戦闘時間と出撃人数の上限）のパス。省略すると同梱の例を使う",
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=None,
        help=(
            "運用者の指定（settings.json。リーダー一覧）のパス。"
            "省略すると同梱の架空の例を使う"
        ),
    )
    parser.add_argument(
        "--answers",
        type=Path,
        default=None,
        help=(
            "番号付きの質問への回答（answers.json。遅れて出撃させる隊と応援先）のパス。"
            "省略すると回答なしで編成する"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """参加者一覧を読み込み、チームを編成してUTF-8 Markdownへ出力する。"""

    argument_parser = create_argument_parser()
    args = argument_parser.parse_args(argv)
    if args.settings is None:
        print(
            "注意: --settingsの指定がないため、同梱の例（架空のリーダー一覧）で編成します。"
            "本物の編成ではイベントのフォルダのsettings.jsonを--settingsで指定してください。",
            file=sys.stderr,
        )
    try:
        source = args.input.read_text(encoding="utf-8")
        specification = default_specification(args.settings)
        answers = load_answers(args.answers)
        builder: TeamBuilder = create_team_builder(default_rules(args.team_master))
        result = builder.build(source, specification, answers)
        args.output.write_text(result, encoding="utf-8")
    except LowerBoundShortfallError as error:
        argument_parser.exit(
            status=EXIT_ANSWER_REQUIRED, message=render_questions(error)
        )
    except SearchTimeoutError as error:
        argument_parser.exit(status=EXIT_TIMEOUT, message=f"エラー: {error}\n")
    except (
        OSError,
        ParseError,
        OptimizationError,
        BuildError,
        TeamMasterLoadError,
        OperatorSettingsLoadError,
        AnswersLoadError,
        SpecificationError,
    ) as error:
        argument_parser.exit(status=EXIT_INPUT_ERROR, message=f"エラー: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

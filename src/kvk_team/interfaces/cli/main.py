"""KvKチームMarkdownを生成するCLIエントリーポイント。"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from kvk_team.interfaces.cli.composition import create_team_builder, default_rules
from kvk_team.interfaces.cli.team_builder import TeamBuilder
from kvk_team.team_building.adapters.input.markdown_member_parser import ParseError
from kvk_team.team_building.adapters.optimization.errors import OptimizationError
from kvk_team.team_building.adapters.persistence.json_team_master_repository import (
    TeamMasterLoadError,
)
from kvk_team.team_building.application.build_team_plan import BuildError


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
        help="チームマスタJSONのパス。省略すると同梱の例を使う",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """参加者一覧を読み込み、チームを編成してUTF-8 Markdownへ出力する。"""

    argument_parser = create_argument_parser()
    args = argument_parser.parse_args(argv)
    if args.team_master is None:
        print(
            "注意: --team-masterの指定がないため、同梱の例（架空の集結主と役割）で編成します。"
            "本物の編成では--team-masterで本物のチームマスタを指定してください。",
            file=sys.stderr,
        )
    try:
        source = args.input.read_text(encoding="utf-8")
        builder: TeamBuilder = create_team_builder(default_rules(args.team_master))
        result = builder.build(source)
        args.output.write_text(result, encoding="utf-8")
    except (
        OSError,
        ParseError,
        OptimizationError,
        BuildError,
        TeamMasterLoadError,
    ) as error:
        argument_parser.exit(status=2, message=f"エラー: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

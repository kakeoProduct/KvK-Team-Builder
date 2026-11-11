"""参加者一覧から編成Markdownを生成し、運用者向けの要約と前回との差分を表示する。

編成または表示を変更したときに、テスト成功だけでなく実際の出力が運用上読めることを
確かめるための補助Scriptである。出力は既定でGit管理外の`tmp/preview/`へ書き、
再実行時は直前の出力を`*.previous.md`へ退避して差分を示す。CP-SATの探索は時間制限に
左右されるため、差分は確認材料として表示し、合否判定には使用しない。
"""

from __future__ import annotations

import argparse
import difflib
import sys
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# editable installは元の作業ツリーの`src`を指すため、worktreeで実行すると変更前のコードで
# 編成してしまう。このScriptと同じ作業ツリーの`src`を先に読む。
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from kvk_team.interfaces.cli.composition import (  # noqa: E402
    create_team_builder,
    default_rules,
    default_specification,
    load_answers,
)
from kvk_team.interfaces.cli.main import (  # noqa: E402
    EXIT_ANSWER_REQUIRED,
    EXIT_INPUT_ERROR,
    EXIT_TIMEOUT,
)
from kvk_team.team_building.adapters.input.markdown_member_parser import ParseError  # noqa: E402
from kvk_team.team_building.adapters.optimization.errors import OptimizationError  # noqa: E402
from kvk_team.team_building.adapters.output.shortfall_question_text import (  # noqa: E402
    render_questions,
)
from kvk_team.team_building.adapters.persistence.json_answers_repository import (  # noqa: E402
    AnswersLoadError,
)
from kvk_team.team_building.adapters.persistence.json_operator_settings_repository import (  # noqa: E402, E501
    OperatorSettingsLoadError,
)
from kvk_team.team_building.adapters.persistence.json_team_master_repository import (  # noqa: E402
    TeamMasterLoadError,
)
from kvk_team.team_building.application.build_team_plan import (  # noqa: E402
    BuildError,
    LowerBoundShortfallError,
)
from kvk_team.team_building.application.ports import SearchTimeoutError  # noqa: E402
from kvk_team.team_building.domain.specification import SpecificationError  # noqa: E402

DEFAULT_INPUT = PROJECT_ROOT / "sample" / "参加者一覧.md"
DEFAULT_OUTPUT = PROJECT_ROOT / "tmp" / "preview" / "チーム編成.md"
SELF_CHECK_HEADING = "## 自己チェック"
REQUIRED_OK_LINE = "- 必須条件: OK"

Build = Callable[[str], str]


def summarize(markdown: str) -> str:
    """自己チェックと警告詳細の節を返す。"""

    start = markdown.find(SELF_CHECK_HEADING)
    if start < 0:
        return "自己チェックの節が見つかりません。"
    return markdown[start:].strip()


def compare(previous: str, current: str) -> str:
    """変化した行だけを統一差分形式で返す。変化がなければ空文字を返す。"""

    lines = difflib.unified_diff(
        previous.splitlines(),
        current.splitlines(),
        fromfile="前回",
        tofile="今回",
        n=0,
        lineterm="",
    )
    return "\n".join(lines)


def _default_build(
    seconds: float | None, settings: Path | None, answers_path: Path | None
) -> Build:
    """既定ルールのTeamBuilderと運用者の指定、回答で生成する関数を返す。

    `settings`を省略すると同梱の架空のリーダー一覧を使い、`answers_path`を省略すると回答なしとする。
    """

    rules = (
        default_rules()
        if seconds is None
        else replace(default_rules(), maximum_optimization_seconds=seconds)
    )
    specification = default_specification(settings)
    answers = load_answers(answers_path)
    builder = create_team_builder(rules)
    return lambda source: (
        builder.build(
            source, specification, answers, created_at=datetime.now().astimezone()
        ).markdown
    )


def _use_utf8_output() -> None:
    """Windows CIなど非UTF-8のConsoleでも日本語の出力で失敗しないようにする。"""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def create_argument_parser() -> argparse.ArgumentParser:
    """確認Scriptの引数Parserを生成する。"""

    parser = argparse.ArgumentParser(
        description="編成Markdownを生成し、自己チェックと前回との差分を表示します。"
    )
    parser.add_argument(
        "--input", type=Path, default=DEFAULT_INPUT, help="参加者一覧Markdownのパス"
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT, help="出力Markdownのパス"
    )
    parser.add_argument(
        "--seconds",
        type=float,
        help="最適化の制限時間（秒）。省略時は編成ルールの既定値（30秒）を使う",
    )
    parser.add_argument(
        "--settings",
        type=Path,
        help="運用者の指定（settings.json）のパス。省略時は同梱の架空のリーダー一覧を使う",
    )
    parser.add_argument(
        "--answers",
        type=Path,
        help="番号付きの質問への回答（answers.json）のパス。省略時は回答なしで編成する",
    )
    return parser


def main(argv: Sequence[str] | None = None, build: Build | None = None) -> int:
    """生成、退避、要約、差分表示を行い、終了コードを返す。"""

    _use_utf8_output()
    args = create_argument_parser().parse_args(argv)
    try:
        builder = build or _default_build(args.seconds, args.settings, args.answers)
        source = args.input.read_text(encoding="utf-8")
        markdown = builder(source)
    except LowerBoundShortfallError as error:
        print(render_questions(error), file=sys.stderr, end="")
        return EXIT_ANSWER_REQUIRED
    except SearchTimeoutError as error:
        print(f"エラー: {error}", file=sys.stderr)
        return EXIT_TIMEOUT
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
        print(f"エラー: {error}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    output: Path = args.output
    previous_path = output.with_name(f"{output.stem}.previous{output.suffix}")
    previous = None
    if output.is_file():
        previous = output.read_text(encoding="utf-8")
        previous_path.write_text(previous, encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")

    print(f"出力: {output}")
    print()
    print(summarize(markdown))
    print()
    if previous is None:
        print("前回の出力がないため差分はありません。")
    else:
        difference = compare(previous, markdown)
        print(f"前回（{previous_path.name}）との差分:")
        print(difference or "変化はありません。")
    return 0 if REQUIRED_OK_LINE in markdown else 1


if __name__ == "__main__":
    raise SystemExit(main())

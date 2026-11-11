"""KvKチームMarkdownを生成するCLIエントリーポイント。

出力のフォルダの`<実行の時刻>/`へ、編成のMarkdownと編成のJSONを上書きせずに書く（DAT-008、ADR 0036）。

終了コード（ADR 0035）:

- 0: 編成を出力した
- 2: 入力のエラー（ファイル、出力のフォルダ、参加者一覧、チームマスタ、運用者の指定、回答、前回の編成）と、
  必須条件を満たす編成がないことの証明
- 3: 運用者の回答が要る。番号付きの質問（FRM-075）を標準エラーへ出し、出力を書かない
- 4: 時間切れ。探索の制限内に結果を確定できなかった
"""

import argparse
import sys
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path

from kvk_team.interfaces.cli.composition import (
    create_team_builder,
    default_rules,
    default_specification,
    load_answers,
    load_previous_plan,
)
from kvk_team.interfaces.cli.run_output import (
    MARKDOWN_NAME,
    PLAN_JSON_NAME,
    write_run_output,
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
from kvk_team.team_building.adapters.persistence.json_plan_record_repository import (
    PlanRecordLoadError,
    render_plan_record,
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


def _tolerate_unencodable_stdout() -> None:
    """標準出力で表せない文字を退避して書き、成功した実行を例外で終えないようにする。

    Windowsで標準出力をファイルやパイプへ送ると、符号化がcp932やcp1252になり、日本語やパスの文字を
    表せないことがある。標準エラーは既定で退避する。
    """

    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="backslashreplace")


def _output_dir_problem(output_dir: Path) -> str | None:
    """編成の前に分かる出力のフォルダの誤りを、利用者向けの文で返す。誤りがなければNoneを返す。

    `.md`で終わるパスは、以前の版の出力が残っていても、置き方が変わったことを先に示す（利用者の決定1、
    作成者の仮定A-42の(5)）。
    """

    if output_dir.suffix.lower() == ".md":
        return (
            f"エラー: 出力先には出力のフォルダを指定してください: {output_dir}\n"
            "編成のMarkdownとJSONは、<出力のフォルダ>/<実行の時刻>/へ上書きせずに書きます"
            "（例: <イベントのフォルダ>/output）。\n"
        )
    try:
        is_file = output_dir.exists() and not output_dir.is_dir()
    except OSError as error:
        return f"エラー: 出力のフォルダを確かめられません: {output_dir}: {error}\n"
    if is_file:
        return f"エラー: 出力のフォルダがフォルダではありません: {output_dir}\n"
    return None


def local_now() -> datetime:
    """実行した計算機の現地時刻を、時差付きで返す（DAT-002）。"""

    return datetime.now().astimezone()


def create_argument_parser() -> argparse.ArgumentParser:
    """コマンドライン引数Parserを生成する。"""

    parser = argparse.ArgumentParser(
        description="KvK参加者一覧からチーム編成を生成します。"
    )
    parser.add_argument("input", type=Path, help="参加者一覧Markdownのパス")
    parser.add_argument(
        "output",
        type=Path,
        help=(
            "出力のフォルダ（例: <イベントのフォルダ>/output）。"
            f"<出力のフォルダ>/<実行の時刻>/へ{MARKDOWN_NAME}と{PLAN_JSON_NAME}を書く"
        ),
    )
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
    parser.add_argument(
        "--previous",
        type=Path,
        default=None,
        help=(
            f"前回の編成（共有した回の{PLAN_JSON_NAME}）のパス。"
            "この版では読み込みと今回の参加者一覧との照合だけに使う"
        ),
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    clock: Callable[[], datetime] = local_now,
) -> int:
    """参加者一覧を読み込み、チームを編成して、出力のフォルダへMarkdownとJSONを書く。

    `clock`は実行の時刻を時差付きで返す。テストでは固定した時刻を渡す。
    """

    _tolerate_unencodable_stdout()
    argument_parser = create_argument_parser()
    args = argument_parser.parse_args(argv)
    output_dir: Path = args.output
    problem = _output_dir_problem(output_dir)
    if problem is not None:
        argument_parser.exit(status=EXIT_INPUT_ERROR, message=problem)
    if args.settings is None:
        print(
            "注意: --settingsの指定がないため、同梱の例（架空のリーダー一覧）で編成します。"
            "本物の編成ではイベントのフォルダのsettings.jsonを--settingsで指定してください。",
            file=sys.stderr,
        )
    try:
        source = args.input.read_text(encoding="utf-8")
        previous_plan = load_previous_plan(args.previous)
        if previous_plan is not None:
            print(
                "注意: 前回の編成（--previous）は、この版では読み込みと今回の参加者一覧との照合だけに使い、"
                "編成には使いません（前回からの移動の数は今後の版で比べます）。",
                file=sys.stderr,
            )
        specification = default_specification(args.settings, previous_plan)
        answers = load_answers(args.answers)
        builder: TeamBuilder = create_team_builder(default_rules(args.team_master))
        created_at = clock()
        result = builder.build(source, specification, answers, created_at=created_at)
        folder = write_run_output(
            output_dir, created_at, result.markdown, render_plan_record(result.record)
        )
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
        PlanRecordLoadError,
        SpecificationError,
    ) as error:
        argument_parser.exit(status=EXIT_INPUT_ERROR, message=f"エラー: {error}\n")
    if result.previous_unmatched:
        print(
            f"注意: 前回の編成の{result.previous_unmatched}人が、"
            "今回の参加者一覧（名前と同盟の組）にいません。",
            file=sys.stderr,
        )
    print(f"出力: {folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

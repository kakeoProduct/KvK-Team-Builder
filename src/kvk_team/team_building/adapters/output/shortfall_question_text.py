"""下限の不足について運用者へ示す、番号付きの質問の文（FRM-075、FRM-090）。

画面（UI-008）ができるまで、CLIはこの文を標準エラーへ出し、終了コード3で終える（ADR 0035）。
回答には質問の番号ではなく、問いの対象の（隊、時間帯）と指定そのものを書く（作成者の仮定A-41）。
"""

from kvk_team.team_building.application.build_team_plan import (
    LowerBoundShortfallError,
    ShortfallQuestion,
)
from kvk_team.team_building.domain.team import (
    EXTENSION_BOUNDARY_MINUTES,
    FIRST_SUPPORTED_TEAM,
    TOP_TEAM_COUNT,
    team_name,
)
from kvk_team.team_building.domain.validation import format_clock


def render_questions(error: LowerBoundShortfallError) -> str:
    """番号付きの質問と注記を、運用者が回答を書ける文にして返す。"""

    lines = [
        "運用者の判断が要るため、編成を出力しません。",
        f"延長境界時刻（{format_clock(EXTENSION_BOUNDARY_MINUTES)}）より前に、"
        "所属メンバーが参加せず休止になる隊があります。",
        "",
    ]
    for question in error.questions:
        lines.extend(_render_question(question))
        lines.append("")
    lines.extend(f"注記: {note}" for note in error.notes)
    return "\n".join(lines).rstrip() + "\n"


def _render_question(question: ShortfallQuestion) -> list[str]:
    """1つの問いを描画する。"""

    times = "、".join(format_clock(slot.start_minutes) for slot in question.time_slots)
    name = team_name(question.team_number)
    heading = f"問{question.number}: {name} {times}"
    if question.opening:
        heading += "（序盤）"
    lines = [f"{heading}: 所属メンバーが参加しておらず休止になります。"]
    if not question.answerable:
        lines.append(
            "  この版では回答できません。参加者一覧かリーダー一覧を見直してください。"
            "隊数を減らす、明示して許すの選択肢は今後の版で示します。"
        )
        return lines
    first = format_clock(question.time_slots[0].start_minutes)
    lines.extend(
        (
            f"  遅れて出撃させる隊（第{TOP_TEAM_COUNT + 1}隊以降）、出撃開始時刻、出撃開始前に"
            f"参加するメンバーの応援先（第{FIRST_SUPPORTED_TEAM}隊以降）を、回答のファイル"
            "（answers.json）に書き、--answersで渡して再実行してください。",
            "  回答の対象: "
            f'"target": {{"team": {question.team_number}, "time": "{first}"}}'
            + (
                "（直したい時刻を1つ書いてください。書いた時刻の休止がなくなる回答だけを"
                "受け入れ、残りの時刻は次の実行で改めて問います）"
                if len(question.time_slots) > 1
                else ""
            ),
            "  受け入れられる回答がなければ、参加者一覧かリーダー一覧を見直してください。"
            "隊数を減らす、明示して許すの選択肢は今後の版で示します。",
        )
    )
    return lines

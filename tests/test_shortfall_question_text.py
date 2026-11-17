"""番号付きの質問の文のテスト（FRM-075、FRM-090、作成者の仮定A-41）。"""

from kvk_team.team_building.adapters.output.shortfall_question_text import (
    render_questions,
)
from kvk_team.team_building.application.build_team_plan import (
    LowerBoundShortfallError,
    ShortfallQuestion,
)
from kvk_team.team_building.domain.plan import TimeSlot

H21 = 21 * 60
H2130 = H21 + 30
H23 = 23 * 60


def _slot(start: int) -> TimeSlot:
    return TimeSlot(start, start + 30)


def _error(notes: tuple[str, ...] = ()) -> LowerBoundShortfallError:
    return LowerBoundShortfallError(
        shortfalls=(),
        questions=(
            ShortfallQuestion(1, 7, (_slot(H21), _slot(H2130)), opening=True),
            ShortfallQuestion(2, 8, (_slot(H23),), opening=False),
        ),
        notes=notes,
    )


def test_questions_are_numbered_with_team_times_and_answer_target() -> None:
    """問いに番号を付け、隊と時刻、回答に書く対象を示す（FRM-075）。"""

    text = render_questions(_error())

    assert "問1: 第7隊 21:00、21:30（序盤）" in text
    assert '"target": {"team": 7, "time": "21:00"}' in text
    assert "--answers" in text
    assert "問2: 第8隊 23:00: 所属メンバー" in text
    assert "受け入れられる回答がなければ" in text
    assert "書いた時刻の休止がなくなる回答だけを受け入れ" in text


def test_question_outside_opening_says_it_cannot_be_answered_yet() -> None:
    """序盤以外の問いは、この版では回答できず見直しを求める（利用者の決定、2026-11-10）。"""

    text = render_questions(_error())
    second = text[text.index("問2:") :]

    assert "この版では回答できません" in second
    assert "参加者一覧かリーダー一覧を見直してください" in second
    assert "target" not in second


def test_notes_follow_questions() -> None:
    """回答の扱いの注記を、問いの後に「注記:」の行で示す（OUT-007）。"""

    text = render_questions(_error(("第7隊 21:00への回答は受け入れませんでした",)))

    assert text.index("問2:") < text.index(
        "注記: 第7隊 21:00への回答は受け入れませんでした"
    )

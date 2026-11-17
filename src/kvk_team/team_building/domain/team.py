"""隊の番号と、運用で変えない固定値（ADR 0034）。

隊の数はリーダーの人数で決まり、リーダー一覧の番号が隊の番号になる（FRM-001）。
上位隊の数と人数、延長境界時刻、出撃人数の下限の基本、30分単位の時間帯（ADR 0034）と、序盤の長さ、
応援を受けられる最初の隊（ADR 0035）は利用者が決めた固定値であり、運用値（チームマスタ、運用者の指定）
ではなくドメインの定数として持つ。
戦力関係は固定値ではなく、分割案の3でFRM-027へ置き換えるまで維持する現行の規則である。
"""

from kvk_team.team_building.domain.member import MINUTES_PER_HOUR

SLOT_MINUTES = 30
"""時間帯の長さ（分）。利用者が決めた固定値で、設定では変えない。"""

TOP_TEAM_COUNT = 3
"""上位隊（第1〜3隊）の数。固定をなくさない（FRM-026）。"""

TOP_TEAM_SIZE = 8
"""上位隊のリーダーを含む人数（FRM-020）。リーダー不在の時間帯は1人少ない。"""

SORTIE_FLOOR = 8
"""出撃人数の下限の基本（FRM-031）。第4隊以降で下回ると警告にする。"""

EXTENSION_BOUNDARY_MINUTES = 24 * MINUTES_PER_HOUR
"""延長境界時刻（FRM-043）。これより前の休止は下限の不足として扱う（FRM-048）。"""

OPENING_MINUTES = MINUTES_PER_HOUR
"""序盤の長さ（FRM-040）。戦闘開始からの1時間で、利用者が決めた固定値（ADR 0035）。"""

FIRST_SUPPORTED_TEAM = 5
"""応援を受けられる最初の隊の番号（FRM-042）。第1〜4隊は応援を受けない。利用者が決めた固定値（ADR 0035）。"""

STRICTLY_STRONGER_PAIRS = ((1, 2),)
"""戦力で「>」を満たす上位隊の組（以前の`A > B`）。分割案の3まで維持する現行の規則で、
FRM-027の平均Gの比較へ置き換える。"""

AT_LEAST_AS_STRONG_PAIRS = ((2, 3),)
"""戦力で「>=」を満たす上位隊の組（現行の`B >= C`）。"""


def is_top_team(number: int) -> bool:
    """隊の番号が上位隊かを返す。"""

    return 1 <= number <= TOP_TEAM_COUNT


def can_start_late(number: int) -> bool:
    """運用者が遅れて出撃させてよい隊かを返す（FRM-041）。

    第1〜3隊は選べない。FIXの隊（FRM-072）も選べないが、FIXの指定は分割案の5で加える。
    """

    return not is_top_team(number)


def can_receive_support(number: int) -> bool:
    """応援を受けられる番号の隊かを返す（FRM-042）。出撃中か、上限に空きがあるかは見ない。"""

    return number >= FIRST_SUPPORTED_TEAM


def is_opening(slot_start_minutes: int, battle_start_minutes: int) -> bool:
    """時間帯が序盤（戦闘開始からの1時間、FRM-040）にあるかを返す。"""

    return (
        battle_start_minutes
        <= slot_start_minutes
        < battle_start_minutes + OPENING_MINUTES
    )


def team_name(number: int) -> str:
    """隊の番号を運用者向けの名前にする。"""

    return f"第{number}隊"

"""参加者と運用者の指定から、検証済みの所属固定の編成を作るユースケース。

運用者の回答（遅れて出撃する隊と応援先）は、次の手順で確かめる（旧Q-092、作成者の仮定A-41、ADR 0035）。

1. ほかの指定によって変わらない誤りは、最適化の前に入力のエラーにする（`check_answers`）
2. 回答なしで判定に使う編成を作る。対象の（隊、時間帯）が下限の不足でない回答は使わなかったと注記する
3. 残りの回答を、対象の隊の番号、時刻の順に1つずつ加え、対象の不足をなくし、ほかの（隊、時間帯）に
   不足を新しく生まない編成が見つかれば受け入れる。書いた順によらない（FRM-090の性質(5)）。
   見つかった編成に不足が残り、最適性を示せなければ時間切れのエラーとする（FRM-090の性質(6)）
4. 受け入れた指定で編成し、不足が残れば番号付きの質問（FRM-075）を示して止める

アプリは回答を覚えない。運用者は同じファイルへ回答を足していき、毎回この手順で確かめ直す。
"""

from collections.abc import Sequence
from dataclasses import dataclass

from kvk_team.team_building.application.ports import (
    ProvenInfeasible,
    SearchTimeoutError,
    ShortfallKey,
    TeamPlanOptimizerPort,
    TeamPlanValidatorPort,
)
from kvk_team.team_building.domain.answers import (
    Answer,
    check_answers,
    ordered_answers,
)
from kvk_team.team_building.domain.member import Member
from kvk_team.team_building.domain.plan import TeamPlan, TimeSlot
from kvk_team.team_building.domain.rules import KvKRules
from kvk_team.team_building.domain.specification import (
    OperatorSpecification,
    SpecificationError,
    resolve_leaders,
)
from kvk_team.team_building.domain.team import is_opening, team_name
from kvk_team.team_building.domain.validation import (
    ValidatedTeamPlan,
    ValidationIssue,
    ValidationReport,
    format_clock,
)


class BuildError(RuntimeError):
    """必須条件を満たす編成を出力できない場合に送出する。"""


class NoValidPlanError(BuildError):
    """必須条件を満たす編成がないとOptimizerが証明した場合に送出する。"""


@dataclass(frozen=True, slots=True)
class ShortfallQuestion:
    """下限の不足について運用者へ示す、番号付きの問い（FRM-075、FRM-090）。

    同じ隊で示す選択肢が同じ（隊、時間帯）を1つの問いにまとめる。この版の選択肢は、序盤の
    （隊、時間帯）へ遅れて出撃する隊と応援先を回答に書くことだけで、序盤以外の問いには
    答えられない（利用者の決定、2026-11-10）。隊数を減らす（FRM-005）と明示して許す（FRM-046）は
    分割案の3と4で加える。
    """

    number: int
    team_number: int
    time_slots: tuple[TimeSlot, ...]
    opening: bool
    """序盤（FRM-040）の問いか。序盤の問いには遅れて出撃させる回答を書ける。"""

    @property
    def answerable(self) -> bool:
        """この版で回答を書ける問いかを返す。"""

        return self.opening


class LowerBoundShortfallError(BuildError):
    """延長境界時刻より前の休止が避けられないと示せた場合に送出する（FRM-048、FRM-090）。

    運用者の回答が要るため、番号付きの質問（`questions`）と、回答の扱いの注記（`notes`）を持つ。
    CLIは質問を示して終了コード3で終える。6人以下の禁止（FRM-039）と序盤の8人（FRM-040）は
    分割案の3と4で加える。
    """

    def __init__(
        self,
        shortfalls: Sequence[ValidationIssue],
        questions: Sequence[ShortfallQuestion],
        notes: Sequence[str] = (),
    ) -> None:
        self.shortfalls = tuple(shortfalls)
        self.questions = tuple(questions)
        self.notes = tuple(notes)
        lines = "\n".join(f"- {_describe(issue)}" for issue in self.shortfalls)
        super().__init__(
            "延長境界時刻より前に休止になる隊があるため、編成を出力しません。"
            "運用者の判断が要ります。\n" + lines
        )


class ShortfallUndeterminedError(BuildError, SearchTimeoutError):
    """下限の不足が避けられないかを、探索の制限内に確定できなかった場合に送出する。

    最適だと示せない編成で下限の不足を判定すると、避けられる不足を運用者へ問うことになる。
    このため時間切れのエラーとして扱う（FRM-090の性質(6)、ADR 0019、ADR 0035）。
    """


_UNDETERMINED_MESSAGE = (
    "探索の制限内に最適な編成を示せなかったため、休止が避けられないかを"
    "確定できません。時間切れのため、負荷の低い環境で再実行するか、"
    "制限時間を延ばしてください"
)


_UNUSED_SUFFIX = "使いませんでした"


def _unused_note(answer: Answer) -> str:
    """対象が下限を満たしたため使わなかった回答の注記を返す。"""

    return (
        f"{answer.describe()}は、対象の隊と時間帯が下限を満たしているか出撃開始前のため、"
        + _UNUSED_SUFFIX
    )


def _describe(issue: ValidationIssue) -> str:
    """検証結果へ隊と時刻を付ける。"""

    parts = []
    if issue.time_slot is not None:
        parts.append(format_clock(issue.time_slot.start_minutes))
    if (
        issue.team_number is not None
        and team_name(issue.team_number) not in issue.message
    ):
        parts.append(team_name(issue.team_number))
    prefix = " ".join(parts)
    return f"{prefix}: {issue.message}" if prefix else issue.message


def shortfall_questions(
    shortfalls: Sequence[ValidationIssue], battle_start_minutes: int
) -> tuple[ShortfallQuestion, ...]:
    """下限の不足を、隊と序盤かどうかでまとめた番号付きの問いにする。

    並びは隊の番号、最初の時刻の順とし、1から番号を振る。
    """

    grouped: dict[tuple[int, bool], list[TimeSlot]] = {}
    for issue in shortfalls:
        if issue.team_number is None or issue.time_slot is None:
            continue
        opening = is_opening(issue.time_slot.start_minutes, battle_start_minutes)
        grouped.setdefault((issue.team_number, opening), []).append(issue.time_slot)
    ordered = sorted(
        grouped.items(),
        key=lambda item: (item[0][0], min(slot.start_minutes for slot in item[1])),
    )
    return tuple(
        ShortfallQuestion(
            number=position,
            team_number=team,
            time_slots=tuple(sorted(set(slots), key=lambda slot: slot.start_minutes)),
            opening=opening,
        )
        for position, ((team, opening), slots) in enumerate(ordered, start=1)
    )


@dataclass(frozen=True, slots=True)
class _Attempt:
    """Validatorが必須条件OKか、下限の不足だけと判定した編成。"""

    plan: TeamPlan
    report: ValidationReport
    proven_optimal: bool

    @property
    def shortfall_keys(self) -> frozenset[ShortfallKey]:
        """下限の不足の（隊、時間帯）を返す。"""

        return frozenset(
            (issue.team_number, issue.time_slot.start_minutes)
            for issue in self.report.shortfalls
            if issue.team_number is not None and issue.time_slot is not None
        )


@dataclass(frozen=True, slots=True)
class BuildTeamPlan:
    """回答を確かめ、最適化と独立検証を繰り返し、必須条件を満たす編成だけを返す。

    入力形式と出力形式を扱わない。参加者、運用者の指定、回答はドメイン型で受け取り、
    結果は`ValidatedTeamPlan`で返す。
    """

    rules: KvKRules
    optimizer: TeamPlanOptimizerPort
    validator: TeamPlanValidatorPort

    def execute(
        self,
        members: Sequence[Member],
        specification: OperatorSpecification,
        answers: Sequence[Answer] = (),
    ) -> ValidatedTeamPlan:
        """Validatorが必須条件OKを返した編成を、検証済み編成として返す。

        リーダーが参加者一覧で1人に決まらない場合と、ほかの指定によって変わらない回答の誤りは、
        最適化の前に`SpecificationError`を送出する。
        """

        source_members = list(members)
        resolve_leaders(specification, source_members)
        event = self.rules.team_master.event_time
        check_answers(answers, source_members, specification, event)

        baseline = self._attempt(source_members, specification, None)
        if isinstance(baseline, ProvenInfeasible):
            raise NoValidPlanError(baseline.reason)
        if baseline.report.shortfalls and not baseline.proven_optimal:
            raise ShortfallUndeterminedError(_UNDETERMINED_MESSAGE)

        current = baseline
        accepted = specification
        rejected: list[tuple[Answer, str]] = []
        for answer in ordered_answers(answers):
            outcome = self._try_answer(
                source_members, accepted, current, baseline.shortfall_keys, answer
            )
            if isinstance(outcome, str):
                rejected.append((answer, outcome))
                continue
            accepted, current = outcome
        notes = self._final_notes(rejected, current.shortfall_keys)

        if current.report.is_valid:
            return ValidatedTeamPlan(
                plan=current.plan,
                report=current.report,
                proven_optimal=current.proven_optimal,
                notes=tuple(notes),
            )
        if not current.proven_optimal:
            raise ShortfallUndeterminedError(_UNDETERMINED_MESSAGE)
        raise LowerBoundShortfallError(
            current.report.shortfalls,
            shortfall_questions(current.report.shortfalls, event.start_minutes),
            notes,
        )

    @staticmethod
    def _final_notes(
        rejected: list[tuple[Answer, str]], final_keys: frozenset[ShortfallKey]
    ) -> tuple[str, ...]:
        """受け入れなかった回答の注記を、最後の編成で判定し直して返す。

        後の回答を受け入れて対象の不足が直った場合は、受け入れなかった理由ではなく、
        使わなかったと注記する（FRM-090の性質(3)、性質(6)「使わなかった指定の注記はその編成で
        判定する」）。受け入れた確認の編成は前の不足を新しく増やさないため、一度直った対象は
        最後の編成でも直っている。
        """

        notes: list[str] = []
        for answer, note in rejected:
            key = (answer.target_team, answer.target_slot_start)
            if key not in final_keys:
                note = _unused_note(answer)
            notes.append(note)
        return tuple(notes)

    def _try_answer(
        self,
        members: list[Member],
        accepted: OperatorSpecification,
        current: _Attempt,
        judged_keys: frozenset[ShortfallKey],
        answer: Answer,
    ) -> tuple[OperatorSpecification, _Attempt] | str:
        """回答を1つ加えて確かめる。受け入れれば指定と編成を、受け入れなければ注記を返す。

        `judged_keys`は回答なしの判定に使う編成の不足で、同じ指定で直った対象の注記を省く
        範囲に使う。
        """

        open_keys = current.shortfall_keys
        key = (answer.target_team, answer.target_slot_start)
        where = answer.describe()
        if key not in open_keys:
            if key in judged_keys and answer.late_start in accepted.late_starts:
                # 判定に使う編成で不足だった対象が、受け入れた指定と同じ指定で直った場合は、
                # その対象自身への指定で直ったものとし、注記しない（FRM-090の性質(3)）。
                return accepted, current
            return _unused_note(answer)
        if answer.late_start in accepted.late_starts:
            return (
                f"{where}は、先に受け入れた同じ指定では対象の休止が直らなかったため、"
                "受け入れませんでした"
            )
        try:
            trial_specification = accepted.with_late_start(answer.late_start)
        except SpecificationError:
            return (
                f"{where}は、先に受け入れた回答と同じ隊を遅れて出撃させる別の指定か、"
                "同じメンバーの応援を持つため、受け入れませんでした"
            )
        allowed = open_keys - {key}
        trial = self._attempt(members, trial_specification, allowed)
        if isinstance(trial, ProvenInfeasible):
            return (
                f"{where}は、対象の休止をなくし、ほかの隊と時間帯に休止を新しく生まない"
                f"編成がないため、受け入れませんでした（{trial.reason}）"
            )
        if not trial.shortfall_keys <= allowed:
            raise BuildError(
                "Optimizerが、休止を許した（隊、時間帯）の外に休止のある編成を返しました"
            )
        if trial.shortfall_keys and not trial.proven_optimal:
            # 不足が残る編成で最適性を示せなければ、後の回答の判定と問いがこの編成に
            # 左右されるため、時間切れのエラーとする（FRM-090の性質(6)）。
            raise ShortfallUndeterminedError(_UNDETERMINED_MESSAGE)
        return trial_specification, trial

    def _attempt(
        self,
        members: list[Member],
        specification: OperatorSpecification,
        allowed_shortfalls: frozenset[ShortfallKey] | None,
    ) -> _Attempt | ProvenInfeasible:
        """最適化と検証を繰り返し、必須条件OKか下限の不足だけの編成を返す。

        下限の不足とほかの必須条件エラーが混ざる候補は、Optimizerの誤りとして再試行する。
        """

        last_report: ValidationReport | None = None
        for _ in range(self.rules.maximum_validation_attempts):
            outcome = self.optimizer.optimize(
                members, specification, allowed_shortfalls
            )
            if isinstance(outcome, ProvenInfeasible):
                return outcome
            last_report = self.validator.validate(outcome.plan, members, specification)
            if last_report.is_valid or last_report.has_only_shortfalls:
                return _Attempt(outcome.plan, last_report, outcome.proven_optimal)

        issue_text = (
            "; ".join(issue.message for issue in last_report.issues)
            if last_report
            else "検証結果がありません"
        )
        raise BuildError(
            f"{self.rules.maximum_validation_attempts}回の再配置後も検証NGです: "
            f"{issue_text}"
        )

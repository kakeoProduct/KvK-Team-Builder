"""運用者の回答（`answers.json`、DAT-009）のJSON Repository。

境界は`application.ports.AnswersRepository`。回答は個人名を含むため、本物のファイルはイベントの
フォルダ（Git管理外）に置く（DAT-001、ADR 0029）。誤りのメッセージには名前を出さず、キーと位置だけを
示す。回答には質問の番号を書かず、問いの対象の（隊、時間帯）と指定そのものを書く（作成者の仮定A-41）。
アダプターは形式の変換だけを行い、回答の妥当性はドメインとアプリケーションが確かめる。
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kvk_team.team_building.adapters.persistence.json_operator_settings_repository import (  # noqa: E501
    parse_member_ref,
)
from kvk_team.team_building.adapters.persistence.json_team_master_repository import (
    JsonFields,
)
from kvk_team.team_building.domain.answers import Answer
from kvk_team.team_building.domain.specification import LateStart, SupportRef


class AnswersLoadError(ValueError):
    """運用者の回答を安全に読み込めない場合に送出する。"""


@dataclass(frozen=True, slots=True)
class JsonAnswersRepository:
    """`answers.json`から運用者の回答を構築するRepository。"""

    path: Path

    def load(self) -> tuple[Answer, ...]:
        """JSONを読み込み、回答を返す。UTF-8のBOMの有無の両方を受け付ける（DAT-002）。"""

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8-sig"))
            return parse_answers(raw)
        except UnicodeDecodeError as error:
            raise AnswersLoadError(
                f"運用者の回答をUTF-8として読めません: {self.path}"
            ) from error
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise AnswersLoadError(
                f"運用者の回答を読み込めません: {self.path}: {error}"
            ) from error


def parse_answers(raw: Any) -> tuple[Answer, ...]:
    """JSONオブジェクトを回答の一覧へ変換する。"""

    document = JsonFields(raw, "answers.json")
    document.reject_unknown(frozenset({"answers"}))
    return tuple(
        _answer(item, f"answersの{index}番目")
        for index, item in enumerate(document.items("answers"), start=1)
    )


def _answer(raw: Any, where: str) -> Answer:
    """1件の回答を変換する。"""

    fields = JsonFields(raw, where)
    fields.reject_unknown(frozenset({"target", "late_start"}))
    target = JsonFields(fields.value("target"), f"{where}のtarget")
    target.reject_unknown(frozenset({"team", "time"}))
    late = JsonFields(fields.value("late_start"), f"{where}のlate_start")
    late.reject_unknown(frozenset({"team", "start", "support"}))
    supports = (
        tuple(
            _support(item, f"{where}のlate_startのsupportの{index}番目")
            for index, item in enumerate(late.items("support"), start=1)
        )
        if isinstance(late.raw, dict) and "support" in late.raw
        else ()
    )
    try:
        late_start = LateStart(
            team=late.integer("team"),
            start_minutes=late.clock("start"),
            supports=supports,
        )
    except ValueError as error:
        raise ValueError(f"{where}: {error}") from error
    return Answer(
        target_team=target.integer("team"),
        target_slot_start=target.clock("time"),
        late_start=late_start,
    )


def _support(raw: Any, where: str) -> SupportRef:
    """1件の応援を変換する。"""

    fields = JsonFields(raw, where)
    fields.reject_unknown(frozenset({"member", "time", "team"}))
    return SupportRef(
        member=parse_member_ref(fields.value("member"), f"{where}のmember"),
        slot_start_minutes=fields.clock("time"),
        team=fields.integer("team"),
    )

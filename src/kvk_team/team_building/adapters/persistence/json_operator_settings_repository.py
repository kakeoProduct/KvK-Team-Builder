"""運用者の指定（`settings.json`、DAT-007）のJSON Repository。

境界は`application.ports.OperatorSpecificationRepository`。個人名を含むため、本物のファイルは
イベントのフォルダ（Git管理外）に置く（DAT-001、ADR 0029）。誤りのメッセージには
名前を出さず、キーと位置だけを示す。
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kvk_team.team_building.adapters.persistence.json_team_master_repository import (
    JsonFields,
)
from kvk_team.team_building.domain.specification import (
    MemberRef,
    OperatorSpecification,
)


class OperatorSettingsLoadError(ValueError):
    """運用者の指定を安全に読み込めない場合に送出する。"""


SUPPORTED_KEYS = frozenset({"leaders"})
"""この版で読む指定。"""

PLANNED_KEYS = frozenset(
    {
        "battle_start",
        "battle_end",
        "roster_received_at",
        "pin_team",
        "force_wait",
        "optional_wait",
        "apart_pairs",
        "together_pairs",
        "default_destination_alliance",
        "destination_overrides",
        "alliance_choices",
        "cooperator_destinations",
        "cooperator_alliance",
        "groups",
        "splittable_alliances",
        "overcap_limit",
        "group_member_cap",
        "alliance_member_cap",
        "alliance_power_targets",
    }
)
"""DAT-007にあり、後のIssueで実装する指定。黙って無視すると効いたと誤解されるため、エラーにする。"""


@dataclass(frozen=True, slots=True)
class JsonOperatorSettingsRepository:
    """`settings.json`から運用者の指定を構築するRepository。"""

    path: Path

    def load(self) -> OperatorSpecification:
        """JSONを読み込み、運用者の指定を返す。UTF-8のBOMの有無の両方を受け付ける（DAT-002）。"""

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8-sig"))
            return parse_operator_settings(raw)
        except UnicodeDecodeError as error:
            raise OperatorSettingsLoadError(
                f"運用者の指定をUTF-8として読めません: {self.path}"
            ) from error
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise OperatorSettingsLoadError(
                f"運用者の指定を読み込めません: {self.path}: {error}"
            ) from error


def parse_operator_settings(raw: Any) -> OperatorSpecification:
    """JSONオブジェクトを運用者の指定へ変換する。"""

    settings = JsonFields(raw, "settings")
    settings.reject_unknown(SUPPORTED_KEYS | PLANNED_KEYS)
    planned = sorted(set(raw) & PLANNED_KEYS)
    if planned:
        raise ValueError(
            "まだ対応していない指定があります: "
            + "、".join(planned)
            + "。この版では`leaders`だけを読みます"
        )
    leaders = tuple(
        _member_ref(item, f"leadersの{index}番目")
        for index, item in enumerate(settings.items("leaders"), start=1)
    )
    return OperatorSpecification(leaders=leaders)


def _member_ref(raw: Any, where: str) -> MemberRef:
    """`{"name": 名前, "alliance": 同盟}`をメンバーの指し方へ変換する。"""

    fields = JsonFields(raw, where)
    fields.reject_unknown(frozenset({"name", "alliance"}))
    # 項目の欠けと型の誤りは、JsonFieldsが位置を前置きして送出する。前置きを重ねないよう、
    # 値の検査（空の名前や同盟）だけを位置で包む。
    name = fields.string("name")
    alliance = fields.string("alliance")
    try:
        return MemberRef(name=name, alliance=alliance)
    except ValueError as error:
        raise ValueError(f"{where}: {error}") from error


def default_settings_path() -> Path:
    """同梱する架空の運用者の指定の例のパスを返す。"""

    return Path(__file__).with_name("settings.example.json")

"""Hypothesisの生成を決定的にする設定のテスト。"""

import ast
from pathlib import Path

from hypothesis import settings

HYPOTHESIS_PROFILE = "kvk-deterministic"
"""`tests/conftest.py`が登録して読み込むProfile名。"""

TESTS_DIRECTORY = Path(__file__).resolve().parent
DETERMINISM_SETTINGS = frozenset({"derandomize", "database", "deadline"})
"""テストごとに上書きすると、Profileによる決定性が崩れる設定。"""
SEED_DECORATORS = frozenset({"seed", "reproduce_failure"})
"""入力の並びを固定値で差し替えるため、コミットしないデコレーター。"""


def _called_name(call: ast.Call) -> str | None:
    """`name(...)`または`module.name(...)`の呼び出し名を返す。"""

    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _determinism_overrides(path: Path) -> list[str]:
    """1ファイル内で決定性の設定を上書きしている箇所を返す。"""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    overrides: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _called_name(node)
        location = f"{path.name}:{node.lineno}"
        if name == "settings":
            overrides.extend(
                f"{location}: settings({keyword.arg}=...)"
                for keyword in node.keywords
                if keyword.arg in DETERMINISM_SETTINGS
            )
        elif name in SEED_DECORATORS:
            overrides.append(f"{location}: {name}(...)")
    return overrides


def test_hypothesis_profile_is_deterministic() -> None:
    """入力の固定、失敗例の非保存、制限時間なしをテスト全体へ適用する。

    HypothesisはCI上で同じ値を持つ`ci` Profileを自動で読み込むため、値だけでなく
    Profile名も確かめ、`tests/conftest.py`の読み込みが壊れた場合にCIでも失敗させる。
    """

    current = settings.default

    assert settings.get_current_profile_name() == HYPOTHESIS_PROFILE
    assert current.derandomize is True
    assert current.database is None
    assert current.deadline is None
    assert current.print_blob is True


def test_hypothesis_profile_does_not_inherit_ci_profile() -> None:
    """健全性検査の設定を、CIかどうかで変えない。

    親を指定しないProfileは読み込み時点の既定値を引き継ぎ、CIでは`ci` Profileの
    `too_slow`の抑止が混ざるため、組み込みの`default` Profileを親にする。
    """

    assert settings.default.suppress_health_check == ()


def test_tests_do_not_override_determinism_settings() -> None:
    """テストごとに入力の固定、失敗例の保存、制限時間、乱数の種を上書きしない。"""

    overrides = [
        override
        for path in sorted(TESTS_DIRECTORY.glob("*.py"))
        for override in _determinism_overrides(path)
    ]

    assert overrides == []


def test_determinism_override_detection(tmp_path: Path) -> None:
    """上書きの検出が、引数付きの`settings`と種のデコレーターを見つける。"""

    sample = tmp_path / "test_sample.py"
    sample.write_text(
        "from hypothesis import seed, settings\n"
        "@settings(max_examples=5)\n"
        "def test_allowed(): ...\n"
        "@settings(deadline=500, derandomize=False)\n"
        "@seed(1)\n"
        "def test_forbidden(): ...\n",
        encoding="utf-8",
    )

    assert _determinism_overrides(sample) == [
        "test_sample.py:4: settings(deadline=...)",
        "test_sample.py:4: settings(derandomize=...)",
        "test_sample.py:5: seed(...)",
    ]

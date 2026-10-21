"""ADR 0021のパッケージ構成と依存方向を、importの静的解析で検証する。"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
PACKAGE_ROOT = SOURCE_ROOT / "kvk_team"
CONTEXTS = ("team_building", "battle_timing")
LEGACY_PACKAGES = (
    "models",
    "config",
    "parser",
    "optimizer",
    "validator",
    "exporter",
    "cli",
)
INNER_FORBIDDEN = (
    "json",
    "pathlib",
    "argparse",
    "os",
    "io",
    "shutil",
    "subprocess",
    "socket",
    "http",
    "urllib",
    "sqlite3",
    "csv",
    "tomllib",
    "importlib",
    "ortools",
    "django",
    "ninja",
)
"""domainとapplicationが使わない入出力、外部形式、動的import、外部ライブラリ。"""


def _module_name(path: Path) -> str:
    relative = path.relative_to(SOURCE_ROOT).with_suffix("")
    parts = relative.parts[:-1] if relative.name == "__init__" else relative.parts
    return ".".join(parts)


def _imports(path: Path) -> list[str]:
    """ファイルがimportするモジュール名を返す。相対importは許可しない。"""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"相対importは使わない: {path}"
            if node.module and node.module != "__future__":
                names.append(node.module)
                # `from kvk_team import interfaces`の形も、取り込む名前で判定する
                names.extend(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def _python_files(directory: Path) -> list[Path]:
    return sorted(directory.rglob("*.py")) if directory.is_dir() else []


def _is_standard_library(module: str) -> bool:
    return module.split(".")[0] in sys.stdlib_module_names


def _within(module: str, package: str) -> bool:
    return module == package or module.startswith(f"{package}.")


def test_legacy_top_level_packages_are_removed() -> None:
    """技術レイヤー別の旧パッケージを残さず、新しい名前空間だけを置く。"""

    assert (PACKAGE_ROOT / "team_building").is_dir()
    for legacy in LEGACY_PACKAGES:
        # バージョン管理で消えずに残る`__pycache__`だけなら、削除済みとみなす
        leftovers = [
            path
            for path in (SOURCE_ROOT / legacy).rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        ]
        assert not leftovers, leftovers


def test_source_root_has_only_the_application_namespace() -> None:
    """src直下のPythonパッケージは`kvk_team`だけにする。"""

    packages = {path.parent.name for path in SOURCE_ROOT.glob("*/__init__.py")}
    assert packages == {"kvk_team"}


def test_domain_depends_only_on_standard_library_and_itself() -> None:
    """domainは標準ライブラリと同じコンテキストのdomainだけをimportする。"""

    domain_files = _python_files(PACKAGE_ROOT / "team_building" / "domain")
    assert domain_files
    for context in CONTEXTS:
        own_domain = f"kvk_team.{context}.domain"
        for path in _python_files(PACKAGE_ROOT / context / "domain"):
            for module in _imports(path):
                assert module.split(".")[0] not in INNER_FORBIDDEN, (path, module)
                assert _is_standard_library(module) or _within(module, own_domain), (
                    path,
                    module,
                )


def test_application_depends_only_on_inner_layers() -> None:
    """applicationは標準ライブラリ、同じコンテキストのdomainとapplicationだけをimportする。"""

    application_files = _python_files(PACKAGE_ROOT / "team_building" / "application")
    assert application_files
    for context in CONTEXTS:
        allowed = (
            f"kvk_team.{context}.domain",
            f"kvk_team.{context}.application",
        )
        for path in _python_files(PACKAGE_ROOT / context / "application"):
            for module in _imports(path):
                assert module.split(".")[0] not in INNER_FORBIDDEN, (path, module)
                assert _is_standard_library(module) or any(
                    _within(module, package) for package in allowed
                ), (path, module)


def test_contexts_do_not_import_each_other_or_interfaces() -> None:
    """コンテキストどうしは互いをimportせず、interfacesにも依存しない。"""

    for context in CONTEXTS:
        others = [f"kvk_team.{other}" for other in CONTEXTS if other != context]
        forbidden = [*others, "kvk_team.interfaces"]
        for path in _python_files(PACKAGE_ROOT / context):
            for module in _imports(path):
                assert not any(_within(module, package) for package in forbidden), (
                    path,
                    module,
                )


def test_source_does_not_import_legacy_packages() -> None:
    """src、tests、toolsが旧パッケージのimport pathを使わない。"""

    for directory in (SOURCE_ROOT, PROJECT_ROOT / "tests", PROJECT_ROOT / "tools"):
        for path in _python_files(directory):
            if path.name == Path(__file__).name:
                continue
            for module in _imports(path):
                top = module.split(".")[0]
                assert top not in LEGACY_PACKAGES, (path, module)


def test_all_modules_are_importable() -> None:
    """新しい名前空間の全モジュールを読み込め、循環importや参照先の誤りがない。"""

    names = {
        _module_name(path)
        for path in _python_files(PACKAGE_ROOT)
        if path.name != "__main__.py"
    }
    assert "kvk_team.interfaces.cli.main" in names
    assert "kvk_team.team_building.application.build_team_plan" in names
    assert "kvk_team.interfaces.cli.team_builder" in names
    for name in sorted(names):
        importlib.import_module(name)

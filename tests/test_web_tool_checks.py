"""web/のHTMLを実物のまま検査する仕組み（ADR 0030）の契約を検証する。"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHECK_WEB_SCRIPT = PROJECT_ROOT / "tools" / "check_web.py"
CHECK_SCRIPT = PROJECT_ROOT / "tools" / "check.py"


def _load_module(name: str, path: Path) -> ModuleType:
    """`tools/`のScriptをモジュールとして読み込む。"""

    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _node_version() -> str:
    return (PROJECT_ROOT / ".node-version").read_text(encoding="utf-8").strip()


def test_node_version_is_pinned_once_and_shared_by_ci_and_dev_container() -> None:
    """Node.jsの版を`.node-version`へ固定し、CIとDev Containerが同じ版を使う。"""

    version = _node_version()
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), version

    dockerfile = (PROJECT_ROOT / ".devcontainer" / "Dockerfile").read_text(
        encoding="utf-8"
    )
    assert f"ARG NODE_VERSION={version}\n" in dockerfile
    assert "FROM node:${NODE_VERSION}-bookworm-slim AS node" in dockerfile
    assert "COPY --from=node /usr/local/bin/node /usr/local/bin/node" in dockerfile

    workflow = yaml.safe_load(
        (PROJECT_ROOT / ".github" / "workflows" / "tests.yml").read_text(
            encoding="utf-8"
        )
    )
    steps = workflow["jobs"]["check"]["steps"]
    setup_node = [step for step in steps if step.get("uses") == "actions/setup-node@v4"]
    assert setup_node == [
        {
            "uses": "actions/setup-node@v4",
            "with": {"node-version-file": ".node-version", "cache": "npm"},
        }
    ]


def test_ci_installs_locked_jsdom_and_keeps_existing_steps() -> None:
    """CIは`npm ci`でjsdomを入れ、既存の手順とjobの構成を変えない。"""

    workflow = yaml.safe_load(
        (PROJECT_ROOT / ".github" / "workflows" / "tests.yml").read_text(
            encoding="utf-8"
        )
    )
    job = workflow["jobs"]["check"]
    assert job["name"] == "${{ matrix.os }} / Python ${{ matrix.python-version }}"
    assert job["strategy"]["matrix"] == {
        "os": ["ubuntu-latest", "windows-latest"],
        "python-version": ["3.11", "3.12"],
    }
    runs = [step.get("run") for step in job["steps"] if "run" in step]
    assert runs == [
        'python -m pip install -e ".[dev]"',
        "npm ci",
        "python tools/check.py",
    ]


def test_jsdom_is_pinned_and_locked() -> None:
    """jsdomの版を範囲指定せずに固定し、lockfileと一致させる。"""

    package = json.loads((PROJECT_ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["private"] is True
    jsdom_version = package["devDependencies"]["jsdom"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", jsdom_version), jsdom_version
    assert "dependencies" not in package

    lock = json.loads((PROJECT_ROOT / "package-lock.json").read_text(encoding="utf-8"))
    assert lock["packages"][""]["devDependencies"] == {"jsdom": jsdom_version}
    assert lock["packages"]["node_modules/jsdom"]["version"] == jsdom_version

    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "\nnode_modules/\n" in gitignore


def test_dev_container_installs_node_dependencies_on_create() -> None:
    """Dev Containerは作成時にjsdomも入れ、手作業なしで品質ゲートを通せる。"""

    definition = json.loads(
        (PROJECT_ROOT / ".devcontainer" / "devcontainer.json").read_text(
            encoding="utf-8"
        )
    )
    assert definition["postCreateCommand"].endswith(" && npm ci")


def test_quality_gate_runs_web_checks() -> None:
    """`python tools/check.py`はweb/の検査を省略せずに実行する。"""

    check = _load_module("check_for_web_test", CHECK_SCRIPT)
    for fix in (False, True):
        arguments = [item.arguments for item in check._checks(fix)]
        assert ("tools/check_web.py",) in arguments

    check_web = _load_module("check_web", CHECK_WEB_SCRIPT)
    names = {path.name for path in check_web.web_test_files()}
    assert {"siege-timeline.test.js", "wave-timer.test.js"} <= names


@pytest.mark.parametrize(
    ("output", "expected"),
    [("v22.11.0\n", 22), ("v20.0.0", 20), ("", None), ("22.11.0", None)],
)
def test_parse_major_version(output: str, expected: int | None) -> None:
    """`node --version`の出力からメジャーバージョンを読む。"""

    check_web = _load_module("check_web", CHECK_WEB_SCRIPT)
    assert check_web.parse_major_version(output) == expected


def test_web_checks_fail_with_install_guide_without_node(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Node.jsがない環境では、入れ方を示して失敗する。黙って成功させない。"""

    check_web = _load_module("check_web", CHECK_WEB_SCRIPT)
    monkeypatch.setattr(check_web.shutil, "which", lambda _name: None)

    assert check_web.main([]) == 1
    error = capsys.readouterr().err
    assert "Node.jsが見つかりません" in error
    assert "npm ci" in error
    assert "Rebuild Container" in error


class _FakeNode:
    """`subprocess.run`の代わりに、Node.jsの呼び出しを記録して決まった結果を返す。"""

    def __init__(
        self, version: str, jsdom: str | None, test_returncode: int = 0
    ) -> None:
        self.version = version
        self.jsdom = jsdom
        self.test_returncode = test_returncode
        self.calls: list[list[str]] = []
        self.cwds: dict[str, object] = {}

    def __call__(self, command: list[str], **kwargs: object) -> SimpleNamespace:
        self.calls.append(list(command))
        self.cwds[command[1]] = kwargs.get("cwd")
        if command[1] == "--version":
            return SimpleNamespace(returncode=0, stdout=self.version)
        if command[1] == "-p":
            if self.jsdom is None:
                return SimpleNamespace(returncode=1, stdout="")
            return SimpleNamespace(returncode=0, stdout=self.jsdom + "\n")
        return SimpleNamespace(returncode=self.test_returncode, stdout="")


def _jsdom_version() -> str:
    package = json.loads((PROJECT_ROOT / "package.json").read_text(encoding="utf-8"))
    return str(package["devDependencies"]["jsdom"])


def _run_with_fake_node(
    monkeypatch: pytest.MonkeyPatch, fake: _FakeNode
) -> tuple[ModuleType, int]:
    check_web = _load_module("check_web", CHECK_WEB_SCRIPT)
    monkeypatch.setattr(check_web.shutil, "which", lambda _name: "node")
    monkeypatch.setattr(check_web.subprocess, "run", fake)
    return check_web, check_web.main([])


def test_web_checks_fail_with_install_guide_without_jsdom(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """jsdomが見つからない環境では、worktreeの場合も含めて入れ方を示して失敗する。"""

    fake = _FakeNode(f"v{_node_version()}\n", jsdom=None)
    _check_web, returncode = _run_with_fake_node(monkeypatch, fake)

    assert returncode == 1
    error = capsys.readouterr().err
    assert "jsdomが見つかりません" in error
    assert "npm ci" in error
    assert "worktree" in error
    # 検査と同じモジュール解決（親のnode_modulesも探す）で確かめる。
    resolve = [call for call in fake.calls if call[1] == "-p"]
    # 検査（tests/web/helpers.js）と同じ場所から解決する。
    assert fake.cwds["-p"] == PROJECT_ROOT / "tests" / "web"
    assert resolve == [["node", "-p", "require('jsdom/package.json').version"]]
    assert not any("--test" in call for call in fake.calls)


def test_web_checks_reject_other_jsdom_version(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """入っているjsdomの版が`package.json`と違えば、`npm ci`を案内して失敗する。"""

    fake = _FakeNode(f"v{_node_version()}\n", jsdom="24.0.0")
    _check_web, returncode = _run_with_fake_node(monkeypatch, fake)

    assert returncode == 1
    error = capsys.readouterr().err
    assert f"jsdom {_jsdom_version()}が必要です（現在: 24.0.0）" in error
    assert "npm ci" in error


def test_web_checks_reject_older_node(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`.node-version`より古いメジャーバージョンのNode.jsでは失敗する。"""

    fake = _FakeNode("v18.20.0\n", jsdom=_jsdom_version())
    _check_web, returncode = _run_with_fake_node(monkeypatch, fake)

    assert returncode == 1
    error = capsys.readouterr().err
    assert f"Node.js {_node_version().split('.')[0]}以上が必要です" in error


@pytest.mark.parametrize("test_returncode", [0, 1])
def test_web_checks_pass_every_test_file_and_propagate_the_result(
    monkeypatch: pytest.MonkeyPatch, test_returncode: int
) -> None:
    """全検査ファイルを制限時間付きで`node --test`へ渡し、その終了コードを返す。"""

    fake = _FakeNode(
        f"v{_node_version()}\n", jsdom=_jsdom_version(), test_returncode=test_returncode
    )
    check_web, returncode = _run_with_fake_node(monkeypatch, fake)

    assert returncode == test_returncode
    test_calls = [call for call in fake.calls if "--test" in call]
    # 検査ファイルは最上位からの相対パスで渡すため、最上位で実行する。
    assert fake.cwds["--test"] == PROJECT_ROOT
    assert len(test_calls) == 1
    command = test_calls[0]
    assert command[:2] == ["node", "--test"]
    assert any(argument.startswith("--test-timeout=") for argument in command)
    expected = [
        path.relative_to(PROJECT_ROOT).as_posix() for path in check_web.web_test_files()
    ]
    assert command[-len(expected) :] == expected
    assert {f"tests/web/siege-random-{shard}.test.js" for shard in range(1, 5)} <= set(
        expected
    )

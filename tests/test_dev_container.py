"""Windowsを含むローカル開発用Dev Containerの契約を検証する。"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_dev_container_uses_a_minimal_non_root_python_environment() -> None:
    """開発用ContainerがPythonと非root利用者を固定する。"""

    definition_path = PROJECT_ROOT / ".devcontainer" / "devcontainer.json"
    definition = json.loads(definition_path.read_text(encoding="utf-8"))
    dockerfile = (PROJECT_ROOT / ".devcontainer" / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert definition["build"] == {"dockerfile": "Dockerfile", "context": ".."}
    assert definition["remoteUser"] == "vscode"
    assert definition["updateRemoteUserUID"] is True
    assert definition["postCreateCommand"] == (
        'python -m pip install -e ".[dev]" && npm ci'
    )
    assert definition["customizations"]["vscode"]["extensions"] == [
        "OpenAI.chatgpt",
        "anthropic.claude-code",
        "ms-python.python",
        "ms-python.vscode-pylance",
        "charliermarsh.ruff",
    ]
    assert "FROM python:3.12-slim-bookworm" in dockerfile
    assert "USER vscode" in dockerfile
    for directory in (
        "/home/${USERNAME}/.vscode-server",
        "/home/${USERNAME}/.vscode-server/bin",
        "/home/${USERNAME}/.vscode-server/extensions",
    ):
        assert directory in dockerfile
    assert (
        'install --directory --owner="${USERNAME}" --group="${USERNAME}"' in dockerfile
    )


def test_dev_container_does_not_receive_host_docker_or_credentials() -> None:
    """最小構成がDocker socketや認証情報をContainerへ渡さない。"""

    definition_path = PROJECT_ROOT / ".devcontainer" / "devcontainer.json"
    definition = json.loads(definition_path.read_text(encoding="utf-8"))
    dockerfile = (PROJECT_ROOT / ".devcontainer" / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert definition["mounts"] == [
        "source=kvk-vscode-extensions,"
        "target=/home/vscode/.vscode-server/extensions,type=volume"
    ]
    assert "containerEnv" not in definition
    assert "GH_TOKEN" not in definition_path.read_text(encoding="utf-8")
    assert "docker.sock" not in dockerfile


def test_dev_container_matches_workspace_owner_with_a_single_sudo_command() -> None:
    """Gitの所有者検査を通すため、起動時にRepositoryの所有者を実行利用者へそろえる。

    sudoで許可するのは引数を取らない専用Script1本だけとし、任意のroot実行を許さない。
    """

    definition_path = PROJECT_ROOT / ".devcontainer" / "devcontainer.json"
    definition = json.loads(definition_path.read_text(encoding="utf-8"))
    dockerfile = (PROJECT_ROOT / ".devcontainer" / "Dockerfile").read_text(
        encoding="utf-8"
    )
    script = (PROJECT_ROOT / ".devcontainer" / "fix-workspace-owner.sh").read_text(
        encoding="utf-8"
    )

    assert definition["postStartCommand"] == "sudo /usr/local/bin/fix-workspace-owner"
    assert "safe.directory" not in definition_path.read_text(encoding="utf-8")

    assert "sudo" in dockerfile
    assert (
        "COPY --chown=root:root --chmod=0755 .devcontainer/fix-workspace-owner.sh "
        "/usr/local/bin/fix-workspace-owner"
    ) in dockerfile
    # 空の引数指定で、許可したScriptへ引数を渡す実行も拒否する。
    assert (
        "printf '%s ALL=(root) NOPASSWD: /usr/local/bin/fix-workspace-owner \"\"\\n' "
        '"${USERNAME}"'
    ) in dockerfile
    assert "chmod 0440 /etc/sudoers.d/fix-workspace-owner" in dockerfile
    assert "visudo --check --file=/etc/sudoers.d/fix-workspace-owner" in dockerfile
    assert "NOPASSWD: ALL" not in dockerfile

    assert script.startswith("#!/bin/sh\n")
    assert "set -eu" in script
    assert '[ "$#" -eq 0 ]' in script
    assert "/workspaces" in script
    # Symbolic Linkをたどらず、Gitが所有者を検査する作業ツリーと.gitだけを変更する。
    assert "chown -h" in script
    assert "-L" in script
    assert "chown -R" not in script
    assert "\r\n" not in script

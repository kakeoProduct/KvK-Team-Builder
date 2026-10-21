"""Claude CodeとCodexで共有するAgent Hookの振る舞いテスト。"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOOK_DIRECTORY = PROJECT_ROOT / "tools" / "hooks"
GIT_GUARD_SCRIPT = HOOK_DIRECTORY / "block_dangerous_git.py"
MEMORY_HOOK_SCRIPT = HOOK_DIRECTORY / "project_memory_hook.py"
READ_ONLY_AGENT_SCRIPT = HOOK_DIRECTORY / "enforce_read_only_agent.py"
PROJECT_MEMORY_SCRIPT = (
    PROJECT_ROOT
    / ".agents"
    / "skills"
    / "maintain-project-memory"
    / "scripts"
    / "session_memory.py"
)
CLAUDE_SETTINGS_PATH = PROJECT_ROOT / ".claude" / "settings.json"


def _run_hook(
    script: Path, payload: object, *arguments: str, cwd: Path = PROJECT_ROOT
) -> subprocess.CompletedProcess[str]:
    """Hook ScriptへJSONを標準入力として渡して実行する。"""

    return subprocess.run(
        [sys.executable, str(script), *arguments],
        input=json.dumps(payload),
        cwd=cwd,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def _git_guard_decision(command: str, *arguments: str) -> tuple[str, str] | None:
    """Git保護Hookの判定と理由を返す。許可時はNoneを返す。"""

    completed = _run_hook(
        GIT_GUARD_SCRIPT,
        {"hook_event_name": "PreToolUse", "tool_input": {"command": command}},
        *arguments,
    )
    assert completed.returncode == 0, completed.stderr
    if completed.stdout == "":
        return None
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    return output["permissionDecision"], output["permissionDecisionReason"]


def test_git_guard_denies_destructive_commands_by_default() -> None:
    """既定動作ではpushと作業内容を失う操作をすべて拒否する。"""

    for command, label in (
        ("git push origin main", "git push"),
        ("git -C repo push", "git push"),
        ("git reset --hard HEAD~1", "git reset --hard"),
        ("git clean -fd", "git clean -f"),
        ("git branch -D temporary", "git branch -D"),
        ("git checkout .", "git checkout ."),
        ("git restore -- .", "git restore ."),
        ("git worktree remove --force ../other", "git worktree remove --force"),
        ("git worktree remove -f .worktrees/topic", "git worktree remove --force"),
    ):
        decision = _git_guard_decision(command)
        assert decision is not None
        assert decision[0] == "deny"
        assert label in decision[1]

    assert _git_guard_decision("git status") is None
    assert _git_guard_decision('git commit -m "feat(hooks): 日本語の要約"') is None
    assert _git_guard_decision("git worktree add -b topic .worktrees/topic") is None
    assert _git_guard_decision("git worktree remove .worktrees/topic") is None


def test_git_guard_asks_for_normal_push_but_denies_force_push() -> None:
    """Claude Code用の確認モードでは通常pushだけを利用者確認へ回す。"""

    decision = _git_guard_decision("git push -u origin feature", "--ask-push")
    assert decision is not None
    assert decision[0] == "ask"
    assert "git push" in decision[1]

    for command in (
        "git push --force origin feature",
        "git push -f origin feature",
        "git push --force-with-lease",
        "git push origin +feature",
    ):
        decision = _git_guard_decision(command, "--ask-push")
        assert decision is not None, command
        assert decision[0] == "deny", command
        assert "git push --force" in decision[1]

    reset = _git_guard_decision("git status && git reset --hard", "--ask-push")
    assert reset is not None
    assert reset[0] == "deny"


def test_git_guard_fails_closed_on_unreadable_input() -> None:
    """Hook入力を解析できない場合は安全側へ拒否する。"""

    completed = subprocess.run(
        [sys.executable, str(GIT_GUARD_SCRIPT)],
        input="not json",
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"


def _read_only_decision(payload: object) -> tuple[str, str] | None:
    """読み取り専用AgentのHook判定と理由を返す。許可時はNoneを返す。"""

    completed = _run_hook(READ_ONLY_AGENT_SCRIPT, payload)
    assert completed.returncode == 0, completed.stderr
    if completed.stdout == "":
        return None
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    return output["permissionDecision"], output["permissionDecisionReason"]


def _tool_payload(tool_name: str, tool_input: dict[str, object]) -> dict[str, object]:
    """Subagent内のPreToolUse入力を作る。"""

    return {
        "hook_event_name": "PreToolUse",
        "agent_type": "kvk-test-reviewer",
        "permission_mode": "auto",
        "tool_name": tool_name,
        "tool_input": tool_input,
    }


def _bash_decision(command: str) -> tuple[str, str] | None:
    """Bashコマンドに対する読み取り専用Hookの判定を返す。"""

    return _read_only_decision(_tool_payload("Bash", {"command": command}))


def test_read_only_agent_allows_reading_and_verification() -> None:
    """追跡対象を変更しない確認コマンドだけを許可する。"""

    for command in (
        "git status --short",
        "git diff main...HEAD -- src/",
        "git -C ../other log --oneline -5",
        "git log --oneline | head -20",
        "git show HEAD:README.md",
        "git branch --show-current",
        "cat README.md && wc -l src/kvk/models.py",
        "sed -n 1,40p tools/check.py",
        "grep -rn Must AGENTS.md",
        "find tests -name '*.py'",
        "python -m pytest tests/test_parser.py -q",
        "python tools/check.py",
        "python tools/sync_agent_config.py --check",
        "python -m pytest -q 2>&1 | tail -5",
        "git diff --stat 2>/dev/null",
        "cd tests && ls",
    ):
        assert _bash_decision(command) is None, command


def test_read_only_agent_denies_writes_in_any_permission_mode() -> None:
    """権限モードにかかわらず、編集Toolと書き込み得るコマンドを拒否する。"""

    for tool_name, tool_input in (
        ("Edit", {"file_path": "README.md"}),
        ("Write", {"file_path": "x.md", "content": ""}),
        ("NotebookEdit", {"notebook_path": "x.ipynb"}),
        ("Agent", {"prompt": "edit files"}),
        ("PowerShell", {"command": "New-Item x"}),
        ("Monitor", {"command": "touch x"}),
        ("mcp__example__write", {}),
    ):
        decision = _read_only_decision(_tool_payload(tool_name, tool_input))
        assert decision is not None and decision[0] == "deny", tool_name

    for command in (
        "touch tmp/x",
        "rm -rf src",
        "echo a > README.md",
        "cat README.md >> notes.md",
        "git status; rm README.md",
        "git commit -m x",
        "git checkout main",
        "git branch new-branch",
        "git diff --output=patch.txt",
        "git -c core.pager=sh log",
        "python tools/check.py --fix",
        "python tools/sync_agent_config.py",
        # 既定でもtmp/preview/の前回出力を上書きし、利用者の差分の基準を失わせる。
        "python tools/preview_output.py",
        "python tools/preview_output.py --output README.md",
        "git status\nrm README.md",
        "sort -o README.md README.md",
        "rg --pre sh Must",
        'python -c \'open("x", "w")\'',
        "python -m pytest --junitxml=report.xml",
        "sed -i s/a/b/ README.md",
        "sed -n 'w out.txt' README.md",
        "find . -name '*.pyc' -delete",
        "find . -exec rm {} ;",
        "ls $(rm README.md)",
        "ls `rm README.md`",
        "FOO=1 python tools/check.py",
        "sleep 10 &",
        "ls 'unterminated",
    ):
        decision = _bash_decision(command)
        assert decision is not None and decision[0] == "deny", command


def test_read_only_agent_fails_closed_on_unreadable_input() -> None:
    """Hook入力やTool名を解析できない場合は拒否する。"""

    completed = subprocess.run(
        [sys.executable, str(READ_ONLY_AGENT_SCRIPT)],
        input="not json",
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"

    for payload in (
        {"hook_event_name": "PreToolUse", "agent_type": "kvk-test-reviewer"},
        {
            "hook_event_name": "PreToolUse",
            "agent_type": "kvk-test-reviewer",
            "tool_name": "Bash",
            "tool_input": {},
        },
    ):
        decision = _read_only_decision(payload)
        assert decision is not None and decision[0] == "deny", payload


def test_read_only_hook_limits_only_agents_declared_read_only() -> None:
    """正本で読み取り専用と宣言したAgentだけを制限し、主Sessionと他のAgentは通す。"""

    command = {"command": "touch tmp/readonly-probe.txt"}
    for agent_type in (
        "kvk-architecture-reviewer",
        "kvk-domain-reviewer",
        "kvk-requirements-reviewer",
        "kvk-test-reviewer",
        "evidence-reviewer",
    ):
        payload = {**_tool_payload("Bash", command), "agent_type": agent_type}
        decision = _read_only_decision(payload)
        assert decision is not None and decision[0] == "deny", agent_type

    main_session = _tool_payload("Bash", command)
    del main_session["agent_type"]
    for payload in (
        main_session,
        {**_tool_payload("Bash", command), "agent_type": "general-purpose"},
        {**_tool_payload("Edit", {"file_path": "x"}), "agent_type": "Explore"},
        # パスとして解釈され得る名前で正本外のファイルを読ませない。
        {**_tool_payload("Bash", command), "agent_type": "../agents/kvk-test-reviewer"},
    ):
        assert _read_only_decision(payload) is None, payload


def test_claude_settings_register_repository_hooks() -> None:
    """Claude Codeの共有設定がGit保護と共有記憶のHookを登録する。"""

    settings = json.loads(CLAUDE_SETTINGS_PATH.read_text(encoding="utf-8"))
    hooks = settings["hooks"]

    pre_tool_use = hooks["PreToolUse"]
    matchers = {entry["matcher"] for entry in pre_tool_use}
    assert "Bash|PowerShell" in matchers
    pre_arguments = [hook["args"] for entry in pre_tool_use for hook in entry["hooks"]]
    assert [
        "${CLAUDE_PROJECT_DIR}/tools/hooks/block_dangerous_git.py",
        "--ask-push",
    ] in pre_arguments
    # Subagent定義のHookは発火しないため、共有設定から全Tool呼び出しを検査する。
    read_only_entries = [
        entry
        for entry in pre_tool_use
        if any(
            hook["args"]
            == ["${CLAUDE_PROJECT_DIR}/tools/hooks/enforce_read_only_agent.py"]
            for hook in entry["hooks"]
        )
    ]
    assert len(read_only_entries) == 1
    # 読み取りToolと内部Toolでは起動せず、書き込み得るToolだけを検査する。
    matcher = re.compile(read_only_entries[0]["matcher"])
    for tool_name in (
        "Bash",
        "PowerShell",
        "Monitor",
        "Edit",
        "Write",
        "NotebookEdit",
        "Agent",
        "mcp__example__write",
    ):
        assert matcher.fullmatch(tool_name), tool_name
    for tool_name in (
        "Read",
        "Grep",
        "Glob",
        "WebSearch",
        "WebFetch",
        "SubagentHandback",
        "ToolSearch",
        "TodoWrite",
    ):
        assert not matcher.fullmatch(tool_name), tool_name

    for event, argument in (("SessionStart", "session-start"), ("Stop", "stop")):
        arguments = [hook["args"] for entry in hooks[event] for hook in entry["hooks"]]
        assert [
            "${CLAUDE_PROJECT_DIR}/tools/hooks/project_memory_hook.py",
            argument,
        ] in arguments, event

    # Windowsでもシェルの変数展開へ依存しないよう、exec形式で起動する。
    for entries in hooks.values():
        for entry in entries:
            for hook in entry["hooks"]:
                assert hook["type"] == "command"
                assert hook["command"] == "python"


def test_claude_settings_deny_generated_files_and_secrets() -> None:
    """生成物の直接編集と秘密情報ファイルの読み取りを権限規則で拒否する。"""

    settings = json.loads(CLAUDE_SETTINGS_PATH.read_text(encoding="utf-8"))
    deny = set(settings["permissions"]["deny"])
    assert {
        "Edit(.claude/skills/**)",
        "Edit(.claude/agents/**)",
        "Read(.env)",
        "Read(.env.*)",
    } <= deny
    # 同期Scriptと品質ゲートが動かなくならないよう、実行系の規則は加えない。
    assert not any(rule.startswith("Bash(") for rule in deny)


def test_worktree_directories_are_ignored() -> None:
    """Session用worktreeを元の作業ツリーの差分や品質ゲートへ混ぜない。"""

    ignored = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".worktrees/" in ignored
    assert ".claude/worktrees/" in ignored


def _run_git(repository: Path, *arguments: str) -> None:
    """Test用RepositoryでGit Commandを実行する。"""

    subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )


def _create_memory_repository(tmp_path: Path) -> tuple[Path, Path]:
    """共有記憶ScriptとHookを配置したTest用Repositoryを作る。"""

    repository = tmp_path / "repository"
    script = (
        repository
        / ".agents"
        / "skills"
        / "maintain-project-memory"
        / "scripts"
        / "session_memory.py"
    )
    script.parent.mkdir(parents=True)
    shutil.copy2(PROJECT_MEMORY_SCRIPT, script)
    hook = repository / "tools" / "hooks" / "project_memory_hook.py"
    hook.parent.mkdir(parents=True)
    shutil.copy2(MEMORY_HOOK_SCRIPT, hook)
    memory_root = repository / "docs" / "project-memory"
    memory_root.mkdir(parents=True)
    (memory_root / "README.md").write_text("# Test Memory\n", encoding="utf-8")
    (repository / "feature.txt").write_text("base\n", encoding="utf-8")

    _run_git(repository, "init")
    _run_git(repository, "config", "user.name", "Test User")
    _run_git(repository, "config", "user.email", "test@example.com")
    _run_git(repository, "add", ".")
    _run_git(repository, "commit", "-m", "initial")
    return repository, hook


def test_memory_hook_starts_session_and_reminds_once_before_stop(
    tmp_path: Path,
) -> None:
    """SessionStartで開始状態を保存し、未記録の変更があれば一度だけ停止を止める。"""

    repository, hook = _create_memory_repository(tmp_path)
    session_id = "11111111-2222-3333-4444-555555555555"

    started = _run_hook(
        hook,
        {"hook_event_name": "SessionStart", "session_id": session_id},
        "session-start",
        cwd=repository,
    )
    assert started.returncode == 0, started.stderr
    context = json.loads(started.stdout)["hookSpecificOutput"]
    assert context["hookEventName"] == "SessionStart"
    assert session_id in context["additionalContext"]

    resumed = _run_hook(
        hook,
        {"hook_event_name": "SessionStart", "session_id": session_id},
        "session-start",
        cwd=repository,
    )
    assert resumed.returncode == 0, resumed.stderr
    assert (
        session_id
        in json.loads(resumed.stdout)["hookSpecificOutput"]["additionalContext"]
    )

    stop_payload = {
        "hook_event_name": "Stop",
        "session_id": session_id,
        "stop_hook_active": False,
    }
    unchanged = _run_hook(hook, stop_payload, "stop", cwd=repository)
    assert unchanged.returncode == 0, unchanged.stderr
    assert unchanged.stdout == ""

    (repository / "feature.txt").write_text("Sessionの変更\n", encoding="utf-8")
    blocked = _run_hook(hook, stop_payload, "stop", cwd=repository)
    assert blocked.returncode == 0, blocked.stderr
    decision = json.loads(blocked.stdout)
    assert decision["decision"] == "block"
    assert "feature.txt" in decision["reason"]
    assert session_id in decision["reason"]

    reminded = _run_hook(hook, stop_payload, "stop", cwd=repository)
    assert reminded.returncode == 0, reminded.stderr
    assert reminded.stdout == ""

    active = _run_hook(
        hook, {**stop_payload, "stop_hook_active": True}, "stop", cwd=repository
    )
    assert active.stdout == ""


def test_memory_hook_does_not_block_unknown_sessions(tmp_path: Path) -> None:
    """開始状態のないSessionや壊れた入力では作業を止めない。"""

    repository, hook = _create_memory_repository(tmp_path)
    (repository / "feature.txt").write_text("変更\n", encoding="utf-8")

    unknown = _run_hook(
        hook,
        {"hook_event_name": "Stop", "session_id": "unknown-session"},
        "stop",
        cwd=repository,
    )
    assert unknown.returncode == 0, unknown.stderr
    assert unknown.stdout == ""

    broken = subprocess.run(
        [sys.executable, str(hook), "stop"],
        input="not json",
        cwd=repository,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    assert broken.returncode == 0
    assert "decision" not in broken.stdout


def test_memory_hook_tells_second_session_to_use_a_worktree(tmp_path: Path) -> None:
    """同じ作業ツリーを別Sessionが使用中なら、SessionStartでworktreeを案内する。"""

    repository, hook = _create_memory_repository(tmp_path)

    first = _run_hook(
        hook,
        {"hook_event_name": "SessionStart", "session_id": "first-session"},
        "session-start",
        cwd=repository,
    )
    assert first.returncode == 0, first.stderr
    first_context = json.loads(first.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "worktree" not in first_context

    second = _run_hook(
        hook,
        {"hook_event_name": "SessionStart", "session_id": "second-session"},
        "session-start",
        cwd=repository,
    )
    assert second.returncode == 0, second.stderr
    second_context = json.loads(second.stdout)["hookSpecificOutput"][
        "additionalContext"
    ]
    assert "worktree" in second_context
    assert "$implement" in second_context
    assert "second-session" in second_context


def test_memory_hook_follows_session_into_a_linked_worktree(tmp_path: Path) -> None:
    """Session用worktreeへ移った後は、そのworktreeの開始状態で記録漏れを確認する。"""

    repository, hook = _create_memory_repository(tmp_path)
    worktree = repository / ".claude" / "worktrees" / "topic"
    _run_git(repository, "worktree", "add", "-b", "topic", str(worktree))
    session_id = "worktree-session"

    started = _run_hook(
        hook,
        {
            "hook_event_name": "SessionStart",
            "session_id": session_id,
            "cwd": str(worktree),
        },
        "session-start",
        cwd=worktree,
    )
    assert started.returncode == 0, started.stderr

    (worktree / "feature.txt").write_text("worktreeの変更\n", encoding="utf-8")
    stop_payload = {
        "hook_event_name": "Stop",
        "session_id": session_id,
        "stop_hook_active": False,
        "cwd": str(worktree),
    }
    blocked = _run_hook(hook, stop_payload, "stop", cwd=worktree)
    assert blocked.returncode == 0, blocked.stderr
    assert json.loads(blocked.stdout)["decision"] == "block"

    # 元の作業ツリーには開始状態を作らない。
    main_stop = _run_hook(
        hook, {**stop_payload, "cwd": str(repository)}, "stop", cwd=repository
    )
    assert main_stop.returncode == 0, main_stop.stderr
    assert main_stop.stdout == ""

    # Repository外のcwdは信用せず、元の作業ツリーとして扱う。
    outside = _run_hook(
        hook, {**stop_payload, "cwd": str(tmp_path)}, "stop", cwd=repository
    )
    assert outside.returncode == 0, outside.stderr
    assert outside.stdout == ""


def test_memory_hook_ignores_virtual_environment_of_another_os(tmp_path: Path) -> None:
    """Windowsと共有するWorkspaceで、別OS用のvenvのPythonを起動しない。"""

    repository, hook = _create_memory_repository(tmp_path)
    other_python = (
        repository / ".venv" / "bin" / "python"
        if os.name == "nt"
        else repository / ".venv" / "Scripts" / "python.exe"
    )
    other_python.parent.mkdir(parents=True)
    other_python.write_bytes(b"MZ not runnable on this OS")

    started = _run_hook(
        hook,
        {"hook_event_name": "SessionStart", "session_id": "shared-venv"},
        "session-start",
        cwd=repository,
    )
    assert started.returncode == 0, started.stderr
    assert "shared-venv" in started.stdout

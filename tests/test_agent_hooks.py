"""Claude CodeとCodexで共有するAgent Hookの振る舞いテスト。"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOOK_DIRECTORY = PROJECT_ROOT / "tools" / "hooks"
GIT_GUARD_SCRIPT = HOOK_DIRECTORY / "block_dangerous_git.py"
MEMORY_HOOK_SCRIPT = HOOK_DIRECTORY / "project_memory_hook.py"
READ_ONLY_AGENT_SCRIPT = HOOK_DIRECTORY / "enforce_read_only_agent.py"
REVIEW_REPORT_SCRIPT = HOOK_DIRECTORY / "check_review_report.py"
PROJECT_MEMORY_SCRIPT = (
    PROJECT_ROOT
    / ".agents"
    / "skills"
    / "maintain-project-memory"
    / "scripts"
    / "session_memory.py"
)
CLAUDE_SETTINGS_PATH = PROJECT_ROOT / ".claude" / "settings.json"
CODEX_HOOKS_PATH = PROJECT_ROOT / ".codex" / "hooks.json"
AGENT_DEFINITION_DIRECTORY = PROJECT_ROOT / ".codex" / "agents"
CODE_REVIEW_AGENTS = (
    "kvk-architecture-reviewer",
    "kvk-domain-reviewer",
    "kvk-requirements-reviewer",
    "kvk-test-reviewer",
)
VALID_REVIEW_REPORT = (
    "承認候補\n\n## Must\n\nなし\n\n## Should\n\nなし\n\n"
    "## Nice\n\n- tools/check.py:10 文言を短くする\n\n## 未確定\n\nなし\n"
)


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


def _assert_denies_unreadable_input(script: Path) -> None:
    """解析できない入力を、ASCIIだけのJSONで拒否することを確かめる。"""

    for raw_input in (b"not json", b"\xff\xfe", b"[]", b'"x"'):
        completed = subprocess.run(
            [sys.executable, str(script)],
            input=raw_input,
            capture_output=True,
            check=False,
        )
        assert completed.returncode == 0, raw_input
        # 既定コードページへ依存しないよう、非ASCII文字をエスケープして出力する。
        assert completed.stdout.isascii(), raw_input
        output = json.loads(completed.stdout)["hookSpecificOutput"]
        assert output["permissionDecision"] == "deny", raw_input


def test_git_guard_fails_closed_on_unreadable_input() -> None:
    """Hook入力を解析できない場合は安全側へ拒否する。"""

    _assert_denies_unreadable_input(GIT_GUARD_SCRIPT)


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
    """Bashコマンドに対する読み取り専用Hookの判定を、Scriptを起動して返す。"""

    return _read_only_decision(_tool_payload("Bash", {"command": command}))


def _bash_reason(command: str) -> str | None:
    """Bashコマンドを拒否する理由を、判定関数を直接呼んで返す。許可時はNoneを返す。"""

    # 子プロセスの起動を代表の入力に絞り、規則ごとの多数の入力は直接判定する。
    return _SHARED_READ_ONLY_MODULE._blocked_reason(  # type: ignore[attr-defined]
        _tool_payload("Bash", {"command": command})
    )


def test_read_only_agent_script_reports_decisions_as_json() -> None:
    """Scriptとして起動しても、許可は空の出力、拒否はdenyのJSONで返す。"""

    assert _bash_decision("git status --short") is None
    decision = _bash_decision("touch tmp/x")
    assert decision is not None and decision[0] == "deny"


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
        'find tests -name "*.py"',
        "python -m pytest tests/test_parser.py -q",
        "python tools/check.py",
        "python tools/sync_agent_config.py --check",
        "python -m pytest -q 2>&1 | tail -5",
        "git diff --stat 2>/dev/null",
        "cd tests && ls",
        'grep -n "#" AGENTS.md',
        'python -m pytest -q -x -k "parser and not slow" tests/test_parser.py',
        "python -m pytest --tb=short -vv tests/test_cli.py::test_main",
        "sort -rn README.md",
        "sort -t : -k 2 README.md",
        "sort -nk2 README.md",
        'find . -maxdepth 2 -type f -name "*.md" -print',
        'find tests -iname "test_*" -not -path "*/__pycache__/*"',
        "git log --oneline -n5",
        "git log -S Optimizer --oneline",
        'find . -path "./.git" -prune -o -name "*.md" -print',
        "find . -name x -quit",
        "find . -depth -name x -ls",
        'python -m pytest -m "not slow" -q',
    ):
        assert _bash_reason(command) is None, command


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
        # 対話のデバッガーは、標準入力から任意のPythonを実行できる。
        "python -m pytest --pdb",
        "python -m pytest --trace tests/test_cli.py",
        "python -m pytest --pdbcls=x:y",
        # CodexはPowerShellのコマンドも`Bash`として渡す。`{}`はScript Blockとして実行される。
        "ls | sort {Remove-Item README.md}",
        "diff -Property {Remove-Item x} a b",
        "git show HEAD@{1}",
        # PowerShellとcmdは`\`をエスケープとして扱わないため、`\`は丸ごと拒否する。
        'echo "a\\" ; rm README.md ; echo "',
        "echo a \\;Remove-Item x",
        "echo a \\&del x",
        "python -m pytest tests\\ --junitxml=x.xml",
        "git log -Sfoo\\ --output=y",
        # 変数の展開は、Hookが見ていない引数をコマンドへ渡すため、`$`は丸ごと拒否する。
        "echo -l ; wc $_ README.md",
        "echo --output=x ; git diff $_",
        "echo -delete ; find tmp $_",
        "sed -n $p README.md",
        "cat ${HOME}/x",
        # Claude Codeの`find`はbfsで、`-rm`で削除する。findは許可リストで判定する。
        "find tmp -name x -rm",
        "find . -name x -delete",
        "find . -exec rm x +",
        "find . -execdir rm x +",
        "find . -fprint x",
        "find . -fls x",
        "find . -okdir rm x +",
        "find . -newerXY x",
        "python -m pytest -k @args.txt",
        "python -m pytest -m @args.txt",
        # 演算子と対になる記号は、それぞれ単独の入力で固定する。
        "ls <(touch x)",
        "(touch x)",
        # PowerShellでは`echo (…)`が副式として実行される。括弧は片方ずつ固定する。
        "echo (touch x",
        "echo touch x)",
        "cat < README.md",
        "echo a >& README.md",
        "echo a &> README.md",
        "echo {",
        "echo }",
        # shlexの注釈として語の途中の`#`以降を捨てると、後続のコマンドを見落とす。
        "echo a#b ; touch x",
        # Gitとsortは長いOptionの省略形を受け付ける。
        "git grep --open=touch -e Must -- AGENTS.md",
        "git grep --op=touch -e Must",
        # 短いOptionを束ねると、`-O`の残りがPagerのコマンドになる。
        "git grep -nOtouch -e Must -- AGENTS.md",
        "git grep -Otouch -e Must",
        "git grep -inOsh -e Must",
        "rg --hostname-bin=touch --hyperlink-format=default -n Must",
        "python -m pytest @args.txt",
        "git log --outp=x",
        "sort --outp=x README.md",
        "sort -ro x README.md",
        "sort --compress-program=sh README.md",
        # pytestは許可したOptionだけを通す。
        "python -m pytest -o addopts=--trace",
        "python -m pytest --debug=x",
        "python -m pytest --log-file=x",
        "python -m pytest --pastebin=all",
        "python -m pytest -c x.ini",
        "python -m pytest --rootdir=x",
    ):
        assert _bash_reason(command) is not None, command

    # 拒否の理由に、使えない記法と言い換えの手がかりを示す。
    for command, hint in (
        ("git show HEAD@{1}", "SHA"),
        ("python -m pytest --tb short", "--tb=short"),
        ("git log -SOptimizer", "-S Optimizer"),
        ("cat src\\kvk\\x.py", "`/`"),
        ('grep "end$" README.md', "-x"),
        ('grep "\\bword" README.md', "-w"),
        ('grep "a\\.b" README.md', "[.]"),
        ('grep "\\(x\\)" README.md', "-F"),
        ("find . -mtime -1 -delete", "find"),
    ):
        reason = _bash_reason(command)
        assert reason is not None and hint in reason, command


@pytest.mark.parametrize("quote", ["“", "”", "„", "‘", "’"])
def test_read_only_agent_rejects_each_full_width_quote(quote: str) -> None:
    """shlexでは二重引用符の中の1語でも、PowerShellが引用符として扱う文字を拒否する。"""

    assert _bash_reason(f'echo "a{quote} ; rm README.md ; echo "') is not None


# 許可リストの判定の内側へ届く語と、必ず拒否する記号を混ぜてコマンドを作る。
COMMAND_WORDS = (
    "git",
    "-C",
    "..",
    "diff",
    "log",
    "grep",
    "-nO",
    "--open",
    "find",
    ".",
    "-name",
    "-exec",
    "-print",
    "-prune",
    "python",
    "-m",
    "pytest",
    "-k",
    "@x",
    "-q",
    "sort",
    "-o",
    "-nk2",
    "sed",
    "-n",
    "1p",
    "cat",
    "README.md",
    ";",
    "|",
    "&&",
    ">",
    "2>&1",
    "/dev/null",
    '"a b"',
)
ALWAYS_DENIED_MARKERS = ("\n", "`", "$", "\\", "{", "}", "“")


@given(
    st.lists(
        st.sampled_from(COMMAND_WORDS + ALWAYS_DENIED_MARKERS), min_size=1, max_size=8
    )
)
def test_read_only_agent_judges_any_command_without_errors(words: list[str]) -> None:
    """どんな組み合わせでも例外を出さずに判定し、拒否する記号を含めば必ず拒否する。"""

    command = " ".join(words)
    reason = _bash_reason(command)
    assert reason is None or isinstance(reason, str)
    if any(marker in command for marker in ALWAYS_DENIED_MARKERS):
        assert reason is not None, command


@given(st.text())
def test_read_only_agent_judges_any_text_without_errors(command: str) -> None:
    """任意の文字列でも例外を出さずに判定し、終了コードで素通しにしない。"""

    reason = _bash_reason(command)
    assert reason is None or isinstance(reason, str)


def _load_read_only_module() -> object:
    """読み取り専用HookをModuleとして読み込む。"""

    spec = importlib.util.spec_from_file_location(
        "enforce_read_only_agent", READ_ONLY_AGENT_SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# 設定を書き換えないテストで共有する。書き換えるテストは`_load_read_only_module`で別に読む。
_SHARED_READ_ONLY_MODULE = _load_read_only_module()


@pytest.mark.parametrize("windows", [False, True])
def test_read_only_agent_rejects_cmd_syntax_only_on_windows(windows: bool) -> None:
    """cmdの記法と食い違う単一引用符、`^`、`sort /O`は、Windowsでだけ拒否する。"""

    module = _load_read_only_module()
    module.WINDOWS_SHELL = windows  # type: ignore[attr-defined]
    for command in (
        "grep -n 'Must' AGENTS.md",
        "echo 'x & del README.md & rem '",
        "sort /O x README.md",
        # cmdでは`^"`が引用を始めず、`&`で後続のコマンドが実行される。
        'echo ^" & del x & "',
        # cmdは`%VAR:~start,len%`を展開し、Hookが見ていない引数を渡せる。
        "git diff %CMDCMDLINE:~-15,14% && echo --output=x.txt",
        # 遅延展開が有効なcmdでは、`!VAR!`も同じように展開される。
        "git diff !CMDCMDLINE:~-15,14! && echo --output=x.txt",
    ):
        reason = module._blocked_reason(  # type: ignore[attr-defined]
            _tool_payload("Bash", {"command": command})
        )
        assert (reason is not None) == windows, command
    assert (
        module._blocked_reason(  # type: ignore[attr-defined]
            _tool_payload("Bash", {"command": 'grep -n "Must" AGENTS.md'})
        )
        is None
    )


def test_read_only_agent_fails_closed_on_unreadable_input() -> None:
    """Hook入力やTool名を解析できない場合は拒否する。"""

    _assert_denies_unreadable_input(READ_ONLY_AGENT_SCRIPT)

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


def test_read_only_agent_restricts_codex_tool_calls() -> None:
    """CodexのSubagent内の入力でも、編集とAgent起動を拒否し、確認コマンドを通す。"""

    def codex_payload(tool_name: str, command: str) -> dict[str, object]:
        # Codexは`agent_id`と`agent_type`を加え、Shellと編集を`{"command": 文字列}`で渡す。
        return {
            "session_id": "parent",
            "turn_id": "turn",
            "agent_id": "thread",
            "agent_type": "kvk-test-reviewer",
            "hook_event_name": "PreToolUse",
            "permission_mode": "default",
            "tool_name": tool_name,
            "tool_input": {"command": command},
            "tool_use_id": "call",
        }

    for tool_name, command in (
        ("apply_patch", "*** Begin Patch\n*** Add File: x.md\n+x\n*** End Patch"),
        ("spawn_agent", "edit files"),
        ("Bash", "touch tmp/x"),
    ):
        decision = _read_only_decision(codex_payload(tool_name, command))
        assert decision is not None and decision[0] == "deny", tool_name

    assert _read_only_decision(codex_payload("Bash", "git diff --stat")) is None


def _review_report_decision(payload: object) -> str | None:
    """レビュー結果検査Hookが書き直しを求めた理由を返す。通す場合はNoneを返す。"""

    completed = _run_hook(REVIEW_REPORT_SCRIPT, payload)
    assert completed.returncode == 0, completed.stderr
    if completed.stdout == "":
        return None
    # 既定コードページへ依存しないよう、非ASCII文字をエスケープして出力する。
    assert completed.stdout.isascii()
    output = json.loads(completed.stdout)
    assert output["decision"] == "block"
    return str(output["reason"])


def _subagent_stop(agent_type: str, message: str) -> dict[str, object]:
    """SubagentStopの入力を作る。"""

    return {
        "hook_event_name": "SubagentStop",
        "agent_type": agent_type,
        "agent_id": "agent",
        "stop_hook_active": False,
        "last_assistant_message": message,
    }


def _agent_instructions() -> dict[str, str]:
    """正本のAgent定義から、名前と指示文の対応を返す。"""

    instructions: dict[str, str] = {}
    for path in sorted(AGENT_DEFINITION_DIRECTORY.glob("*.toml")):
        with path.open("rb") as source:
            definition = tomllib.load(source)
        instructions[definition["name"]] = definition["developer_instructions"]
    return instructions


def test_review_report_hook_checks_every_heading_the_instructions_require() -> None:
    """指示が見出しを求めるAgentごとに、どの見出しが欠けても書き直させる。"""

    headed_agents = {
        name
        for name, instructions in _agent_instructions().items()
        if "`## Must`" in instructions
    }
    assert headed_agents == set(CODE_REVIEW_AGENTS)
    for agent_type in sorted(headed_agents):
        assert (
            _review_report_decision(_subagent_stop(agent_type, VALID_REVIEW_REPORT))
            is None
        ), agent_type
        for heading in ("## Must", "## Should", "## Nice", "## 未確定"):
            assert f"`{heading}`" in _agent_instructions()[agent_type]
            lines = VALID_REVIEW_REPORT.splitlines()
            report = "\n".join(line for line in lines if line != heading)
            reason = _review_report_decision(_subagent_stop(agent_type, report))
            assert reason is not None and heading in reason, (agent_type, heading)


def test_review_report_hook_checks_the_evidence_table_in_the_instructions() -> None:
    """証拠担当は、指示に書いた判定表の見出し行を持つ結果だけを通す。"""

    instructions = _agent_instructions()["evidence-reviewer"]
    header = next(
        line.strip("`").split("`")[0]
        for line in instructions.splitlines()
        if line.startswith("`| 主張")
    )
    columns = [cell.strip() for cell in header.strip("|").split("|")]
    separator = "|" + "---|" * len(columns)
    row = "| C1 | verified | https://example.com | 2026-10-25 | なし |"
    report = "\n".join((header, separator, row))
    assert _review_report_decision(_subagent_stop("evidence-reviewer", report)) is None

    for column in columns:
        without_column = report.replace(f" {column} |", "", 1)
        reason = _review_report_decision(
            _subagent_stop("evidence-reviewer", without_column)
        )
        assert reason is not None, column

    # 列の順序が違う見出し行も、決めた表とはみなさない。
    swapped = report.replace("| 主張 | 判定 |", "| 判定 | 主張 |", 1)
    assert swapped != report
    assert _review_report_decision(_subagent_stop("evidence-reviewer", swapped))


def test_review_report_hook_asks_only_once() -> None:
    """見出しではない行の語を見出しとみなさず、書き直しの後は繰り返さない。"""

    plain = "Must: なし\nShould: なし\nNice: なし\n未確定: なし\n"
    reason = _review_report_decision(_subagent_stop("kvk-test-reviewer", plain))
    assert reason is not None
    for heading in ("## Must", "## Should", "## Nice", "## 未確定"):
        assert heading in reason

    retried = {**_subagent_stop("kvk-domain-reviewer", plain), "stop_hook_active": True}
    assert _review_report_decision(retried) is None


def _write_transcript(path: Path, entries: list[dict[str, object]]) -> Path:
    """Claude CodeのSubagentの記録と同じ形のJSONLを書く。"""

    path.write_text(
        "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in entries),
        encoding="utf-8",
    )
    return path


def _assistant(*content: dict[str, object]) -> dict[str, object]:
    """記録のassistant行を作る。"""

    return {"type": "assistant", "message": {"role": "assistant", "content": content}}


def _handback(report: str) -> dict[str, object]:
    """最終報告を返すTool呼び出しを作る。"""

    return {
        "type": "tool_use",
        "name": "SubagentHandback",
        "input": {"message": report},
    }


def test_review_report_hook_reads_reports_returned_by_tool(tmp_path: Path) -> None:
    """最終報告をTool呼び出しで返した場合は、記録から報告を読んで検査する。"""

    valid = _write_transcript(
        tmp_path / "valid.jsonl",
        [
            _assistant(
                {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}
            ),
            {"type": "user", "message": {"content": [{"type": "tool_result"}]}},
            _assistant(_handback(VALID_REVIEW_REPORT)),
            {"type": "user", "message": {"content": [{"type": "tool_result"}]}},
            _assistant({"type": "text", "text": "報告しました。"}),
        ],
    )
    for message in ("", "報告します。"):
        payload = {
            **_subagent_stop("kvk-test-reviewer", message),
            "agent_transcript_path": str(valid),
        }
        assert _review_report_decision(payload) is None, message

    invalid = _write_transcript(
        tmp_path / "invalid.jsonl", [_assistant(_handback("指摘はありません。"))]
    )
    payload = {
        **_subagent_stop("kvk-test-reviewer", ""),
        "agent_transcript_path": str(invalid),
    }
    reason = _review_report_decision(payload)
    assert reason is not None and "## Must" in reason

    # 報告を取り出せない場合は、書き漏れと区別できないため止めない。
    for transcript in (str(tmp_path / "missing.jsonl"), None):
        payload = {
            **_subagent_stop("kvk-test-reviewer", ""),
            "agent_transcript_path": transcript,
        }
        assert _review_report_decision(payload) is None, transcript


def test_review_report_hook_ignores_other_agents_and_unreadable_input() -> None:
    """対象外のAgentと解析できない入力では、作業を止めない。"""

    for agent_type in ("general-purpose", "Explore", "default"):
        assert _review_report_decision(_subagent_stop(agent_type, "結果")) is None
    without_message = _subagent_stop("kvk-test-reviewer", "")
    del without_message["last_assistant_message"]
    assert _review_report_decision(without_message) is None
    assert _review_report_decision([]) is None

    for raw_input in (b"not json", b"\xff\xfe"):
        completed = subprocess.run(
            [sys.executable, str(REVIEW_REPORT_SCRIPT)],
            input=raw_input,
            capture_output=True,
            check=False,
        )
        assert completed.returncode == 0
        assert completed.stdout == b""


def _codex_hooks() -> dict[str, list[dict[str, object]]]:
    """Codexの共有Hook設定を返す。"""

    return json.loads(CODEX_HOOKS_PATH.read_text(encoding="utf-8"))["hooks"]


def test_codex_hooks_register_repository_hooks() -> None:
    """Codexの共有Hookが、読み取り専用の強制、Git保護、結果の検査を登録する。"""

    hooks = _codex_hooks()

    def entries_running(event: str, script: str) -> list[dict[str, object]]:
        return [
            entry
            for entry in hooks[event]
            if any(script in hook["command"] for hook in entry["hooks"])
        ]

    read_only_entries = entries_running("PreToolUse", "enforce_read_only_agent.py")
    assert len(read_only_entries) == 1
    # CodexのSubagentは親のsandboxと承認設定を継承するため、書き込み得るToolを検査する。
    # Codexはmatcherを部分一致で評価する。
    matcher = re.compile(str(read_only_entries[0]["matcher"]))
    for tool_name in ("Bash", "apply_patch", "spawn_agent", "mcp__example__write"):
        assert matcher.search(tool_name), tool_name
    for tool_name in ("update_plan", "view_image", "WebSearch"):
        assert not matcher.search(tool_name), tool_name

    git_guard_entries = entries_running("PreToolUse", "block_dangerous_git.py")
    assert len(git_guard_entries) == 1
    assert git_guard_entries[0]["matcher"] == "Bash"
    assert len(entries_running("SubagentStop", "check_review_report.py")) == 1

    for entries in hooks.values():
        for entry in entries:
            for hook in entry["hooks"]:
                assert hook["type"] == "command"
                # Codexは作業Directoryで起動するため、Repositoryのルートから解決する。
                script = re.search(r"tools/hooks/\w+\.py", hook["command"])
                assert script is not None
                assert "git rev-parse --show-toplevel" in hook["command"]
                assert script.group() in hook["commandWindows"]
                assert "git rev-parse --show-toplevel" in hook["commandWindows"]


def _run_codex_hook(
    hook: dict[str, str], payload: object, cwd: Path
) -> subprocess.CompletedProcess[str]:
    """CodexがHookを起動する方法で、指定した作業Directoryから実行する。"""

    # CodexはUnixで`sh -lc`、Windowsで`cmd.exe /C "<command>"`としてHookを起動する。
    # ログインShellの`/etc/profile`はRunnerによってPATHを変えるため、テストでは`sh -c`を
    # 使い、検査の対象をコマンドの綴りと作業Directoryからの解決に絞る。
    if os.name == "nt":
        arguments: str | list[str] = f'cmd.exe /C "{hook["commandWindows"]}"'
    else:
        arguments = ["sh", "-c", hook["command"]]
    return subprocess.run(
        arguments,
        input=json.dumps(payload),
        cwd=cwd,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def _codex_hook_result(hook: dict[str, str], payload: object) -> dict[str, object]:
    """Repositoryの下位Directoryから起動したHookの出力を返す。"""

    completed = _run_codex_hook(hook, payload, PROJECT_ROOT / "tests")
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_codex_report_hook_does_not_continue_outside_a_repository(
    tmp_path: Path,
) -> None:
    """ルートを解決できないとき、SubagentStopが終了コード2で続行を求めない。"""

    # Codexは標準エラーがある終了コード2を続行の指示として扱い、繰り返しの上限がない。
    hook = next(
        hook
        for entry in _codex_hooks()["SubagentStop"]
        for hook in entry["hooks"]
        if "check_review_report.py" in hook["command"]
    )
    completed = _run_codex_hook(
        hook, _subagent_stop("kvk-test-reviewer", "指摘なし"), tmp_path
    )
    assert completed.returncode != 2, completed.stderr
    assert completed.stdout == ""


def test_codex_hook_commands_run_every_script_from_a_subdirectory() -> None:
    """Codexの全Hookが、作業Directoryにかかわらず同じScriptを実行して判定する。"""

    payloads = {
        "enforce_read_only_agent.py": {
            "hook_event_name": "PreToolUse",
            "agent_type": "kvk-test-reviewer",
            "tool_name": "apply_patch",
            "tool_input": {"command": "*** Begin Patch"},
        },
        "block_dangerous_git.py": {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "git push origin main"},
        },
        "check_review_report.py": _subagent_stop("kvk-test-reviewer", "指摘なし"),
    }
    executed: set[str] = set()
    for entries in _codex_hooks().values():
        for entry in entries:
            for hook in entry["hooks"]:
                script = next(name for name in payloads if name in hook["command"])
                output = _codex_hook_result(hook, payloads[script])
                if script == "check_review_report.py":
                    assert output["decision"] == "block"
                else:
                    decision = output["hookSpecificOutput"]["permissionDecision"]
                    assert decision == "deny", script
                executed.add(script)
    assert executed == set(payloads)


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

    report_arguments = [
        hook["args"] for entry in hooks["SubagentStop"] for hook in entry["hooks"]
    ]
    assert [
        "${CLAUDE_PROJECT_DIR}/tools/hooks/check_review_report.py"
    ] in report_arguments

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

    # 補助的なHookのため、解析できない入力では作業を止めず、ASCIIだけで出力する。
    for event in ("session-start", "stop"):
        for raw_input in (b"not json", b"\xff\xfe", b"[]"):
            broken = subprocess.run(
                [sys.executable, str(hook), event],
                input=raw_input,
                cwd=repository,
                capture_output=True,
                check=False,
            )
            assert broken.returncode == 0, (event, raw_input)
            assert broken.stdout.isascii(), (event, raw_input)
            assert b"decision" not in broken.stdout, (event, raw_input)


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

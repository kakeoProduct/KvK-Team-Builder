"""Playwright MCPでweb/をブラウザ操作して確かめる仕組み（ADR 0032）の契約を検証する。"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLAYWRIGHT_MCP_VERSION = "0.0.83"
CHROMIUM_PATH = "/usr/bin/chromium"
WEB_ORIGIN = "http://127.0.0.1:8765"
# lockfileの版を起動し、見つからなければ取得せずに失敗させる（`--no`）。`--`がないと、npxが
# `--executable-path`などをnpmの設定として読み取り、サーバーへ渡さない。
PLAYWRIGHT_MCP_ARGS = [
    "--no",
    "--",
    "playwright-mcp",
    "--headless",
    "--isolated",
    "--no-sandbox",
    "--allowed-origins",
    WEB_ORIGIN,
    "--executable-path",
    CHROMIUM_PATH,
    "--output-dir",
    "tmp/playwright-mcp",
]
# 空白のない注釈（`//state.value`）やSVGの名前空間にも一致するが、失敗する側に倒れるため許容する。
EXTERNAL_URL = re.compile(
    r"(?:https?|wss?)://(?!127\.0\.0\.1(?::\d+)?(?:[/\"'\s)]|$))[^\s\"'<>)]+"
    r"|(?<![:/])//(?:[^\s/@\"'<>]+@)?(?:[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}|\d{1,3}(?:\.\d{1,3}){3})",
    re.IGNORECASE,
)
WEB_RESOURCE_SUFFIXES = {".html", ".htm", ".js", ".mjs", ".css", ".svg"}
# Git保護のHookや`.env`の拒否を迂回するため`permissions.deny`で拒否するTool。版を上げて名前が
# 変わると、拒否は黙って効かなくなる（ADR 0032）。
DENIED_TOOLS = ("browser_run_code_unsafe", "browser_drop", "browser_file_upload")


def _read_json(relative_path: str) -> dict:
    return json.loads((PROJECT_ROOT / relative_path).read_text(encoding="utf-8"))


def _configured_args() -> list[list[str]]:
    """Claude CodeとCodexの設定に書いたサーバーの引数を返す。"""

    claude = _read_json(".mcp.json")["mcpServers"]["playwright"]["args"]
    codex = tomllib.loads(
        (PROJECT_ROOT / ".codex" / "config.toml").read_text(encoding="utf-8")
    )["mcp_servers"]["playwright"]["args"]
    return [claude, codex]


def _option_value(args: list[str], option: str) -> str:
    assert args.count(option) == 1, option
    return args[args.index(option) + 1]


def test_playwright_mcp_version_matches_this_contract() -> None:
    """Playwright MCPの版は、この検査が確かめた版である（lockは開発依存の検査が確かめる）。"""

    package = _read_json("package.json")
    assert package["devDependencies"]["@playwright/mcp"] == PLAYWRIGHT_MCP_VERSION


def test_npm_ci_does_not_download_browsers() -> None:
    """`npm ci`はinstall時のScriptを実行する依存を持たず、CIでブラウザを取得しない。"""

    lock = _read_json("package-lock.json")
    with_install_script = [
        name
        for name, entry in lock["packages"].items()
        if entry.get("hasInstallScript")
    ]
    assert with_install_script == []


def test_claude_code_and_codex_start_the_same_locked_server() -> None:
    """Claude CodeとCodexは、同じ引数でlockfileの版のサーバーを起動する。"""

    expected = {"command": "npx", "args": PLAYWRIGHT_MCP_ARGS}

    claude = _read_json(".mcp.json")
    assert claude == {"mcpServers": {"playwright": expected}}

    codex = tomllib.loads(
        (PROJECT_ROOT / ".codex" / "config.toml").read_text(encoding="utf-8")
    )
    assert codex == {"mcp_servers": {"playwright": expected}}


def test_browser_runs_headless_in_memory_and_names_outputs_under_ignored_tmp() -> None:
    """ブラウザは画面なしで閲覧データを残さず、自動で名前を付けた出力はGit管理外の`tmp/`へ書く。

    名前を指定した出力は作業ツリーからの相対で解決されるため、この設定では限れない。
    Claude Codeでは`restrict_browser_files.py`が`tmp/playwright-mcp/`の下に限る（ADR 0032）。
    """

    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "\n/tmp/\n" in gitignore
    for args in _configured_args():
        assert "--headless" in args
        assert "--isolated" in args
        assert _option_value(args, "--output-dir").startswith("tmp/")


def test_unsandboxed_browser_is_pointed_only_at_the_local_web_server() -> None:
    """sandboxを外したブラウザの要求先を、ローカルで配信するweb/のoriginに限る（ADR 0032）。

    Dockerの既定のseccompがuser namespaceを禁じ、Containerの中ではChromiumのsandboxを使えない。
    利用者は2026-11-03に、Containerの制限を緩めず、接続先を限って`--no-sandbox`を使うと決めた。
    上流は`--allowed-origins`を安全境界ではないとしており、残る前提は「外部の資源を読まない
    自作のweb/だけを開く」ことである。この検査は設定の値だけを確かめる。
    """

    for args in _configured_args():
        assert "--no-sandbox" in args
        assert _option_value(args, "--allowed-origins").split(";") == [WEB_ORIGIN]


@pytest.mark.parametrize(
    "text",
    [
        '<script src="https://cdn.example.com/x.js">',
        "src='//fonts.gstatic.com/x'",
        "new WebSocket('wss://a.example.com')",
        "fetch('https://203.0.113.5/x.js')",
        "fetch('https://u@cdn.example.com/x.js')",
        "src='//203.0.113.5/x.js'",
        "src='//u@cdn.example.com/x.js'",
        "fetch('http://127.0.0.1:8765@cdn.example.com/x.js')",
        "fetch('http://127.0.0.1.example.com/x.js')",
        "fetch('HTTPS://CDN.EXAMPLE.COM/x.js')",
    ],
)
def test_external_url_pattern_finds_external_resources(text: str) -> None:
    assert EXTERNAL_URL.search(text)


@pytest.mark.parametrize(
    "text",
    [
        "http://127.0.0.1:8765/index.html",
        "fetch('http://127.0.0.1:8765')",
        "// comment.here",
        "a // b",
        "//1.5倍",
    ],
)
def test_external_url_pattern_ignores_local_origin_and_comments(text: str) -> None:
    assert not EXTERNAL_URL.search(text)


def test_web_tools_do_not_load_external_resources() -> None:
    """sandboxを外して開く前提（ADR 0032）が崩れないよう、web/のページは外部のURLを持たない。"""

    pages = [
        path
        for path in (PROJECT_ROOT / "web").rglob("*")
        if path.is_file() and path.suffix.lower() in WEB_RESOURCE_SUFFIXES
    ]
    assert {"index.html", "pet-bonus.js"} <= {path.name for path in pages}
    found = {
        path.name: matches
        for path in pages
        if (matches := EXTERNAL_URL.findall(path.read_text(encoding="utf-8")))
    }
    assert not found, (
        f"web/に外部のURLがあります: {found}。sandboxを外したブラウザで開くため、"
        "ADR 0032の判断を見直してください。"
    )


def test_deny_rules_match_the_denied_tools() -> None:
    """Playwright MCPの拒否の規則は、綴りの違いも余りもなく`DENIED_TOOLS`と一致する。"""

    prefix = "mcp__playwright__"
    deny = _read_json(".claude/settings.json")["permissions"]["deny"]
    assert {rule for rule in deny if rule.startswith(prefix)} == {
        f"{prefix}{tool}" for tool in DENIED_TOOLS
    }


def test_documents_tell_every_client_what_not_to_use() -> None:
    """Codexでは文書の規則が唯一の防ぎのため、共通の規約と手順の両方に書く（ADR 0032）。"""

    development = (PROJECT_ROOT / "DEVELOPMENT.md").read_text(encoding="utf-8")
    agents = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for tool in DENIED_TOOLS:
        assert tool in agents
        assert tool in development
    assert "`browser_file_upload`は使わない" in agents
    assert "この3つを使わず" in development
    assert "`filename`は`tmp/playwright-mcp/`から始める" in agents
    assert "`filename`は`tmp/playwright-mcp/`から始めます" in development


def test_installed_server_matches_the_guarded_tools_and_arguments() -> None:
    """固定した版のToolと、ファイルにつながる引数が、拒否とHookの前提どおりである。

    版を上げてTool名や引数名が変わると、拒否とHookは黙って効かなくなる。`npm ci`前の環境では
    skipする。CIは`npm ci`の後に実行する。
    """

    server = PROJECT_ROOT / "node_modules" / "@playwright" / "mcp"
    if not (PROJECT_ROOT / "node_modules").is_dir():
        pytest.skip("`npm ci`を実行していません")
    assert _read_json("node_modules/@playwright/mcp/package.json")["version"] == (
        PLAYWRIGHT_MCP_VERSION
    )
    readme = (server / "README.md").read_text(encoding="utf-8")
    for tool in DENIED_TOOLS:
        assert f"**{tool}**" in readme

    sections = re.split(r"^- \*\*(browser_\w+)\*\*", readme, flags=re.MULTILINE)[1:]
    tool_arguments = {
        tool: set(re.findall(r"^\s*- `(\w+)` \(", section, re.MULTILINE))
        for tool, section in zip(sections[0::2], sections[1::2], strict=True)
    }
    file_arguments = {
        name
        for arguments in tool_arguments.values()
        for name in arguments
        if re.search(r"file|path|dir|cwd", name, re.IGNORECASE)
    }
    # `filename`はHookが限り、`paths`は拒否した2つのToolだけが持つ。`path`はCookieの属性である。
    assert file_arguments == {"filename", "paths", "path"}

    def tools_with(argument: str) -> set[str]:
        return {tool for tool, names in tool_arguments.items() if argument in names}

    assert tools_with("paths") == {"browser_drop", "browser_file_upload"}
    assert tools_with("path") == {"browser_cookie_list", "browser_cookie_set"}


def test_install_runs_no_package_scripts() -> None:
    """`npm ci`でRepository自身のScriptを実行せず、ブラウザの取得も起こさない。"""

    assert "scripts" not in _read_json("package.json")


def test_documented_steps_match_the_configured_origin_and_output() -> None:
    """手順の配信コマンド、接続先、出力先を、サーバーの設定の値とそろえる。"""

    port = WEB_ORIGIN.rsplit(":", 1)[1]
    development = (PROJECT_ROOT / "DEVELOPMENT.md").read_text(encoding="utf-8")
    agents = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert f"python -m http.server {port} --bind 127.0.0.1 --directory web" in (
        development
    )
    assert WEB_ORIGIN in development
    assert WEB_ORIGIN in agents
    for args in _configured_args():
        output_dir = _option_value(args, "--output-dir")
        assert f"`{output_dir}/`" in development
        assert f"`{output_dir}/`" in agents


def test_dev_container_provides_the_browser_and_japanese_fonts() -> None:
    """Dev Containerはイメージの作成時に、MCPが起動するChromiumと日本語・絵文字のフォントを入れる。

    sudoは作業ツリーの所有者をそろえるScriptにしか許していない（ADR 0016）ため、
    Containerを作った後にはブラウザの共有ライブラリを入れられない。
    """

    dockerfile = (PROJECT_ROOT / ".devcontainer" / "Dockerfile").read_text(
        encoding="utf-8"
    )
    # 最終stageの注釈を除き、行末の`\`で続く行を1つの命令へつなぎ、`&&`で区切ったコマンドごとに
    # tokenを比べる。Node.jsを複写するだけの前のstageや注釈の記述では合格しない。
    final_stage = dockerfile[dockerfile.rindex("\nFROM ") :]
    instructions = "\n".join(
        line for line in final_stage.splitlines() if not line.lstrip().startswith("#")
    )
    commands = re.split(r"&&|\n", re.sub(r"\\\n", " ", instructions))
    install_tokens = [
        set(command.split()) for command in commands if "apt-get install" in command
    ]
    required = {
        "--no-install-recommends",
        "chromium",
        "fonts-noto-cjk",
        "fonts-noto-color-emoji",
    }
    assert any(required <= tokens for tokens in install_tokens), install_tokens
    for args in _configured_args():
        assert _option_value(args, "--executable-path") == CHROMIUM_PATH

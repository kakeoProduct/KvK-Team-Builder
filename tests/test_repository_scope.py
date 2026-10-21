"""Python処理と独立したブラウザ用補助ツールの境界を検証する。"""

from __future__ import annotations

import re
import subprocess
import tomllib
import unicodedata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 公開Repositoryで検索に当たらないよう伏せる語（ADR 0026）。この検査自身が当たらないよう、
# 英字、カタカナ、ひらがなの表記と、イベント名（2つの字体）をコードポイントで持つ。
HIDDEN_WORDS = tuple(
    "".join(map(chr, codes))
    for codes in (
        (0x6B, 0x69, 0x6E, 0x67, 0x73, 0x68, 0x6F, 0x74),
        (0x30AD, 0x30F3, 0x30B0, 0x30B7, 0x30E7, 0x30C3, 0x30C8),
        (0x304D, 0x3093, 0x3050, 0x3057, 0x3087, 0x3063, 0x3068),
        (0x708E, 0x9F8D),
        (0x708E, 0x7ADC),
    )
)
SEPARATORS = re.compile(r"[\s\-_・.／/]+")


def _normalize(text: str) -> str:
    """全角と半角、大文字と小文字、区切り文字の違いをなくす。"""

    return SEPARATORS.sub("", unicodedata.normalize("NFKC", text).casefold())


def _hidden_word_hits(text: str) -> list[str]:
    """正規化した文に含まれる伏せる語を返す。"""

    normalized = _normalize(text)
    return [word for word in HIDDEN_WORDS if _normalize(word) in normalized]


def _tracked_paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=True,
    )
    return [path for path in result.stdout.decode("utf-8").split("\0") if path]


def test_hidden_words_are_detected_after_normalization() -> None:
    """表記ゆれ（大文字、空白、全角、半角カナ、中黒、改行）も検出できることを確かめる。"""

    english, katakana, hiragana, event, event_variant = HIDDEN_WORDS
    wide = english.translate({code: code + 0xFEE0 for code in range(0x21, 0x7F)})
    half_katakana = "".join(
        map(chr, (0xFF77, 0xFF9D, 0xFF78, 0xFF9E, 0xFF7C, 0xFF6E, 0xFF6F, 0xFF84))
    )
    variants = {
        f"{english[:4].upper()} {english[4:].title()}": english,
        wide: english,
        f"{english[:4]}-{english[4:]}": english,
        f"{english[:4]}\n{english[4:]}": english,
        f"{katakana[:3]}・{katakana[3:]}": katakana,
        half_katakana: katakana,
        hiragana: hiragana,
        f"{event[0]}　{event[1]}": event,
        event_variant: event_variant,
    }
    for variant, expected in variants.items():
        assert expected in _hidden_word_hits(f"前{variant}後"), variant
    assert _hidden_word_hits("KvK Team Builder") == []


def test_tracked_files_do_not_contain_hidden_words() -> None:
    """追跡するファイルのパスと内容に、伏せる語が入っていない（ADR 0026）。

    UTF-8で読めないファイルは検査を素通りするため、読み飛ばさず失敗にする。
    """

    paths = _tracked_paths()
    assert "README.md" in paths
    found: set[str] = set()
    undecodable: list[str] = []
    for relative in paths:
        if _hidden_word_hits(relative):
            found.add(relative)
        path = PROJECT_ROOT / relative
        if not path.is_file():
            continue
        try:
            content = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            undecodable.append(relative)
            continue
        if _hidden_word_hits(content):
            found.add(relative)
    assert sorted(found) == []
    assert undecodable == []


def test_web_tools_are_excluded_from_python_quality_gate() -> None:
    """web/の単体HTMLツールをRuffの対象外とし、文書へ境界を明記する。"""

    with (PROJECT_ROOT / "pyproject.toml").open("rb") as source:
        pyproject = tomllib.load(source)
    assert "web" in pyproject["tool"]["ruff"]["extend-exclude"]
    assert pyproject["tool"]["mypy"]["files"] == ["src"]
    assert pyproject["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]

    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    architecture = (PROJECT_ROOT / "docs" / "architecture.md").read_text(
        encoding="utf-8"
    )
    assert "web/" in readme
    assert "## ブラウザ用補助ツールの境界" in architecture
    assert (
        PROJECT_ROOT / "docs" / "adr" / "0013-separate-web-tools-from-python-scope.md"
    ).is_file()


def test_every_web_tool_has_requirements_specification() -> None:
    """web/直下の各HTMLを要件定義書の索引へ載せ、リンク先の文書が存在する。"""

    requirements_dir = PROJECT_ROOT / "docs" / "requirements" / "web-tools"
    index = (requirements_dir / "README.md").read_text(encoding="utf-8")

    html_files = sorted((PROJECT_ROOT / "web").glob("*.html"))
    assert html_files
    for html_file in html_files:
        assert f"`web/{html_file.name}`" in index, html_file.name

    linked_documents = re.findall(r"\]\(([\w-]+\.md)\)", index)
    assert linked_documents
    for document in linked_documents:
        assert (requirements_dir / document).is_file(), document


def test_repository_structure_is_decided_by_adr() -> None:
    """モノリポジトリの構成とコンテキスト分割をADRと正本文書でそろえる。"""

    adr = (
        PROJECT_ROOT / "docs" / "adr" / "0021-repository-structure-and-contexts.md"
    ).read_text(encoding="utf-8")
    for required in (
        "src/kvk_team/",
        "team_building",
        "battle_timing",
        "interfaces",
        "frontend/",
        "npm",
        "ADR 0003",
        "ADR 0013",
    ):
        assert required in adr, required

    domain_model = (PROJECT_ROOT / "docs" / "domain-model.md").read_text(
        encoding="utf-8"
    )
    for required in ("src/kvk_team/", "`team_building`", "`battle_timing`"):
        assert required in domain_model, required

    architecture = (PROJECT_ROOT / "docs" / "architecture.md").read_text(
        encoding="utf-8"
    )
    assert "## リポジトリ構成" in architecture
    for path in ("AGENTS.md", "README.md"):
        text = (PROJECT_ROOT / path).read_text(encoding="utf-8")
        assert "ADR 0021" in text, path


TEAM_BUILDING_REQUIREMENTS = PROJECT_ROOT / "docs" / "requirements" / "team-building"
REQUIREMENT_ID = re.compile(r"^(?:ROS|FRM|OUT|UI|D|Q)-\d{3}$")
ID_REFERENCE = re.compile(r"(?<![A-Za-z0-9旧-])((?:ROS|FRM|OUT|UI|D)-\d{3})(?!\d)")
QUESTION_REFERENCE = re.compile(r"(?<![A-Za-z0-9旧-])(Q-\d{3})(?!\d)")
RETIRED_QUESTION = re.compile(r"旧(Q-\d{3})")


def _id_tables(text: str) -> list[list[str]]:
    """1列目の見出しが「ID」の表について、本文の行の1列目を返す。"""

    tables: list[list[str]] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("|") and cells[0] == "ID" and index + 1 < len(lines):
            rows: list[str] = []
            for row in lines[index + 2 :]:
                if not row.startswith("|"):
                    break
                rows.append(row.strip().strip("|").split("|")[0].strip())
            tables.append(rows)
    return tables


def _classification_table(text: str) -> set[str]:
    """総則の「要件の分類」の表から、分類の値を返す。"""

    heading = "### 2.1 要件の分類"
    assert heading in text, "総則に「要件の分類」の見出しがない"
    section = text.split(heading, 1)[1].split("\n#", 1)[0]
    values: set[str] = set()
    for line in section.splitlines()[1:]:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("|") and cells[0] not in {"分類", "---"}:
            values.add(cells[0])
    return values


def test_team_building_requirements_are_indexed_and_ids_are_unique() -> None:
    """編成の要件定義書を索引からたどれ、要件IDが一意で、参照先が実在する。"""

    index = (TEAM_BUILDING_REQUIREMENTS / "README.md").read_text(encoding="utf-8")
    linked = list(dict.fromkeys(re.findall(r"\]\(([\w-]+\.md)\)", index)))
    assert "open-questions.md" in linked
    documents = ["README.md", *linked]
    assert {path.name for path in TEAM_BUILDING_REQUIREMENTS.glob("*.md")} == set(
        documents
    )

    texts = {
        name: (TEAM_BUILDING_REQUIREMENTS / name).read_text(encoding="utf-8")
        for name in documents
    }
    defined: dict[str, str] = {}
    for name, text in texts.items():
        ids = [row for table in _id_tables(text) for row in table]
        if name != "open-questions.md":
            assert ids, name
        for requirement_id in ids:
            assert REQUIREMENT_ID.match(requirement_id), (name, requirement_id)
            assert requirement_id not in defined, (requirement_id, name)
            defined[requirement_id] = name

    whole = "\n".join(texts.values())
    for reference in ID_REFERENCE.findall(whole):
        assert reference in defined, reference

    retired = set(RETIRED_QUESTION.findall(texts["open-questions.md"]))
    open_questions = {key for key in defined if key.startswith("Q-")}
    assert not retired & open_questions
    # 「旧」を付けない参照は未決事項だけを指す。決定済みの事項は「旧Q-」で参照する
    for reference in QUESTION_REFERENCE.findall(whole):
        assert reference in open_questions, reference

    # 本文が根拠にする旧Qは、決定済みの事項の表に記録されている
    decided_rows = [
        line
        for line in texts["open-questions.md"].splitlines()
        if line.startswith("|") and RETIRED_QUESTION.search(line.split("|")[1])
    ]
    decided = {
        question
        for line in decided_rows
        for question in RETIRED_QUESTION.findall(line.split("|")[1])
    }
    for name, text in texts.items():
        for reference in RETIRED_QUESTION.findall(text):
            assert reference in decided, (name, reference)

    # 決定済みの事項は、1つの番号を1行だけに記録する
    recorded = [
        question
        for line in decided_rows
        for question in RETIRED_QUESTION.findall(line.split("|")[1])
    ]
    assert len(recorded) == len(set(recorded)), sorted(recorded)

    # 本文が参照する作成者の仮定は、仮定の表に1行だけある
    assumptions = re.findall(
        r"^\| (A-\d{2}) \|", texts["open-questions.md"], flags=re.MULTILINE
    )
    assert len(assumptions) == len(set(assumptions)), assumptions
    retracted = set(
        re.findall(
            r"^\| (A-\d{2}) \| （取り下げ）",
            texts["open-questions.md"],
            flags=re.MULTILINE,
        )
    )
    retracted_rows = [
        line
        for line in texts["open-questions.md"].splitlines()
        if re.match(r"^\| A-\d{2} \|", line) and "取り下げ" in line
    ]
    assert len(retracted_rows) == len(retracted), retracted_rows
    found = set()
    for name, text in texts.items():
        body = "\n".join(
            line for line in text.splitlines() if not re.match(r"^\| A-\d{2} \|", line)
        )
        # \wは日本語にも一致するため、境界はASCIIの文字で判定する
        for reference in re.findall(r"(?<![A-Za-z0-9_-])(A-\d{2})(?!\d)", body):
            assert reference in assumptions, (name, reference)
            assert reference not in retracted, (name, reference)
            found.add(reference)
    # 照合が空振りしていないことと、取り下げていない仮定がすべて参照されていることを確かめる
    assert found == set(assumptions) - retracted, sorted(
        set(assumptions) - retracted - found
    )

    # FRM-037の指標の番号への参照は、FRM-037の定義にある番号だけを使う
    objective = re.search(
        r"^\| FRM-037 \|.*$", texts["formation-rules.md"], flags=re.MULTILINE
    )
    assert objective is not None
    circled = "⓪①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
    # 参照（「⑨⑩は、」のように丸数字、「は」、読点が続くもの）を除き、定義を出現順に集める
    objective_marks = re.findall(
        rf"([{circled}])(?![{circled}]*は、)", objective.group(0)
    )
    # 定義は①から欠けなく連番で並ぶ
    assert objective_marks == list(circled[1 : len(objective_marks) + 1]), (
        objective_marks
    )
    referenced = set()
    for name, text in texts.items():
        for marks in re.findall(rf"FRM-037の?([{circled}]+)", text):
            for mark in marks:
                assert mark in objective_marks, (name, mark)
                referenced.add(mark)
    # 照合が空振りしていないことを確かめる
    assert {"③", "⑤", "⑧", "⑨", "⑩"} <= referenced, sorted(referenced)

    # Qの番号は再利用せず、欠けもない。未決か決定済みのどちらかに必ずある
    numbers = sorted(int(key[2:]) for key in open_questions | decided)
    assert numbers == list(range(1, numbers[-1] + 1)), numbers

    # 要件の分類は総則2.1の分類表にある値だけを使う
    categories = _classification_table(texts["README.md"])
    assert {"必須条件", "警告", "目的関数", "廃止"} <= categories
    for name, text in texts.items():
        for line in text.splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if line.startswith("|") and REQUIREMENT_ID.match(cells[0]):
                if cells[0].startswith(("Q-", "D-")):
                    continue
                assert cells[1] in categories, (name, cells[0], cells[1])

    agents = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "docs/requirements/team-building/" in agents
    assert "ADR 0023" in agents
    assert (
        PROJECT_ROOT
        / "docs"
        / "adr"
        / "0023-team-building-requirements-specification.md"
    ).is_file()

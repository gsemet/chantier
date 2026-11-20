"""`validate`: a whole planning folder checked, read-only, on trees built by hand."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from conftest import Chantier, Surface

from chantier.core.errors import EXIT_CONFLICT, EXIT_USAGE

INTENT = {"1-inbox/a/01-intent.md": "# A\n"}
LAYOUT = 'not in a CR folder\'s layout (concepts.md, "Change Request")'
NO_REQUEST = (
    "no request (no intake/*.md, 01-intent.md or 03-change-spec.md) → "
    "write its request or move the folder out"
)
FILE_IN_STAGE = (
    "a file in a stage folder, not a CR → move it into a CR folder or out of the planning folder"
)
LINKS = """# Links

[broken](../../P1/x/01-intent.md) and [again](../../P1/x/01-intent.md)
`[span](../../P1/zz/01-intent.md)`

```
[fenced](../../P1/zz/01-intent.md)
```

[web](https://example.org/a.md) ![image](../../P1/img/01-intent.md)
[outside](../../../../AGENTS.md)
"""
ARCHIVE_LINES = 3
ELEVEN = 11
LONG = "t" * 73
WRITE = 'write a short "# Title" line (at most 72 characters) at its top, the text below it'
BAD_LABEL = json.dumps({"title": "T", "summary": "S", "labels": ["Bad"]})


def summary(**fields: object) -> str:
    return json.dumps({"schema": 1, "title": "T", "summary": "S", **fields})


def build(base: Path, files: dict[str, str]) -> None:
    """Plain files and folders (a name ending in `/` is a folder)."""
    for name, text in files.items():
        path = base / name
        if name.endswith("/"):
            path.mkdir(parents=True, exist_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")


def snapshot(base: Path) -> dict[str, bytes]:
    return {p.relative_to(base).as_posix(): p.read_bytes() for p in base.rglob("*") if p.is_file()}


@pytest.mark.parametrize("cell", ["repo", "surface"])
def test_a_planning_folder_made_by_the_cli_validates_and_nothing_is_written(
    cell: str, chantier: Chantier, request: pytest.FixtureRequest
) -> None:
    place = request.getfixturevalue(cell)
    base = (place / ".agents" / "changes") if isinstance(place, Path) else place.project / "changes"
    if cell == "repo":
        assert chantier("init")[0] == 0
    for title in ("Fix login", "Add export"):
        assert chantier("file", title)[0] == 0
    _, lint, _ = chantier("summary", "lint")
    for line in lint[1:]:
        path = line.split(": ", 1)[0]
        assert chantier("summary", "set", path, "--title", "T", "--summary", "S")[0] == 0
    assert chantier("triage", path, "--priority", "P2")[0] == 0
    before = snapshot(base)
    assert chantier("validate") == (0, ["no error, no gap (2 CRs)"], "")
    assert snapshot(base) == before


ERRORS = {
    "no priority": (
        {"2-backlog/x/01-intent.md": "i"},
        "error 2-backlog/x: in 2-backlog without a P1..P4 folder → move it into 2-backlog/P<n>/ "
        "(`triage` reads no such folder)",
    ),
    "not a priority": ({"2-backlog/x/": ""}, "error 2-backlog/x: not a priority folder (P1..P4)"),
    "batch folder": (
        {"4-batch/zz/": ""},
        "error 4-batch/zz: not a batch state folder (1-pending, 2-actives, 3-done)",
    ),
    "top level": ({"loose/01-intent.md": "i"}, "error loose: a CR outside a stage folder"),
    "priority in ready": (
        {"3-ready/P2/x/01-intent.md": "i"},
        "error 3-ready/P2: a priority folder outside 2-backlog",
    ),
    "nested": (
        {**INTENT, "1-inbox/a/work/b/01-intent.md": "i"},
        "error 1-inbox/a/work/b: a CR inside the CR 1-inbox/a",
    ),
    "unreadable": (
        {**INTENT, "1-inbox/a/summary.json": "{"},
        "error 1-inbox/a/summary.json: unreadable (",
    ),
    "file for folder": (
        {**INTENT, "1-inbox/a/work": "x"},
        "error 1-inbox/a/work: a file where chantier reads a folder",
    ),
    "long summary title": (
        {**INTENT, "1-inbox/a/summary.json": summary(title=LONG)},
        "error 1-inbox/a/summary.json: title is 73 characters: the limit is 72 → "
        'summary set 1-inbox/a --title "<at most 72 characters>"',
    ),
    "long heading": (
        {"1-inbox/a/intake/request.md": f"# {LONG}\n\ntext\n"},
        f"error 1-inbox/a/intake/request.md: title is 73 characters: the limit is 72 → {WRITE}",
    ),
    "no heading": (
        {"1-inbox/a/intake/request.md": "one paragraph\nof words\n"},
        f'error 1-inbox/a/intake/request.md: no "# " heading → {WRITE}',
    ),
    "bad waits": (
        {**INTENT, "1-inbox/a/waits.json": "{"},
        "error 1-inbox/a/waits.json: waits.json is not valid:",
    ),
    "folder for file": (
        {**INTENT, "1-inbox/a/delivery.md/": ""},
        "error 1-inbox/a/delivery.md: a folder where chantier reads a file",
    ),
}


@pytest.mark.parametrize("name", list(ERRORS))
def test_what_chantier_misreads_is_an_error_and_exits_3(
    name: str, repo: Path, chantier: Chantier
) -> None:
    files, expected = ERRORS[name]
    build(repo / ".agents" / "changes", files)
    code, lines, err = chantier("validate")
    assert code == EXIT_CONFLICT, lines
    assert any(line.startswith(expected) for line in lines), lines
    assert re.fullmatch(r"\d+ error\(s\), \d+ gap\(s\) in \d+ CRs", lines[0]), lines
    assert not err


GAPS = {
    "label": (
        {**INTENT, "1-inbox/a/summary.json": BAD_LABEL},
        "gap 1-inbox/a/summary.json: label 'Bad': a label is lowercase",
    ),
    "schema": (
        {**INTENT, "1-inbox/a/summary.json": summary(schema=2)},
        "gap 1-inbox/a/summary.json: schema 2, this chantier reads 1",
    ),
    "file in stage": ({"1-inbox/note.md": "x"}, f"gap 1-inbox/note.md: {FILE_IN_STAGE}"),
    "no request": ({"1-inbox/a/work/n.txt": "x"}, f"gap 1-inbox/a: {NO_REQUEST}"),
    "unknown entry": (
        {**INTENT, "1-inbox/a/junk.txt": "x"},
        f"gap 1-inbox/a/junk.txt: {LAYOUT}",
    ),
    "waits in a batch": (
        {"4-batch/2-actives/a/01-intent.md": "# A\n", "4-batch/2-actives/a/waits.json": "{}"},
        f"gap 4-batch/2-actives/a/waits.json: {LAYOUT}",
    ),
    "broken link": (
        {"1-inbox/a/01-intent.md": LINKS},
        "gap 1-inbox/a/01-intent.md: link to ../../P1/x/01-intent.md does not resolve",
    ),
    "link by case": (
        {
            "1-inbox/x/01-intent.md": "i",
            "1-inbox/a/01-intent.md": "[x](../x/01-Intent.md)\n",
        },
        "gap 1-inbox/a/01-intent.md: link to ../x/01-Intent.md does not resolve",
    ),
}


@pytest.mark.parametrize("name", list(GAPS))
def test_a_gap_is_shown_and_passes(name: str, repo: Path, chantier: Chantier) -> None:
    files, expected = GAPS[name]
    build(repo / ".agents" / "changes", files)
    code, lines, _ = chantier("validate")
    assert code == 0, lines
    assert any(line.startswith(expected) for line in lines), lines
    assert re.fullmatch(r"\d+ gap\(s\) in \d+ CRs", lines[0]), lines
    if name == "broken link":
        assert len([x for x in lines if "link to" in x]) == 1, lines


TITLES = {
    "summary": ("summary.json", summary(title=LONG), "title is 73 characters: the limit is 72"),
    "heading": ("intake/request.md", f"# {LONG}\n", "title is 73 characters: the limit is 72"),
    "none": ("intake/request.md", "a paragraph\n", 'no "# " heading'),
}


@pytest.mark.parametrize(
    "place",
    ["4-batch/1-pending", "4-batch/2-actives", "4-batch/3-done", "5-archives", "6-trash"],
)
@pytest.mark.parametrize("kind", list(TITLES))
def test_a_long_title_or_a_missing_heading_is_a_gap_after_the_backlog(
    place: str, kind: str, repo: Path, chantier: Chantier
) -> None:
    name, text, message = TITLES[kind]
    build(repo / ".agents" / "changes", {f"{place}/a/{name}": text})
    code, lines, _ = chantier("validate")
    assert code == 0, lines
    found = [line for line in lines if line.startswith(f"gap {place}/a/{name}: {message}")]
    assert found, lines
    assert place != "6-trash" or "→" not in found[0], found  # `summary set` refuses in the trash


def test_a_title_of_the_limit_passes(repo: Path, chantier: Chantier) -> None:
    build(
        repo / ".agents" / "changes",
        {"1-inbox/a/intake/request.md": f"# {'t' * 72}\n\ntext\n"},
    )
    code, lines, _ = chantier("validate")
    assert code == 0, lines
    assert not any("title is" in line or "heading" in line for line in lines), lines


def test_a_waits_file_of_the_backlog_is_ok(repo: Path, chantier: Chantier) -> None:
    ok = json.dumps({"schema": 1, "waits": []})
    build(repo / ".agents" / "changes", {**INTENT, "1-inbox/a/waits.json": ok})
    assert not [x for x in chantier("validate")[1] if "waits.json" in x]


@pytest.mark.parametrize("late", [False, True])
def test_a_missing_or_late_summary_reads_as_summary_lint_says(
    late: bool, repo: Path, chantier: Chantier
) -> None:
    files = dict(INTENT)
    if late:
        files["1-inbox/a/summary.json"] = summary(sources={"01-intent.md": "0" * 64})
    build(repo / ".agents" / "changes", files)
    _, lint, _ = chantier("summary", "lint")
    code, lines, _ = chantier("validate")
    assert code == 0 and lines[1:] == [f"gap {line}" for line in lint[1:]], (lines, lint)


def test_an_error_comes_before_a_gap(repo: Path, chantier: Chantier) -> None:
    build(
        repo / ".agents" / "changes",
        {**INTENT, "1-inbox/a/summary.json": "{", "1-inbox/note.md": "x"},
    )
    code, lines, _ = chantier("validate")
    assert code == EXIT_CONFLICT and lines[0] == "1 error(s), 1 gap(s) in 1 CRs", lines
    assert lines[1].startswith("error ") and lines[2].startswith("gap "), lines


def test_the_archives_and_the_trash_keep_their_format_only(repo: Path, chantier: Chantier) -> None:
    base = repo / ".agents" / "changes"
    old = {"01-intent.md": LINKS, "junk.txt": "x"}
    build(base, {f"5-archives/x/{n}": t for n, t in old.items()})
    build(base, {"5-archives/x/summary.json": "{", "5-archives/batches/batch-01.json": "{}"})
    build(base, {"6-trash/y/summary.json": summary(title=LONG)})
    code, lines, _ = chantier("validate")
    assert code == EXIT_CONFLICT and len(lines) == ARCHIVE_LINES, lines
    assert lines[0] == "1 error(s), 1 gap(s) in 2 CRs"
    assert lines[1].startswith("error 5-archives/x/summary.json: unreadable (")
    assert lines[1].endswith("→ repair or remove it, then summary set 5-archives/x …")
    assert lines[2] == "gap 6-trash/y/summary.json: title is 73 characters: the limit is 72"


def test_validate_cannot_run_on_a_surface_without_a_project(
    surface: Surface, chantier: Chantier
) -> None:
    (surface.root / "projects" / "other" / "changes").mkdir(parents=True)
    code, lines, err = chantier("validate")
    assert (code, lines) == (EXIT_USAGE, []) and err.startswith("error: "), err
    assert "--project" in err


def test_validate_cannot_run_without_a_planning_folder(repo: Path, chantier: Chantier) -> None:
    code, lines, err = chantier("validate")
    assert (code, lines) == (EXIT_USAGE, []), lines
    assert err.startswith("error: no planning folder at "), err


def test_eleven_findings_are_all_printed(repo: Path, chantier: Chantier) -> None:
    build(repo / ".agents" / "changes", {f"1-inbox/n{i:02}.md": "x" for i in range(ELEVEN)})
    code, lines, _ = chantier("validate")
    assert code == 0 and len(lines) == ELEVEN + 1, lines
    assert lines[0] == "11 gap(s) in 0 CRs" and not any("more lines" in x for x in lines)

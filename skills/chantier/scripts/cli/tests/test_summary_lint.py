"""`summary lint`'s hint: the path it prints is the one `summary set` reads."""

import json
from pathlib import Path

import pytest
from conftest import Chantier

from chantier.core.errors import EXIT_PRECONDITION


@pytest.mark.parametrize("cell", ["repo", "surface"])
def test_the_summary_lint_hint_is_a_path_summary_set_reads(
    cell: str, chantier: Chantier, request: pytest.FixtureRequest
) -> None:
    place = request.getfixturevalue(cell)
    root = place if isinstance(place, Path) else place.root
    _, out, _ = chantier("file", "Fix login")
    folder = root / out[0].removeprefix("filed ").split(";")[0]
    (folder / "03-change-spec.md").write_text("# Fix login\n\nDo it.\n")
    code, lines, _ = chantier("summary", "lint")
    assert code == EXIT_PRECONDITION, lines
    command = lines[1].split("summary set ", 1)[1].split(" ")[0]
    assert not command.startswith((".agents/", "projects/")), command
    code, _, err = chantier("summary", "set", command, "--title", "T", "--summary", "S")
    assert code == 0, err
    assert chantier("summary", "lint") == (0, ["no gap (1 CRs)"], "")


def _filed(root: Path, name: str, files: dict[str, str]) -> Path:
    folder = root / ".agents" / "changes" / "1-inbox" / name
    for rel, text in files.items():
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_text(text, encoding="utf-8")
    return folder


LONG = "t" * 73
GAP_CASES = [
    pytest.param(
        (
            "intake/request.md",
            "a paragraph\n",
            {"title": "T", "summary": "S"},
            'no "# " heading → write a short "# Title" line (at most 72 characters) at its top',
        ),
        id="no heading",
    ),
    pytest.param(
        (
            "summary.json",
            "# T\n",
            {"title": LONG, "summary": "S"},
            'title is 73 characters: the limit is 72 → summary set 1-inbox/a --title "<at most 72',
        ),
        id="long title",
    ),
]


@pytest.mark.parametrize("case", GAP_CASES)
def test_a_missing_heading_and_a_long_title_are_gaps_that_exit_2(
    case: tuple[str, str, dict[str, str], str], repo: Path, chantier: Chantier
) -> None:
    name, request_text, summary, line = case
    folder = _filed(repo, "a", {"intake/request.md": request_text})
    (folder / "summary.json").write_text(json.dumps({"schema": 1, **summary}), encoding="utf-8")
    assert chantier("summary", "set", "1-inbox/a", "--unchanged")[0] == 0
    code, lines, _ = chantier("summary", "lint")
    assert code == EXIT_PRECONDITION, lines
    assert lines[1].startswith(f"1-inbox/a/{name}: {line}"), lines


def test_a_late_cr_without_a_heading_is_still_late_and_no_summary_names_the_limit(
    repo: Path, chantier: Chantier
) -> None:
    folder = _filed(repo, "a", {"intake/request.md": "a paragraph\n"})
    _, lines, _ = chantier("summary", "lint")
    assert '--title "<at most 72 characters>"' in lines[1], lines
    (folder / "summary.json").write_text(
        json.dumps(
            {"schema": 1, "title": "T", "summary": "S", "sources": {"intake/request.md": "0"}}
        ),
        encoding="utf-8",
    )
    _, lines, _ = chantier("summary", "lint")
    assert "summary late" in lines[1], lines

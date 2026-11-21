"""The card's text (`description`) never shows a frontmatter."""

from __future__ import annotations

from pathlib import Path

import pytest

from chantier.board.backlog import description
from chantier.store import FolderStore

FM = "---\ntype: cr-intent\nid: x\n---\n"
CASES = [
    pytest.param({"01-intent.md": FM + "\n# T\n\nThe text.\n"}, "The text.", id="frontmatter"),
    pytest.param(
        {"01-intent.md": FM.replace("\n", "\r\n") + "\r\nThe text.\r\n"},
        "The text.",
        id="crlf",
    ),
    pytest.param({"01-intent.md": "\ufeff" + FM + "\nThe text.\n"}, "The text.", id="bom"),
    pytest.param({"01-intent.md": "---\n---\nThe text.\n"}, "The text.", id="empty-frontmatter"),
    pytest.param(
        {"01-intent.md": FM + "\n# Only headings\n", "notes.md": "Next file."},
        "Next file.",
        id="only-frontmatter-falls-through",
    ),
    pytest.param(
        {"01-intent.md": "First paragraph.\n\n---\n\nAfter a rule.\n"},
        "First paragraph.",
        id="rule-lower-is-not-frontmatter",
    ),
    pytest.param({"01-intent.md": "Plain text.\n\nMore.\n"}, "Plain text.", id="no-frontmatter"),
]


@pytest.mark.parametrize(("files", "expected"), CASES)
def test_description_skips_a_frontmatter(
    tmp_path: Path, files: dict[str, str], expected: str
) -> None:
    for name, text in files.items():
        (tmp_path / name).write_bytes(text.encode("utf-8"))
    assert description(FolderStore(tmp_path), tmp_path) == expected

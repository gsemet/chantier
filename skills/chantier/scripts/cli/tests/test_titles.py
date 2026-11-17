"""A document's title (`markdown_title`) and a CR's shown title: never a front matter's `---`."""

from __future__ import annotations

from pathlib import Path

import pytest
from batch_helpers import FROM_AGENTS_MD, host, prepared, record
from conftest import Chantier

from chantier.core.files import markdown_title
from chantier.lifecycle.backlog import idea_slug
from chantier.status.views import _title, shown_title

FM = "---\ntype: cr-spec\ndescription: x\n---\n"
CASES = [
    pytest.param(FM + "\n# The title\n\nText.\n", "The title", id="heading-after-frontmatter"),
    pytest.param("﻿" + FM + "\n# The title\n", "The title", id="bom"),
    pytest.param((FM + "\n# The title\n").replace("\n", "\r\n"), "The title", id="crlf"),
    pytest.param(FM + "\nJust a line\n", "Just a line", id="no-heading-first-line"),
    pytest.param("Intro.\n\n## Below\n", "Below", id="heading-below-a-paragraph"),
    pytest.param(FM, "", id="only-frontmatter"),
    pytest.param("\n# Plain\n", "Plain", id="no-frontmatter"),
    pytest.param("---\ntype: x\n\n# Heading\n", "Heading", id="unclosed-fence"),
]


@pytest.mark.parametrize(("text", "expected"), CASES)
def test_markdown_title(text: str, expected: str) -> None:
    assert markdown_title(text) == expected


def test_a_title_behind_a_frontmatter_is_found_recorded_and_shown(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    folder = prepared(repo, chantier, "Placeholder")
    (folder / "03-change-spec.md").write_text(FM + "\n# Real title\n\nDo it.\n", encoding="utf-8")
    assert _title(folder) == "Real title"
    assert shown_title("---", folder) == "Real title"
    assert shown_title("Kept", folder) == "Kept"
    assert shown_title("---", None) == "---"
    assert shown_title("---", folder / "missing") == "---"
    code, _, err = chantier("open", str(folder), *FROM_AGENTS_MD)
    assert code == 0, err
    assert record(repo)["crs"][0]["title"] == "Real title"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param(FM + "\n# The title\n", "the-title", id="frontmatter-heading"),
        pytest.param("# Plain title\n", "plain-title", id="heading"),
        pytest.param("\n\nFirst line\nmore\n", "first-line", id="first-line"),
    ],
)
def test_idea_slug_uses_the_title_behind_a_frontmatter(text: str, expected: str) -> None:
    assert idea_slug(text) == expected

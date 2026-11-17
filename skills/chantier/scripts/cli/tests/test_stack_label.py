"""The label of a stack row: the CR's status and, with a PR, its recorded draft flag."""

from __future__ import annotations

import pytest

from chantier.commands.facts import stack_label
from chantier.core.records import CrEntry

GH = "https://github.com/o/r/pull/"
GL = "https://gitlab.com/g/p/-/merge_requests/"


@pytest.mark.parametrize(
    ("status", "pr", "draft", "label"),
    [
        ("ready", GH + "251", True, "ready, PR draft (#251)"),
        ("ready", GH + "250", False, "ready, PR out of draft (#250)"),
        ("working", GH + "253", True, "working, PR draft (#253)"),
        ("ready", GL + "12", None, "ready, PR draft not read (!12)"),
        ("blocked", "https://example.com/pr/", False, "blocked, PR out of draft"),
        ("queued", None, None, "queued"),
        ("ready", None, False, "ready"),
    ],
)
def test_a_stack_row_label(status: str, pr: str | None, draft: bool | None, label: str) -> None:
    c = CrEntry(id="CR-1", order=1, status=status, pr=pr, pr_draft=draft)
    assert stack_label(c) == label

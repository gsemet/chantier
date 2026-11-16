"""The surface file edit the Configuration page uses: comments kept, emptied maps removed."""

from __future__ import annotations

import pytest
from conftest import Surface

from chantier.core.repo import Repo
from chantier.playbook import edit

COPILOT_HEAD = "hosts:\n  copilot:\n    roles:\n      coder:\n"
A = "        "  # a role's key

COMMENTED = "# top\nboard:\n  port: 8123 # port\n"
HELD = COPILOT_HEAD + A + "model: default\n" + A + "agent: mine # mine\n"


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (COMMENTED + COPILOT_HEAD + A + "model: gpt-6.1-terra\n", COMMENTED),  # the maps go
        (HELD, COPILOT_HEAD + A + "agent: mine # mine\n"),  # a held reset goes with the key
        (COPILOT_HEAD + A + "model: ~\n", ""),
    ],
)
def test_the_surface_file_edit_keeps_comments_and_removes_what_it_empties(
    surface: Surface, start: str, end: str
) -> None:
    path = surface.project / "chantier.yaml"
    path.write_text(start, encoding="utf-8", newline="\n")
    repo = Repo.find(project="demo", readonly=True)
    view = edit.config_view(repo)
    change = [{"host": "copilot", "role": "coder", "key": "model", "value": None}]
    edit.edit_surface_file(repo, change, view["sha256"], False)
    assert path.read_text(encoding="utf-8") == end

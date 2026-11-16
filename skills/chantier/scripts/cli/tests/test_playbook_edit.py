"""The surface file edit the Configuration page uses: comments kept, emptied maps removed."""

from __future__ import annotations

import hashlib

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


@pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"])
def test_the_surface_file_edit_writes_lf_onto_a_crlf_file(surface: Surface, bom: bytes) -> None:
    path = surface.project / "chantier.yaml"
    path.write_bytes(bom + COMMENTED.replace("\n", "\r\n").encode("utf-8"))
    repo = Repo.find(project="demo", readonly=True)
    view = edit.config_view(repo)
    set_model = [{"host": "copilot", "role": "coder", "key": "model", "value": "gpt-6.1-terra"}]
    view = edit.edit_surface_file(repo, set_model, view["sha256"], False)
    data = path.read_bytes()
    assert b"\r" not in data
    assert data.startswith(bom)
    text = data.decode("utf-8-sig")
    assert "# top" in text
    assert "port: 8123 # port" in text
    assert "model: gpt-6.1-terra" in text
    assert view["sha256"] == hashlib.sha256(data).hexdigest()
    reset = [{"host": "copilot", "role": "coder", "key": "model", "value": None}]
    edit.edit_surface_file(repo, reset, view["sha256"], False)  # the new hash is the disk's
    assert "model:" not in path.read_text(encoding="utf-8")

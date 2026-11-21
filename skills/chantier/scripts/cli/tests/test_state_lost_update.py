"""`server.json`: a read that fails must never become a write from an empty file (the lost update
that dropped the `server` and `key` entries), and the board puts them back when they are lost."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from chantier.hub import state

FULL = {"key": "k", "created": "t", "server": {"pid": 1}, "hub": {"pid": 2}}


def _git(tmp_path: Path, text: str | None) -> Path:
    git = tmp_path / "git"
    if text is not None:
        state.path(git).parent.mkdir(parents=True)
        state.path(git).write_text(text, encoding="utf-8")
    return git


@pytest.mark.parametrize("failure", ["denied", "half-written"])
def test_a_bad_read_never_erases_the_other_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    text = json.dumps(FULL)
    git = _git(tmp_path, text if failure == "denied" else text[:10])
    if failure == "denied":

        def denied(_file: Path, *_a: Any) -> str:
            raise PermissionError("sharing violation")

        monkeypatch.setattr(state, "read_text", denied)
        monkeypatch.setattr(state, "READ_WIN_S", 0.05)
    assert state.read(git) == {}  # a reader still gets "no state"
    with pytest.raises(state.StateError):
        state.set_key(git, "new")
    monkeypatch.undo()
    assert state.path(git).read_text(encoding="utf-8") in (text, text[:10])


def test_the_board_puts_back_its_entry_and_key(tmp_path: Path) -> None:
    git = _git(tmp_path, json.dumps({"hub": {"pid": 2}}))
    state.write_server(git, "127.0.0.1", 1, "1", "x")

    def lose(data: dict[str, Any]) -> None:
        data.pop("server")
        data.pop("key", None)

    state.modify(git, lose)
    state.reassert_server(git, "k")
    got = state.read(git)
    assert got["key"] == "k" and got["server"]["port"] == 1 and got["hub"] == {"pid": 2}

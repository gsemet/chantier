"""A published write of a command, on an external surface, is refused with no live writer
(spec CR-404 C.8): exit 2, the text, nothing changed; in-project mode never asks for one.
The rows are Part B's command table (`test_store_command_table.py`)."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import Chantier, Surface
from store_spy import fingerprint, unguarded
from test_store_command_table import (  # noqa: F401 - fixtures of the table
    ROWS,
    Row,
    _prepare,
    states,
)
from test_store_command_table import world as table_world  # noqa: F401

from chantier import __version__
from chantier.core import clock
from chantier.core.errors import EXIT_PRECONDITION
from chantier.hub import state

REFUSED = "the surface's writer is not running"
CLI_ROWS = [r for r in ROWS if not r.command.startswith("board")]


def _no_writer(surface: Surface) -> Path:
    git_dir = surface.root / ".git"
    state.modify(git_dir, lambda data: data.pop(state.WRITER, None))
    return git_dir


@pytest.mark.parametrize("row", CLI_ROWS, ids=[r.name for r in CLI_ROWS])
def test_a_published_write_with_no_writer_is_refused_and_changes_nothing(
    row: Row,
    table_world: Callable[[str], Surface],  # noqa: F811
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if row.name == "close":  # no Foreman transcript in a test: nothing to price
        monkeypatch.setattr("chantier.commands.closing.final_rows", lambda *a: [])
    surface = table_world(row.state)
    argv = _prepare(row, surface, chantier)
    _no_writer(surface)
    before = fingerprint(surface.project)
    code, out, err = chantier(*argv)
    assert code == EXIT_PRECONDITION, (out, err)
    assert f"{row.command}: {REFUSED}: nothing written; for the Chief of Staff:" in err
    # the `.gitignore` of the local files is no published write: written before the check
    assert unguarded(fingerprint(surface.project)) == unguarded(before)


def test_with_a_live_writer_the_same_command_goes_through(
    table_world: Callable[[str], Surface],  # noqa: F811
    chantier: Chantier,
) -> None:
    surface = table_world("backlog")
    git_dir = _no_writer(surface)
    assert chantier("file", "An idea")[0] == EXIT_PRECONDITION
    record = {"pid": os.getpid(), "started": clock.now(), "state": "synced"}
    state.modify(git_dir, lambda data: data.__setitem__(state.WRITER, record))
    code, out, _ = chantier("file", "An idea")
    assert code == 0 and not [x for x in out if x.startswith("writer:")]  # synced: no note


@pytest.mark.parametrize(
    ("kind", "more", "note"),
    [
        ("pending", {"ahead": 2}, "writer: pending: not pushed yet (2 commits)"),
        ("pending", {}, "writer: pending: not pushed yet (0 paths)"),
        ("blocked", {"reason": "staged"}, "writer: blocked: not pushed yet (staged)"),
        ("offline", {"ahead": 1}, "writer: offline: not pushed yet (1 commits)"),
    ],
)
def test_a_write_the_writer_has_not_pushed_says_so_on_the_last_line(
    table_world: Callable[[str], Surface],  # noqa: F811
    chantier: Chantier,
    kind: str,
    more: dict[str, object],
    note: str,
) -> None:
    surface = table_world("backlog")
    record = {"pid": os.getpid(), "started": clock.now(), "state": kind, **more}
    state.modify(surface.root / ".git", lambda data: data.__setitem__(state.WRITER, record))
    code, out, _ = chantier("file", "An idea")
    assert code == 0 and out[-1] == note
    assert not [x for x in chantier("rules")[1] if "not pushed yet" in x]  # a read adds no note


def test_an_older_board_with_no_writer_is_named_in_the_refusal(
    table_world: Callable[[str], Surface],  # noqa: F811
    chantier: Chantier,
) -> None:
    surface = table_world("backlog")
    git_dir = _no_writer(surface)
    server = {
        "pid": os.getpid(),
        "started": clock.now(),
        "host": "127.0.0.1",
        "port": 1,
        "version": "0.0.1",
    }
    assert __version__ != "0.0.1"
    state.modify(git_dir, lambda data: data.__setitem__(state.SERVER, server))
    code, _, err = chantier("file", "An idea")
    assert code == EXIT_PRECONDITION
    assert f"chantier board 0.0.1 (PID {os.getpid()}) serves this surface with no writer" in err
    assert "ask the user to stop it" in err


def test_in_project_mode_a_write_never_asks_for_a_writer(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(repo)
    assert chantier("init")[0] == 0
    code, out, err = chantier("file", "An idea")
    assert code == 0, (out, err)
    assert REFUSED not in err

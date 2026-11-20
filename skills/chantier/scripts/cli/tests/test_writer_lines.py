"""The `writer:` lines (spec CR-404 C.10) from a prepared entry, and the board's start of the
writer (C.2): no seat needed, external mode only, `writer not started` when the lock is held."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from conftest import Surface

from chantier.board import command
from chantier.board.projects import Projects
from chantier.core import clock
from chantier.core.repo import Repo
from chantier.hub import state
from chantier.hub.lock import WriterLock
from chantier.writer import lines
from chantier.writer.record import read

AT = "2026-11-20T10:30:00Z"
HHMM = clock.local_hhmm(AT)
NOT_RUNNING = "writer: not running: writes to the surface are refused; for the Chief of Staff: "
START = "start the surface server ($CHANTIER board --seat <session id>)"


def entry(kind: str, **more: Any) -> dict[str, Any]:
    return {"state": kind, "ahead": 2, "pending": 3, "reason": "", "text": "", **more}


@pytest.mark.parametrize(
    ("record", "expected"),
    [
        (entry("synced", last_push={"at": AT}), f"writer: synced, pushed {HHMM}"),
        (entry("synced"), "writer: synced, never pushed"),
        (
            entry("pending", pending_since=AT),
            f"writer: pending, 3 paths changed since {HHMM}, 2 commits to push",
        ),
        (entry("syncing"), "writer: syncing"),
        (
            entry("offline", since=AT),
            f"writer: offline since {HHMM}, 2 commits not pushed: retries every 30 s",
        ),
        (
            entry("conflict", conflict={"files": ["a", "b", "c", "d", "e"]}),
            "writer: conflict with the remote on a, b, c and 2 more: for the Chief of Staff: "
            "integrate by rebase in the surface's checkout, resolve each file to your best guess "
            "or ask the user; the writer pushes once integrated",
        ),
        (
            entry("blocked", reason="staged", text="x.md"),
            "writer: blocked (staged): x.md; for the Chief of Staff: ",
        ),
        ({"state": "off"}, NOT_RUNNING + START),
    ],
    ids=["synced", "never-pushed", "pending", "syncing", "offline", "conflict", "blocked", "off"],
)
def test_the_writer_line_of_each_state(record: dict[str, Any], expected: str) -> None:
    line = lines.state_line(record)
    assert line.startswith(expected) and "\n" not in line


def test_the_not_pushed_note_is_for_the_states_that_hold_a_commit_back() -> None:
    assert lines.note(entry("pending")) == "writer: pending: not pushed yet (2 commits)"
    blocked = lines.note(entry("blocked", reason="staged"))
    assert blocked == "writer: blocked: not pushed yet (staged)"
    assert lines.note(entry("synced")) is None and lines.note({"state": "off"}) is None


def test_an_older_board_with_no_writer_is_named_in_the_off_line(
    surface: Surface,
) -> None:
    git_dir = surface.root / ".git"
    state.modify(git_dir, lambda data: data.pop(state.WRITER, None))
    server = {
        "pid": os.getpid(),
        "started": clock.now(),
        "host": "127.0.0.1",
        "port": 1,
        "version": "0.0.1",
    }
    state.modify(git_dir, lambda data: data.__setitem__(state.SERVER, server))
    line = lines.state_line(read(git_dir), lines.older_board(git_dir))
    assert line.startswith(
        f"writer: not running: chantier board 0.0.1 (PID {os.getpid()}) serves this surface "
        "with no writer; writes to the surface are refused; for the Chief of Staff: ask the user "
        "to stop it ("
    )
    assert line.endswith(f"), then {START}")


def test_the_board_starts_the_writer_with_no_seat_and_says_so(
    surface: Surface, capsys: pytest.CaptureFixture[str]
) -> None:
    git_dir = surface.root / ".git"
    state.modify(git_dir, lambda data: data.pop(state.WRITER, None))
    home = Repo.find(project="demo", readonly=True)
    assert not (surface.project / "changes" / "seat.json").exists()
    thread = command._start_writer(Projects(home, home.surface, []))
    assert thread is not None
    try:
        assert capsys.readouterr().out.strip() == "writer: syncing"
        assert read(git_dir)["state"] == "syncing"
        # a second board of this machine: the lock is held, the board serves, the reason is said
        assert command._start_writer(Projects(home, home.surface, [])) is None
        out = capsys.readouterr().out
        assert out.startswith("board: writer not started: another process on this machine")
        assert "writer.lock" in out
    finally:
        thread.stop()
    assert read(git_dir)["state"] == "off"
    assert WriterLock(git_dir).acquire()


def test_an_in_project_board_has_no_writer(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(repo)
    home = Repo.find(readonly=True)
    assert command._start_writer(Projects(home, home.surface, [])) is None
    assert read(home.git_dir)["state"] == "off"


def test_a_writer_thread_that_dies_leaves_a_stopped_entry_that_says_why(
    surface: Surface, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    git_dir = surface.root / ".git"
    state.modify(git_dir, lambda data: data.pop(state.WRITER, None))
    home = Repo.find(project="demo", readonly=True)
    thread = command._start_writer(Projects(home, home.surface, []))
    assert thread is not None
    thread._done.set()  # the started thread ends; this test drives the loop by hand
    thread._thread.join(5)
    capsys.readouterr()
    thread._done.clear()

    def boom(*_: Any) -> None:
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(thread.loop, "poll", boom)
    monkeypatch.setattr(thread.loop, "note_error", boom)
    thread._run()  # poll and its error note both raise: the outer handler ends the writer
    found = read(git_dir)
    assert (found["state"], found["text"]) == ("stopped", "disk on fire")
    assert lines.state_line(found).startswith("writer: stopped: disk on fire; writes")
    assert "stopped: disk on fire" in lines.refusal("take", git_dir)
    assert lines.refused(git_dir) and lines.note(found) is None
    assert WriterLock(git_dir).acquire()  # the lock is let go, not held by a dead writer
    thread.stop()
    assert read(git_dir)["state"] == "off"  # the server's end removes the entry

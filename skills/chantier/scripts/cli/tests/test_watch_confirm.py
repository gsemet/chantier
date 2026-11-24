"""The watcher confirms that the server which answers its link is the one `server.json` records
(the one that holds the forge hub), links again after a restart from its cursor, and ends with a
line that names both PIDs when it cannot; `status` says when the hub sees no subscriber. `FakeBoard`
stands for the server."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_watch_board import BOARD, ME, seat
from watch_fakes import PID, FakeBoard, entry, served

from chantier import __version__
from chantier.board import running
from chantier.board.projects import project_name
from chantier.core import clock
from chantier.core.repo import Repo
from chantier.hub import autostart, journal, lock, state
from chantier.hub.lines import unsubscribed, watch_lines
from chantier.hub.watch import END, RETRY_S, SILENT_S, Watch
from chantier.hub.watch_lines import STRAY

STRAY_PID = PID + 1000
GONE = 99_999_999  # no process has this PID


def test_a_link_answered_by_another_process_is_no_link_and_the_watcher_ends_naming_both(
    repo: Path,
) -> None:
    found = Repo.find()
    board = FakeBoard(found, entry())
    board.answers = STRAY_PID
    w = Watch(found, 0, __version__, board=board)
    w.start()
    journal.append(found, [BOARD], "board")
    assert w.poll(0.0) is None and w.feed is None and w.stray == STRAY_PID
    assert w.events == [] and w.cursor == 0  # nothing the stray gave is taken
    assert w.poll(RETRY_S) is None and len(board.feeds) > 1  # linked to it again, still no link
    assert w.poll(SILENT_S - 1) is None
    assert w.poll(SILENT_S) == END and w.code(END) == 1
    assert w.end is not None
    stop = running.stop_command(STRAY_PID)
    text = {**w._where(), "stray": STRAY_PID, "pid": PID, "stop": stop}
    assert w.end.line == STRAY.format(**text)
    assert f"PID {STRAY_PID}" in w.end.line and f"PID {PID}" in w.end.line
    w.close()


@pytest.mark.parametrize("restart", ["new-pid", "same-pid"])
def test_a_restarted_server_gets_the_watchers_link_again_from_its_cursor(
    repo: Path, restart: str
) -> None:
    found = Repo.find()
    board = served(found)
    w = Watch(found, 0, __version__, board=board)
    w.start()
    journal.append(found, [BOARD], "board")
    assert w.poll(0.0) is None and w.cursor == 1
    if restart == "new-pid":
        board.running = entry(pid=PID + 1)  # a new process, as `serve --restart` records it
    journal.append(found, [BOARD | {"text": "y"}], "board")
    assert w.poll(RETRY_S) is None
    assert [after for after, _ in board.feeds] == ([0, 2] if restart == "new-pid" else [0])
    assert w.poll(RETRY_S * 2) is None and w.stray is None
    assert [e["seq"] for e in w.events] == [1, 2]  # no line told twice, none lost
    w.close()


@pytest.mark.parametrize("ours", [True, False])
def test_the_start_line_says_started_only_for_the_board_this_watcher_spawned(
    repo: Path, monkeypatch: pytest.MonkeyPatch, ours: bool
) -> None:
    monkeypatch.setattr(autostart, "session_key", lambda: ME)
    seat(repo, ME)
    found = Repo.find()

    def starts(board: FakeBoard) -> None:  # another start won the surface when not ours
        board.running = entry() if ours else entry(pid=GONE)

    w = Watch(found, 0, __version__, board=FakeBoard(found, starts=starts))
    assert ("started the board" in w.start()[0]) is ours
    w.close()


def _server(pid: int) -> dict[str, Any]:
    return {
        "pid": pid,
        "host": "127.0.0.1",
        "port": 1,
        "version": __version__,
        "served": "x",
        "started": clock.now(),
    }


@pytest.mark.parametrize(
    ("hub", "server", "said"),
    [
        (None, None, "no forge hub runs"),
        ({"idle": True}, None, "sees no subscriber"),
        ({}, os.getpid() + 1, "the recorded server is PID"),
        ({}, None, None),
    ],
    ids=["no-hub", "idle-hub", "other-server", "observed"],
)
def test_status_says_when_a_watcher_runs_and_the_hub_sees_no_subscriber(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    hub: dict[str, Any] | None,
    server: int | None,
    said: str | None,
) -> None:
    monkeypatch.setattr(autostart, "session_key", lambda: ME)
    monkeypatch.setattr("chantier.procs.alive_since", lambda *_a, **_k: True)
    found = Repo.find()
    if hub is not None:
        state.write_hub(found.git_dir, {**state.hub_record(__version__), **hub})
    if server is not None:
        state.modify(found.git_dir, lambda d: d.__setitem__(state.SERVER, _server(server)))
    held = lock.WatcherLock(found.git_dir, project_name(found), ME)
    assert held.acquire()
    d: Any = SimpleNamespace(status="running", foreman_transcript=None, steering="direct")
    try:
        out = watch_lines(found, d)
    finally:
        held.release()
    (mine,) = [x for x in out if x.startswith("watch: this session's watcher runs")]
    assert "pull path:" in mine
    if said is None:
        assert unsubscribed(found) is None and "not subscribed" not in mine
    else:
        assert "not subscribed to the forge hub" in mine and said in mine

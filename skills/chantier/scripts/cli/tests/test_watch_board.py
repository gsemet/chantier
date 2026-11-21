"""The watcher as a client of the surface server: the seat rule with and without a running board,
the detached start and the board that does not come up, the board's lines it passes on, the link
lost and opened again from its cursor, the refusals, and the idle end. `FakeBoard` stands for the
server, so no test starts a process, reaches a socket or sleeps."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from watch_fakes import PID, FakeBoard, JournalFeed, entry, served, serving

from chantier import __version__
from chantier.board import running
from chantier.board.command import BEYOND, CHECKS, NO_NETWORK, WATCHES
from chantier.clients.tui.link import KEY, PROTOCOL_KIND, Linked, Refusal, Refused
from chantier.core.errors import ChantierError
from chantier.core.repo import Repo
from chantier.core.seat import read_seat
from chantier.hub import autostart, feed, journal
from chantier.hub import times as hub_times
from chantier.hub.watch import END, IDLE, RETRY_S, SILENT_S, START_S, Watch, run
from chantier.hub.watch_lines import (
    BAD_KEY,
    IDLE_END,
    NO_KEY,
    NO_SEAT,
    NO_TRANSCRIPT,
    NOT_SERVED,
    NOT_STARTED,
    REFUSED,
    SEAT_LINE,
    UNREADABLE_SEAT,
)
from chantier.plugin_files import cli_command

ME, OTHER, SESSION = "abc-1", "xyz-2", "s-seat"
BOARD = {"type": "board@1", "action": "move", "items": ["x"], "text": "x", "wakes": True}


def seat(repo: Path, transcript: str | None) -> None:
    folder = repo / ".agents" / "changes"
    folder.mkdir(parents=True, exist_ok=True)
    data = {"session": SESSION, "transcript": transcript}
    (folder / "seat.json").write_text(json.dumps(data), encoding="utf-8")


def texts(found: Repo, cursor: int = 0) -> dict[str, str]:
    return {
        "project": found.root.name,
        "cli": cli_command(found),
        "watch": autostart.watch_command(found, cursor),
    }


def where(found: Repo) -> dict[str, str]:
    return {**texts(found), "where": "127.0.0.1:1", "stop": running.stop_command(PID)}


# (the watcher's key, the seat's transcript or "no seat", whether a board runs, the end's line
# and code, or None when it links)
MATRIX: list[Any] = [
    (ME, ME, True, None),
    (ME, OTHER, True, None),
    (ME, "no seat", True, None),
    ("none", ME, True, None),
    ("none", ME, False, (NO_KEY, 1)),
    (ME, "no seat", False, (NO_SEAT, 1)),
    (ME, None, False, (NO_TRANSCRIPT, 1)),
    (ME, "", False, (NO_TRANSCRIPT, 1)),
    (ME, OTHER, False, (SEAT_LINE, 0)),
    (ME, "unreadable", False, (UNREADABLE_SEAT, 1)),
    (ME, ME, False, None),
]


@pytest.mark.parametrize("case", MATRIX)
def test_the_seat_rule_with_and_without_a_running_board(
    repo: Path, monkeypatch: pytest.MonkeyPatch, case: tuple[Any, ...]
) -> None:
    key, transcript, runs, ends = case
    monkeypatch.setattr(autostart, "session_key", lambda: key)
    if transcript == "unreadable":
        seat(repo, None)
        (repo / ".agents" / "changes" / "seat.json").write_text("{not json", encoding="utf-8")
    elif transcript != "no seat":
        seat(repo, transcript)
    found = Repo.find()
    board = served(found) if runs else FakeBoard(found, starts=serving)
    w = Watch(found, 0, __version__, board=board)
    if ends is not None:
        error = ""
        if transcript == "unreadable":
            with pytest.raises(ChantierError) as raised:
                read_seat(found)
            error = str(raised.value)
        assert run(w) == ([ends[0].format(**texts(found), error=error)], ends[1])
        assert board.spawned == [] and board.feeds == []
        return
    start = w.start()
    w.close()
    mine = key == ME and transcript == ME
    assert board.registered == ([(found.root.name, SESSION)] if runs and mine else [])
    assert [after for after, _ in board.feeds] == [0]
    line = f"watch: {found.root.name} from cursor 0 for project"
    line += f", session:{key}" if key != "none" else ""
    if not runs:
        assert board.spawned == [[*feed.board_argv(found, SESSION)]]
        assert board.spawned[0][-4:] == ["board", "--seat", SESSION, "--stop-idle"]
        line += f"; started the board (PID {PID})"  # the entry's PID, the board's own
    assert start == [line, WATCHES]


def test_the_start_is_detached_on_each_system(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    got: list[dict[str, Any]] = []
    monkeypatch.setattr(subprocess, "Popen", lambda argv, **kw: got.append(kw))
    feed.spawn(["board"], tmp_path)
    (kw,) = got
    devnull = subprocess.DEVNULL
    assert (kw["stdin"], kw["stdout"], kw["stderr"], kw["close_fds"]) == (devnull,) * 3 + (True,)
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        assert kw["creationflags"] == flags and not flags & subprocess.DETACHED_PROCESS
        assert "start_new_session" not in kw
    else:
        assert kw["start_new_session"] is True and "creationflags" not in kw


def _never(board: FakeBoard) -> None:
    """A start that records no server."""


def _mute(board: FakeBoard) -> None:
    board.running, board.answer = entry(), "none"


def _other_key(board: FakeBoard) -> None:
    board.running, board.answer = entry(), "another-key"


@pytest.mark.parametrize("start", [_never, _mute, _other_key])
def test_a_board_that_does_not_come_up_ends_the_watcher(
    repo: Path, monkeypatch: pytest.MonkeyPatch, start: Any
) -> None:
    monkeypatch.setattr(autostart, "session_key", lambda: ME)
    seat(repo, ME)
    found = Repo.find()
    board = FakeBoard(found, starts=start)
    lines, code = run(Watch(found, 0, __version__, board=board))
    expected = {
        _never: NOT_STARTED.format(cli=cli_command(found), session=SESSION),
        _mute: f"watch: {running.silent_text(entry())}",
        _other_key: BAD_KEY.format(**where(found)),
    }[start]
    assert (lines, code) == ([expected], 1)
    assert board.now >= START_S if start is not _other_key else board.now == 0.0
    assert board.spawned == [feed.board_argv(found, SESSION)] and board.feeds == []


@pytest.mark.parametrize(
    ("host", "yaml", "files", "passed"),
    [
        ("0.0.0.0", "", "notify", [BEYOND.format(host="0.0.0.0"), WATCHES]),
        ("127.0.0.1", "board:\n  host: network\n", "check", [NO_NETWORK, CHECKS]),
        ("127.0.0.1", "", "check", [CHECKS]),
        ("127.0.0.1", "", None, []),
    ],
)
def test_the_boards_lines_follow_the_start_line(
    repo: Path, host: str, yaml: str, files: str | None, passed: list[str]
) -> None:
    if yaml:
        (repo / "chantier.yaml").write_text(yaml, encoding="utf-8")
    found = Repo.find()
    w = Watch(found, 0, __version__, board=FakeBoard(found, entry(host=host, files=files)))
    assert w.start()[1:] == passed
    w.close()


def test_a_lost_link_is_opened_again_from_the_cursor_and_repeats_no_line(repo: Path) -> None:
    found = Repo.find()
    board = served(found)
    w = Watch(found, 0, __version__, board=board)
    w.start()
    journal.append(found, [BOARD], "board")
    assert w.poll(0.0) is None and w.cursor == 1
    first = board.feeds[0][1]
    first.extra = [Linked(None, None, "reset")]
    journal.append(found, [BOARD | {"text": "y"}], "board")
    assert w.poll(1.0) is None and first.closed and w.cursor == 1  # lost: nothing read
    assert w.poll(RETRY_S) is None and len(board.feeds) == 1  # not yet
    assert w.poll(1.0 + RETRY_S) is None
    assert [after for after, _ in board.feeds] == [0, 1]  # opened again after the line it had
    assert [e["seq"] for e in w.events] == [1, 2] and w.cursor == w.events[-1]["seq"]
    w.close()


def _refusal(kind: str) -> Refusal:
    return Refusal("this server speaks protocol 2", kind)


@pytest.mark.parametrize("kind", [KEY, PROTOCOL_KIND, "refused", "silent", "gone"])
def test_a_refusal_a_silent_board_or_a_board_gone_ends_the_watcher(
    repo: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    monkeypatch.setattr(autostart, "session_key", lambda: ME)
    found = Repo.find()
    board = FakeBoard(found, entry(), transport=None if kind == "silent" else "ws")
    w = Watch(found, 0, __version__, board=board)
    w.start()
    sentence = "this server speaks protocol 2"
    lost: JournalFeed = board.feeds[0][1]
    if kind in (KEY, PROTOCOL_KIND):
        lost.extra = [_refusal(kind)]
        line = (BAD_KEY if kind == KEY else REFUSED).format(**where(found), sentence=sentence)
    elif kind == "refused":
        lost.extra = [Refused("events", 404, "no such project")]
        line = NOT_SERVED.format(**where(found), error="404 no such project")
    elif kind == "silent":
        line = f"watch: {running.silent_text(entry())}"
    else:
        board.running = None  # the board stopped, and no seat to start another for
        lost.extra = [Linked(None)]
        line = NO_SEAT.format(**texts(found))
    got = [w.poll(float(t)) for t in (0, RETRY_S, SILENT_S)]
    w.close()
    assert END in got and w.lines(END)[-1] == line
    assert w.code(END) == 1
    assert board.spawned == []


@pytest.mark.parametrize(("times", "end"), [("1:20:100", 100.0), ("1:20", hub_times.IDLE_END_S)])
def test_a_watcher_with_no_event_that_wakes_ends_after_the_idle_end(
    repo: Path, monkeypatch: pytest.MonkeyPatch, times: str, end: float
) -> None:
    monkeypatch.setenv(hub_times.TEST_ENV, times)
    assert hub_times.idle_end_s() == end
    found = Repo.find()
    w = Watch(found, 0, __version__, board=served(found))
    w.start()
    journal.append(found, [BOARD | {"wakes": False}], "board")
    assert w.poll(0.0) is None and w.poll(end - 1) is None
    assert w.poll(end) == IDLE and w.code(IDLE) == 0
    w.close()
    name = f"{found.root.name} (no batch)"
    out = w.lines(IDLE)
    assert out[:-1] == [journal.event_text(BOARD | {"wakes": False})]
    assert out[-1] == IDLE_END.format(name=name, watch=autostart.watch_command(found, 1))

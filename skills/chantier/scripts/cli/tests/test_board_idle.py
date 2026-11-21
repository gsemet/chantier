"""A board with no client: the idle stop of `--stop-idle` (its count, its reset, the writer's last
cycle before the `server` entry goes), the forge read only while a client observes (or always,
with `--forge-always`), `PushLoop.observed`, the two flags refused together, and the start and
"already running" lines. The time is passed in; the one real `_run` waits for a bounded time."""

from __future__ import annotations

import argparse
import socket
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import ANY

import pytest
from conftest import Chantier
from forge_world import CALLS, CYCLE, MAIN, NEW_VERSION, T1, World, merged
from test_board_running import _answer, _prepare_board
from test_file_watch import _ctx

from chantier import __version__
from chantier.board import command, idle
from chantier.board import key as keys
from chantier.board.api import ops, times
from chantier.board.api.push import PushLoop
from chantier.board.context import Context
from chantier.board.idle import IdleStop
from chantier.board.projects import Projects, open_projects
from chantier.board.seats import Seats
from chantier.board.watch_files import CHECK, NOTIFY
from chantier.core.errors import EXIT_USAGE
from chantier.hub import state
from chantier.hub.loop import HubLoop

WAIT_S = 10.0
THERE = ("127.0.0.1", 40123)
MINUTE = 60.0


def test_the_idle_stop_counts_from_the_last_observed_moment(
    capsys: pytest.CaptureFixture[str],
) -> None:
    seen, stopped = [False], list[int]()
    stop = IdleStop(lambda: seen[0], lambda: stopped.append(1), 0.0)
    assert times.IDLE_STOP_S == 30 * MINUTE
    assert stop.poll(times.IDLE_STOP_S - 1) is False and stopped == []
    seen[0] = True
    assert stop.poll(times.IDLE_STOP_S - 1) is False  # one observed moment: the count restarts
    seen[0] = False
    assert stop.poll(2 * times.IDLE_STOP_S - 2) is False and stopped == []
    assert stop.poll(2 * times.IDLE_STOP_S - 1) is True and stopped == [1]
    assert stop.poll(10 * times.IDLE_STOP_S) is True and stopped == [1]
    assert capsys.readouterr().out == f"{idle.STOPPED}\n"


class _Server:
    """`make_server`'s stand-in: serves until `should_exit`, within `wait` seconds."""

    def __init__(self, order: list[str], wait: float = WAIT_S) -> None:
        self.should_exit, self.order, self.wait = False, order, wait

    def run(self, sockets: list[socket.socket]) -> None:
        end, tick = time.monotonic() + self.wait, threading.Event()
        while not self.should_exit and time.monotonic() < end:
            tick.wait(0.02)
        self.order.append("stopped" if self.should_exit else "timed out")


class _Stub:
    def __init__(self, order: list[str], name: str) -> None:
        self.order, self.name = order, name

    def stop(self) -> None:
        self.order.append(self.name)


@pytest.mark.parametrize(
    ("stop_idle", "seated", "first"),
    [(True, False, "stopped"), (True, True, "stopped"), (False, False, "timed out")],
    ids=["idle-stop", "seats-do-not-observe", "no-flag-no-stop"],
)
@pytest.mark.usefixtures("repo")
def test_an_idle_board_stops_and_its_writer_runs_before_its_entry_goes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stop_idle: bool,
    seated: bool,
    first: str,
) -> None:
    """With `--stop-idle`, a board with no client stops, a registered seat being no observer;
    without it, a board idle five times the delay still serves until stopped by other means."""
    monkeypatch.setenv(times.TEST_ENV, "2:30:1:1:5:0.2")  # the idle stop after 0.2 s
    order: list[str] = []
    monkeypatch.setattr(command, "make_server", lambda _ctx: _Server(order, 1.0))
    monkeypatch.setattr(command, "_start_writer", lambda _p: _Stub(order, "writer"))
    real = state.remove_entry

    def remove(git_dir: Path, kind: str, pid: int) -> None:
        if kind == state.SERVER:
            order.append("entry")
        real(git_dir, kind, pid)

    monkeypatch.setattr(state, "remove_entry", remove)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    base = _ctx()
    if seated:
        assert base.seats.add(base.projects.home_id, "session-1") and base.seats.count() == 1
    ctx = command._context(base.projects, base.seats, sock, None)
    files: Any = _Stub(order, "files")
    command._run(ctx, sock, files, argparse.Namespace(stop_idle=stop_idle, forge_always=False))
    assert order == [first, "writer", "files", "entry"]
    assert (idle.STOPPED in capsys.readouterr().out) is stop_idle


@pytest.fixture
def hub_loop(world: World, monkeypatch: pytest.MonkeyPatch) -> HubLoop:
    monkeypatch.setattr("chantier.hub.loop.hub_times.poll_s", lambda: 0.01)
    world.hub.close()
    world.forge = {10: merged(MAIN, T1)}
    return HubLoop(world.repo("alpha"), NEW_VERSION)


def test_the_hub_reads_the_forge_only_while_a_client_observes(
    world: World, hub_loop: HubLoop
) -> None:
    git = world.repo("alpha").git_dir
    for at in range(0, int(MINUTE) + 1, 5):
        hub_loop.poll(float(at), lambda: False)
    held = state.live_entry(git, state.HUB)
    assert world.calls == [] and held is not None and held["idle"] is True
    hub_loop.poll(MINUTE + 1, lambda: True)  # the first observer: a cycle at once
    assert len(world.calls) == CALLS and "idle" not in (state.live_entry(git, state.HUB) or {})
    hub_loop.poll(MINUTE + 2, lambda: True)
    assert len(world.calls) == CALLS
    hub_loop.poll(MINUTE + 1 + CYCLE, lambda: True)
    assert len(world.calls) == 2 * CALLS
    hub_loop.stop()


def test_with_the_forge_always_the_hub_reads_with_no_client(
    world: World, hub_loop: HubLoop
) -> None:
    git = world.repo("alpha").git_dir
    always = command._observer(argparse.Namespace(forge_always=True), PushLoop(_ctx_of(world)))
    for at in range(0, int(MINUTE) + 1, 5):
        hub_loop.poll(float(at), always)
        assert "idle" not in (state.live_entry(git, state.HUB) or {})
    assert len(world.calls) == CALLS * (1 + int(MINUTE // CYCLE))
    hub_loop.stop()


def _ctx_of(world: World) -> Context:
    found = world.repo("alpha")
    projects = Projects(found, found.surface, [])
    return Context(
        projects, keys.KeyFile(keys.key_path(found)), Seats(projects), "t", lambda: None, None
    )


def test_a_client_observes_with_a_socket_sub_or_a_recent_long_poll(repo: Path) -> None:
    loop = PushLoop(_ctx())
    assert loop.observed() is False
    sub = loop.subscribe("board", {}, lambda _e: None)
    assert not isinstance(sub, ops.Result) and loop.observed() is True
    loop.unsubscribe(sub)
    assert loop.observed() is False
    assert loop.hold([], 0.0) == []
    now = time.monotonic()
    assert loop.observed(now) is True
    assert loop.observed(now + 2 * times.hold_s() + 1) is False


@pytest.mark.parametrize(
    ("forge", "told"), [(None, True), ("always", False)], ids=["watcher-board", "forge-board"]
)
def test_a_second_board_with_the_forge_always_registers_its_seat_and_says_the_forge_rule(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    forge: str | None,
    told: bool,
) -> None:
    """`board --seat <id> --forge-always` on a running board started without the flag (by a
    watcher): its seat registered, and the `FORGE_WHEN_OBSERVED` line; none on a board that
    reads the forge always."""
    served = open_projects().served.as_posix()
    rec: dict[str, Any] = {
        "pid": 4242,
        "host": "127.0.0.1",
        "port": THERE[1],
        "version": __version__,
        "served": served,
        "started": "2026-01-01T00:00:00Z",
        "files": NOTIFY,
        **({"forge": forge} if forge else {}),
    }
    _prepare_board(repo, chantier, monkeypatch, (True, rec, _answer(served, __version__)))
    seats: list[tuple[Any, ...]] = []

    def register(*a: Any) -> bool:
        seats.append(a)
        return True

    monkeypatch.setattr(command, "register_seat", register)
    code, out, err = chantier("board", "--seat", "s-1", "--forge-always")
    assert code == 0, err
    assert seats == [("127.0.0.1", THERE[1], ANY, open_projects().home_id, "s-1")]
    assert (command.FORGE_WHEN_OBSERVED in out) is told and command.WATCHES in out


def test_the_two_flags_together_are_a_usage_error(repo: Path, chantier: Chantier) -> None:
    code, _, err = chantier("board", "--stop-idle", "--forge-always")
    assert code == EXIT_USAGE and command.BOTH_FLAGS in "".join(err)


@pytest.mark.parametrize(("mode", "line"), [(NOTIFY, command.WATCHES), (CHECK, command.CHECKS)])
def test_the_start_line_says_the_file_watch(
    capsys: pytest.CaptureFixture[str], mode: str, line: str
) -> None:
    command._announce(*THERE, "k", "/served", [command.files_line(mode) or ""])
    assert capsys.readouterr().out.splitlines()[-1] == line


@pytest.mark.parametrize(
    ("entry", "always", "tail"),
    [
        ({}, False, []),
        ({"files": NOTIFY, "stop_idle": 1800}, False, [command.WATCHES, command.STOPS_IDLE]),
        (
            {"files": CHECK, "stop_idle": 1800},
            True,
            [command.CHECKS, command.FORGE_WHEN_OBSERVED, command.STOPS_IDLE],
        ),
        ({"files": NOTIFY, "forge": "always"}, True, [command.WATCHES]),
    ],
    ids=["old-entry", "watcher-board", "forge-always-on-watcher-board", "forge-always-board"],
)
def test_the_already_running_lines_say_the_watch_the_forge_and_the_idle_stop_last(
    entry: dict[str, Any], always: bool, tail: list[str]
) -> None:
    got = command._running_lines(THERE, "k", False, entry, always)
    assert got[0].startswith("board already running at ") and got[1:] == tail

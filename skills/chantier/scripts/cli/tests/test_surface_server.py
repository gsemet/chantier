"""The surface server: the hub election between it and the watchers, the `hub` entry it keeps, the
hub loop of `chantier board` and the writers of `server.json`. No test reaches a forge and none
sleeps: the loop is driven with an injected monotonic time."""

from __future__ import annotations

import os
import threading
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import DEAD, name_server
from forge_world import BOARD_LINE, CALLS, CYCLE, MAIN, NEW_VERSION, T1, World, merged, shape

from chantier import procs
from chantier.core.repo import Repo
from chantier.hub import journal, lock, state
from chantier.hub.cycle import Hub
from chantier.hub.loop import HubLoop, HubThread
from chantier.hub.watch import Watch


@pytest.fixture
def dead_is_dead(monkeypatch: pytest.MonkeyPatch) -> None:
    real = procs.alive_since
    monkeypatch.setattr(
        procs, "alive_since", lambda pid, *a, **k: pid != DEAD and real(pid, *a, **k)
    )


@pytest.mark.parametrize("server", [False, True], ids=["no-server", "live-server"])
def test_one_watcher_holds_the_hub_lock_and_the_next_takes_it(
    repo: Path, dead_is_dead: None, server: bool
) -> None:
    found = Repo.find()
    git = found.git_dir
    if server:
        name_server(git)
    first, second = lock.HubLock(git), lock.HubLock(git)
    assert (first.acquire(), second.acquire()) == (True, False)
    hub = Hub(found, NEW_VERSION)
    held = state.live_entry(git, state.HUB)
    assert held is not None
    assert (held["pid"], held["version"]) == (os.getpid(), NEW_VERSION)
    hub.close()
    first.release()
    assert state.live_entry(git, state.HUB) is None
    assert not (git / "chantier" / "hub.json").exists()
    assert second.acquire() is True
    second.release()
    # the election: with no server the first watcher is the hub; with a live one, none elects
    w = Watch(found, 0, NEW_VERSION)
    w.poll(0.0)
    assert (w.hub is not None) is (not server)
    if server:
        assert not w.lock.held and state.live_entry(git, state.HUB) is None
        name_server(git, DEAD)  # the server was killed: its entry names a dead process
        w.poll(1.0)
        assert w.hub is not None and state.live_entry(git, state.HUB) is not None
    # a server appears: the hub watcher ends its cycle, removes its entry and lets the lock go
    name_server(git)
    w.poll(2.0)
    assert w.hub is None and state.live_entry(git, state.HUB) is None
    probe = lock.HubLock(git)
    assert probe.acquire()
    probe.release()
    name_server(git, DEAD)  # and once none is live, the next poll takes the lock again
    w.poll(3.0)
    assert w.hub is not None
    w.close()


def test_a_hub_entry_that_cannot_be_written_is_written_at_the_next_cycle(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    git_dir = world.repo("alpha").git_dir
    real = state.write_hub

    def refused(*_a: object, **_k: object) -> None:
        raise state.StateError("server.json: refused")

    world.forge = {10: merged(MAIN, T1)}
    monkeypatch.setattr(state, "write_hub", refused)
    world.hub.cycle(0.0)  # the lock is kept, the cycle's events are in the journal anyway
    assert shape(world.journal("alpha")) == [(1, "hub", "merged@1", "CR-1", None)]
    mine = state.live_entry(git_dir, state.HUB)
    assert mine is not None and "alpha" not in mine["projects"]
    monkeypatch.setattr(state, "write_hub", real)
    world.hub.cycle(CYCLE)
    mine = state.live_entry(git_dir, state.HUB)
    assert mine is not None and mine["projects"]["alpha"]["read_at"]
    assert len(world.journal("alpha")) == 1


def _put(name: str, n: int, data: dict[str, Any]) -> None:
    data[name] = {"n": n}


def test_two_writers_of_server_json_lose_neither_entry(repo: Path) -> None:
    git = Repo.find().git_dir
    errors: list[BaseException] = []

    def keep(name: str) -> None:
        try:
            for n in range(10):
                state.modify(git, partial(_put, name, n))
        except BaseException as e:
            errors.append(e)

    threads = [threading.Thread(target=keep, args=(x,)) for x in (state.SERVER, state.HUB)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert state.read(git) == {state.SERVER: {"n": 9}, state.HUB: {"n": 9}}


class Dies:
    def poll(self, _now: float) -> None:
        raise RuntimeError("boom")

    def note_error(self, _e: Exception) -> None:
        raise RuntimeError("boom")


class BadCycle:
    """A cycle that raises once (a refused line): noted, the loop goes on."""

    def __init__(self) -> None:
        self.noted: list[Exception] = []
        self.polls = 0

    def poll(self, _now: float) -> None:
        self.polls += 1
        if self.polls == 1:
            raise ValueError("bad line")

    def note_error(self, e: Exception) -> None:
        self.noted.append(e)


def test_the_servers_hub_loop_elects_cycles_when_due_and_lets_go(
    world: World, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("chantier.hub.loop.hub_times.poll_s", lambda: 0.01)
    world.hub.close()
    alpha = world.repo("alpha")
    git = alpha.git_dir
    world.forge = {10: merged(MAIN, T1)}
    loop = HubLoop(alpha, NEW_VERSION)
    watcher = lock.HubLock(git)
    assert watcher.acquire()  # a watcher is the hub: the server serves and waits
    loop.poll(0.0)
    assert loop.hub is None and not world.calls
    watcher.release()  # it yielded: within one poll the server is the hub
    loop.poll(1.0)
    assert loop.hub is not None and len(world.calls) == CALLS
    held = state.live_entry(git, state.HUB)
    assert held is not None and held["pid"] == os.getpid()
    journal.append(alpha, [BOARD_LINE], "board")
    loop.poll(2.0)  # not due
    assert len(world.calls) == CALLS
    loop.poll(1.0 + CYCLE)  # due: the merge is not written twice
    assert len(world.calls) == 2 * CALLS
    kinds = [(e["source"], e["type"]) for e in world.journal("alpha")]
    assert kinds == [("hub", "merged@1"), ("board", "board@1")]
    loop.stop()
    assert state.live_entry(git, state.HUB) is None
    again = lock.HubLock(git)
    assert again.acquire()
    again.release()
    # a bad cycle is noted and the thread goes on to the next one
    bad = BadCycle()
    thread = HubThread(bad, lambda: None)
    runner = threading.Thread(target=thread._run)
    runner.start()
    for _ in range(200):
        if bad.polls > 1:
            break
        threading.Event().wait(0.05)
    thread._done.set()
    runner.join(5)
    assert bad.polls > 1 and [str(e) for e in bad.noted] == ["bad line"]
    # a loop that cannot even note its error ends the server, with a line
    ended: list[int] = []
    HubThread(Dies(), lambda: ended.append(1))._run()
    assert ended == [1] and "the forge hub stopped: boom" in capsys.readouterr().err

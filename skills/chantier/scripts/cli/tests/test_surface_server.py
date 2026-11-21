"""The surface server, the only forge hub: the `hub` entry it keeps, the hub loop of
`chantier board` and the writers of `server.json`. No test reaches a forge and none
sleeps: the loop is driven with an injected monotonic time."""

from __future__ import annotations

import os
import threading
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from forge_world import BOARD_LINE, CALLS, CYCLE, MAIN, NEW_VERSION, T1, World, merged, shape

from chantier.core.repo import Repo
from chantier.hub import journal, lock, state
from chantier.hub.loop import HubLoop, HubThread


def seen() -> bool:  # a client observes the server
    return True


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
    def poll(self, _now: float, _observed: object) -> None:
        raise RuntimeError("boom")

    def note_error(self, _e: Exception) -> None:
        raise RuntimeError("boom")


class BadCycle:
    """A cycle that raises once (a refused line): noted, the loop goes on."""

    def __init__(self) -> None:
        self.noted: list[Exception] = []
        self.polls = 0

    def poll(self, _now: float, _observed: object) -> None:
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
    other = lock.HubLock(git)
    assert other.acquire()  # another server holds the lock: this one serves and waits
    loop.poll(0.0, seen)
    assert loop.hub is None and not world.calls
    other.release()  # it stopped: within one poll this server is the hub
    loop.poll(1.0, seen)
    assert loop.hub is not None and len(world.calls) == CALLS
    held = state.live_entry(git, state.HUB)
    assert held is not None and held["pid"] == os.getpid()
    journal.append(alpha, [BOARD_LINE], "board")
    loop.poll(2.0, seen)  # not due
    assert len(world.calls) == CALLS
    loop.poll(1.0 + CYCLE, seen)  # due: the merge is not written twice
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
    thread = HubThread(bad, lambda: None, seen)
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
    HubThread(Dies(), lambda: ended.append(1), seen)._run()
    assert ended == [1] and "the forge hub stopped: boom" in capsys.readouterr().err

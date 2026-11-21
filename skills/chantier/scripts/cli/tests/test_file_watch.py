"""The surface server's watch of the planning files: a project settles once quiet for `QUIET_S` (or
`MOST_S` into a stream that never pauses), one walk each; a lock or an uncounted file settles
nothing; the push loop's passes walk nothing; the real notification backend sees a write; with
no backend, or once it dies, the checks every `CHECK_S` see it. The settle rule is driven with a
clock, no sleep; the two real-thread tests wait for a bounded time."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from chantier.board import command, context, fingerprint
from chantier.board import key as keys
from chantier.board.api import ops, times
from chantier.board.api.push import PushLoop
from chantier.board.context import Context
from chantier.board.projects import Projects
from chantier.board.seats import Seats
from chantier.board.watch_files import (
    CHECK,
    MOST_S,
    NOTIFY,
    QUIET_S,
    STOPPED,
    FileWatchThread,
    Settler,
)
from chantier.core.repo import Repo

WAIT_S = 10.0  # the real threads' bound
PASSES = 10
STEP_S = 0.5


def _ctx() -> Context:
    found = Repo.find(readonly=True)
    found.changes.mkdir(parents=True, exist_ok=True)  # a board serves an existing folder
    projects = Projects(found, None, [])
    return Context(
        projects, keys.KeyFile(keys.key_path(found)), Seats(projects), "t", lambda: None, None
    )


def _walks(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Each walk of a project's files, counted."""
    walks: list[Path] = []
    real = fingerprint.fingerprint  # what `Context.settle` calls

    def counted(store: Any, root: Path) -> str:
        walks.append(root)
        return real(store, root)

    monkeypatch.setattr(context, "fingerprint", counted)
    return walks


def _idea(ctx: Context, name: str = "idea") -> Path:
    folder = ctx.projects.home.changes / "1-inbox" / name / "intake"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "request.md"
    path.write_text(f"{name}\n", encoding="utf-8")
    return path


def _until(done: Callable[[], bool]) -> bool:
    """`done` within `WAIT_S`, looked at every 50 ms."""
    end, tick = time.monotonic() + WAIT_S, threading.Event()
    while not done():
        if time.monotonic() > end:
            return False
        tick.wait(0.05)
    return True


def test_the_shipped_settle_times() -> None:
    assert (QUIET_S, MOST_S, times.CHECK_S) == (1.0, 5.0, 5.0)


@pytest.mark.parametrize(
    ("changes", "early", "settles"),
    [
        ((0.0, 0.4, 0.8), 1.7, 1.8),  # quiet for 1 s after the last change
        (tuple(STEP_S * i for i in range(10)), 4.9, 5.0),  # every 0.5 s: 5 s at the most
    ],
    ids=["quiet", "stream"],
)
def test_a_project_settles_once_quiet_or_at_the_latest_with_one_walk(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    changes: tuple[float, ...],
    early: float,
    settles: float,
) -> None:
    ctx = _ctx()
    walks = _walks(monkeypatch)
    watch = FileWatchThread(ctx)
    path = _idea(ctx)
    for at in changes:
        watch.feed([str(path)], at)
        assert watch.tick(at) == []
    assert watch.tick(early) == [] and walks == []
    assert watch.tick(settles) == [ctx.projects.home_id] and len(walks) == 1
    assert watch.tick(settles + 10) == [] and len(walks) == 1


def test_two_projects_settle_once_each_and_a_lock_or_an_uncounted_file_settles_nothing(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settler = Settler()
    settler.change("a", 0.0)
    settler.change("b", 0.5)
    settler.change("a", 0.6)
    assert settler.due(1.5) == ["b"] and settler.due(1.6) == ["a"] and settler.due(9) == []
    ctx = _ctx()
    walks = _walks(monkeypatch)
    watch = FileWatchThread(ctx)
    root = ctx.projects.home.changes
    batch = root / "4-batch"
    watch.feed([str(batch / ".lock"), str(batch / ".long-gate.x"), str(root / "notes.txt")], 0.0)
    assert watch.tick(10.0) == [] and walks == []


def test_the_push_loop_walks_nothing_per_pass_and_one_settle_moves_the_topics(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = _ctx()
    loop = ctx.push = PushLoop(ctx)
    project = {"project": ctx.projects.home_id}
    seen: list[dict[str, Any]] = []
    for topic, args in (("board", {}), ("project", project), ("costs", project)):
        assert not isinstance(loop.subscribe(topic, args, seen.append), ops.Result)
    for i in range(3):  # the live reading's mark settles: the rev is steady after that
        loop.poll(10.0 * i)
    walks, sent = _walks(monkeypatch), len(seen)
    for i in range(PASSES):
        loop.poll(100.0 + 10.0 * i)
    assert walks == [] and len(seen) == sent
    watch = FileWatchThread(ctx)
    watch.feed([str(_idea(ctx))], 300.0)
    watch.tick(300.0 + QUIET_S)
    assert len(walks) == 1 and loop.woken.is_set()
    loop.poll(400.0)
    assert len(walks) == 1 and {e["topic"] for e in seen[sent:]} >= {"project"}


def test_the_notification_backend_sees_a_write(repo: Path) -> None:
    ctx = _ctx()
    before = ctx.settle(ctx.projects.all()[0])
    watch = FileWatchThread(ctx)
    try:
        assert watch.start() == NOTIFY
        _idea(ctx)
        assert _until(lambda: ctx.revs[ctx.projects.home_id] != before)
    finally:
        watch.stop()


class _Dies:
    """A notification backend that dies at its first wait."""

    def __init__(self, *_a: object) -> None:
        pass

    def watch(self, *_a: object) -> object:
        raise RuntimeError("the queue overflowed")

    def close(self) -> None:
        pass


class _Refused:
    def __init__(self, *_a: object) -> None:
        raise OSError("no inotify watch left")


@pytest.mark.parametrize("backend", [_Refused, _Dies], ids=["no-start", "dies"])
def test_with_no_notification_the_checks_every_five_seconds_see_a_write(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    backend: type,
) -> None:
    monkeypatch.setattr("watchfiles._rust_notify.RustNotify", backend)
    monkeypatch.setenv(times.TEST_ENV, "2:30:1:1:0.05")  # the check field shortened
    ctx = _ctx()
    before = ctx.settle(ctx.projects.all()[0])
    moved: list[str] = []
    watch = FileWatchThread(ctx, moved.append)
    try:
        started = watch.start()
        assert started == (CHECK if backend is _Refused else NOTIFY)
        assert command.files_line(started) == (
            command.CHECKS if backend is _Refused else command.WATCHES
        )
        _idea(ctx)
        assert _until(lambda: ctx.revs[ctx.projects.home_id] != before)
        assert watch.mode == CHECK
    finally:
        watch.stop()
    err = capsys.readouterr().err
    if backend is _Dies:
        assert STOPPED.format(reason="the queue overflowed") in err and moved == [CHECK]
    else:
        assert err == "" and moved == []

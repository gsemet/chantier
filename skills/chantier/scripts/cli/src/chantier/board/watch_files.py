"""The surface server's watch of the planning files: the system tells it of a change (inotify,
FSEvents, ReadDirectoryChangesW, through `watchfiles`); once a project's files are quiet for
`QUIET_S` (or `MOST_S` after the first change of a stream that never pauses), the server walks
that project once (`Context.settle`) and wakes the push loop. Where the notification watch cannot
start, or dies, the thread checks each project every `CHECK_S` instead (the user's decision for a
system with no notification, not a fallback). No timer walk while notifications work.

`Settler` is pure and `FileWatchThread.feed` / `tick` take the monotonic time, so a test drives
them with no sleep; `watchfiles` loads only once the board serves."""

from __future__ import annotations

import contextlib
import os
import sys
import threading
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from chantier.board.api import times
from chantier.board.context import Context
from chantier.board.fingerprint import counts_for
from chantier.core.errors import ChantierError

NOTIFY, CHECK = "notify", "check"  # the mode, as `server.json`'s `server` entry says it
QUIET_S = 1.0  # a project settles once its files are quiet this long
MOST_S = 5.0  # and at the latest this long after the first change of a stream
DEBOUNCE_MS, STEP_MS = 200, 50  # the notification backend's grouping of changes
TIMEOUT_MS = 250  # the backend returns this often with no change, so a quiet project settles
POLL_DELAY_MS = 300  # the backend's poll delay, used only if it polls (never forced here)
JOIN_S = 5.0
STOPPED = "board: file notifications stopped ({reason}); checks every 5 s"


class Settler:
    """Per project, the first and the last change of the window it is in."""

    def __init__(self, quiet: float = QUIET_S, most: float = MOST_S) -> None:
        self.quiet, self.most = quiet, most
        self._open: dict[str, tuple[float, float]] = {}

    def change(self, project_id: str, now: float) -> None:
        first = self._open.get(project_id, (now, now))[0]
        self._open[project_id] = (first, now)

    def due(self, now: float) -> list[str]:
        """The projects that settle now (their window closes): quiet for `quiet`, or open for
        `most`."""
        done = [
            p
            for p, (first, last) in self._open.items()
            if now - last >= self.quiet or now - first >= self.most
        ]
        for p in done:
            del self._open[p]
        return sorted(done)


def _key(path: str | Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def _home_of(key: str, homes: list[tuple[str, str]]) -> tuple[str, str] | None:
    """The project whose planning folder holds `key`, with the path inside it (`/`-separated)."""
    for home, project_id in homes:
        if key.startswith(home + os.sep):
            return project_id, key[len(home) + 1 :].replace(os.sep, "/")
    return None


class FileWatchThread:
    """The watch in a daemon thread: `start()` decides the mode (the notification watch is made
    in the caller's thread, so the mode is known when it returns), `stop()` ends it.
    `on_mode` is told when a dying notification watch moves to the check mode."""

    def __init__(self, ctx: Context, on_mode: Callable[[str], None] | None = None) -> None:
        self.ctx = ctx
        self.on_mode = on_mode
        self.settler = Settler()
        self.mode: str | None = None
        self._notify: Any = None  # the backend's watch, in the notification mode
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="file-watch", daemon=True)

    def roots(self) -> list[Path]:
        """What is watched: a surface's `projects/` folder (its projects' planning folders, and
        a project added or removed), else the one planning folder."""
        projects = self.ctx.projects
        if projects.surface is not None:
            return [(projects.surface / "projects").resolve()]
        return [projects.home.changes.resolve()]

    def start(self) -> str:
        try:
            from watchfiles._rust_notify import RustNotify

            paths = [str(r) for r in self.roots()]
            self._notify = RustNotify(paths, False, False, POLL_DELAY_MS, True, True)
            self.mode = NOTIFY
        except (ImportError, OSError, RuntimeError):
            self.mode = CHECK
        mode = self.mode  # read before the thread runs: a backend that dies at once moves it
        self._thread.start()
        return mode

    def _run(self) -> None:
        if self.mode == NOTIFY:
            self._notified()
        if self.mode == CHECK:
            while not self._stop.wait(times.check_s()):
                self.check()

    def _notified(self) -> None:
        """The notification mode, until the stop or the backend's death (the checks take over)."""
        try:
            self._watch()
        except Exception as e:
            self._died(e)
        finally:
            with contextlib.suppress(Exception):
                self._notify.close()

    def _died(self, error: Exception) -> None:
        reason = " ".join(str(error).split()) or type(error).__name__
        print(STOPPED.format(reason=reason), file=sys.stderr, flush=True)
        self.mode = CHECK
        if self.on_mode is not None:
            with contextlib.suppress(Exception):
                self.on_mode(CHECK)

    def _watch(self) -> None:
        while not self._stop.is_set():
            got = self._notify.watch(DEBOUNCE_MS, STEP_MS, TIMEOUT_MS, self._stop)
            if got == "stop":
                return
            if isinstance(got, set):
                self.feed((path for _change, path in got), time.monotonic())
            self.tick(time.monotonic())

    def feed(self, paths: Iterable[str], now: float) -> None:
        """Changed paths: each one the fingerprint covers opens or extends its project's window;
        a path of a surface's `projects/` outside any planning folder may add or remove a
        project. Locks and other files count for nothing."""
        projects = self.ctx.projects
        homes = [(_key(p.repo.changes.resolve()), p.id) for p in projects.all()]
        surface = projects.surface
        base = _key((surface / "projects").resolve()) if surface is not None else None
        listed = False
        for path in paths:
            key = _key(path)
            hit = _home_of(key, homes)
            if hit is not None:
                if counts_for(hit[1]):
                    self.settler.change(hit[0], now)
            elif base is not None and key.startswith(base + os.sep):
                listed = listed or key[len(base) + 1 :].count(os.sep) <= 1
        if listed:
            self._listed()

    def tick(self, now: float) -> list[str]:
        """Settle every project whose window closed: one walk each, the push loop woken."""
        done = self.settler.due(now)
        for project_id in done:
            project = self.ctx.projects.get(project_id)
            if project is not None:
                with contextlib.suppress(OSError, ChantierError):
                    self.ctx.settle(project)
        return done

    def _listed(self) -> None:
        """The projects' list may have moved: read it again, walk the new ones, wake the push."""
        with contextlib.suppress(OSError, ChantierError):
            self.ctx.projects.refresh()
            for project in self.ctx.projects.all():
                if project.id not in self.ctx.revs:
                    self.ctx.settle(project)
        if self.ctx.push is not None:
            self.ctx.push.wake()

    def check(self) -> None:
        """The check mode's look: each project walked once, a moved fingerprint being a change."""
        with contextlib.suppress(OSError, ChantierError):
            self.ctx.projects.refresh()
        for project in self.ctx.projects.all():
            with contextlib.suppress(OSError, ChantierError):
                self.ctx.settle(project)

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(JOIN_S)
        if not self._thread.is_alive() and self._notify is not None:
            with contextlib.suppress(Exception):
                self._notify.close()

"""The idle stop of a board started with `--stop-idle` (a watcher starts it so): once no client
has observed it (the push loop's `observed()`) for `IDLE_STOP_S`, counted from its start or from
the last moment one did, it stops by the path Ctrl-C and the seat rule take, so its writer's final
cycle runs before its `server` entry goes. The seats registered on it are no observers.
`IdleStop.poll(now)` takes the monotonic time, so a test drives it with no sleep."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from chantier.board.api import times

STOPPED = "board: no client for 30 min; stopped"
LOOK_S = 5.0  # the thread looks at least this often


class Runs:
    """The commands a client's `cli.run` runs now, and the moment the last one ended: one counts
    as a client for the idle stop, from its start to a little after its end (so the count of 30
    minutes starts again at its end, within one look of the thread)."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self._running = 0
        self._ended: float | None = None
        self._lock = threading.Lock()

    def begin(self) -> None:
        with self._lock:
            self._running += 1

    def end(self) -> None:
        with self._lock:
            self._running -= 1
            self._ended = self.clock()

    def running(self) -> bool:
        """A command runs now (the idle stop's grace after the last one's end is not counted)."""
        with self._lock:
            return self._running > 0

    def busy(self) -> bool:
        with self._lock:
            if self._running:
                return True
            return self._ended is not None and self.clock() - self._ended < LOOK_S + 1


class IdleStop:
    def __init__(self, observed: Callable[[], bool], stop: Callable[[], None], now: float) -> None:
        self.observed, self.stop = observed, stop
        self.since = now  # the start, or the last moment a client observed
        self.stopped = False

    def poll(self, now: float) -> bool:
        """One look: True once the board was stopped."""
        if self.stopped:
            return True
        if self.observed():
            self.since = now
            return False
        if now - self.since < times.idle_stop_s():
            return False
        self.stopped = True
        print(STOPPED, flush=True)
        self.stop()
        return True


class IdleThread:
    """`IdleStop` in a daemon thread."""

    def __init__(self, idle: IdleStop) -> None:
        self.idle = idle
        self._done = threading.Event()
        self._thread = threading.Thread(target=self._run, name="idle-stop", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        look = min(LOOK_S, times.idle_stop_s() / 4)
        while not self._done.wait(look):
            if self.idle.poll(time.monotonic()):
                return

    def stop(self) -> None:
        self._done.set()

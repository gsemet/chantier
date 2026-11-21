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

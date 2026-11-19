"""The surface server's hub loop: a thread of `chantier board` that tries `hub.lock` (never
waiting) every `poll_s()` until it holds it, then runs `Hub.cycle` whenever `Hub.due` says so.
`HubLoop.poll(now)` takes the monotonic time, so a test drives it with no sleep and no thread."""

from __future__ import annotations

import sys
import threading
import time
from collections.abc import Callable

from chantier import __version__
from chantier.core.repo import Repo
from chantier.hub import lock
from chantier.hub import times as hub_times
from chantier.hub.cycle import Hub

JOIN_S = 5.0


class HubLoop:
    def __init__(self, repo: Repo, version: str = __version__) -> None:
        self.repo, self.version = repo, version
        self.lock = lock.HubLock(repo.git_dir)
        self.hub: Hub | None = None

    def poll(self, now: float) -> None:
        """One look: the election while the lock is not held, then the cycle when due."""
        if self.hub is None and self.lock.acquire():
            self.hub = Hub(self.repo, self.version)
        if self.hub is not None and self.hub.due(now):
            self.hub.cycle(now)

    def note_error(self, e: Exception) -> None:
        """A cycle that raised: the error goes in the hub entry as a failed forge read's does."""
        if self.hub is not None:
            self.hub.note_error(e)

    def stop(self) -> None:
        """Remove the `hub` entry that names this process and release the lock."""
        if self.hub is not None:
            self.hub.close()
            self.hub = None
        self.lock.release()


class HubThread:
    """`HubLoop` in a daemon thread. A loop that dies ends the server: `on_death` is called after
    an error line on stderr."""

    def __init__(self, loop: HubLoop, on_death: Callable[[], None]) -> None:
        self.loop, self.on_death = loop, on_death
        self._done = threading.Event()
        self._thread = threading.Thread(target=self._run, name="forge-hub", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        try:
            while True:
                try:
                    self.loop.poll(time.monotonic())
                except Exception as e:  # one bad cycle does not end the server
                    self.loop.note_error(e)
                if self._done.wait(hub_times.poll_s()):
                    return
        except Exception as e:
            print(
                f"board: the forge hub stopped: {' '.join(str(e).split()) or type(e).__name__}",
                file=sys.stderr,
                flush=True,
            )
            self.on_death()

    def stop(self) -> None:
        """Stop the thread, then release the lock and remove the `hub` entry."""
        self._done.set()
        if self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(JOIN_S)
        self.loop.stop()

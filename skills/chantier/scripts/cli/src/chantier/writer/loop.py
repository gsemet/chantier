"""The surface server's writer loop: the election of `writer.lock` (never waited on), then
`Writer.cycle` whenever `Writer.due` says so or `writer.wake` is newer than the last cycle's start.
`WriterLoop.poll(now)` takes the monotonic time, so a test drives it with no sleep and no thread.
At the end, one final cycle limited to 30 s, then the entry goes and the lock is let go."""

from __future__ import annotations

import sys
import threading
import time

from chantier import __version__
from chantier.core import clock
from chantier.core.repo import Repo
from chantier.hub import lock
from chantier.writer import record, times
from chantier.writer.cycle import Writer

JOIN_S = times.FINAL_S + 5.0


class WriterLoop:
    def __init__(self, repo: Repo, version: str = __version__) -> None:
        self.repo, self.version = repo, version
        self.lock = lock.WriterLock(repo.git_dir)
        self.writer: Writer | None = None
        self.failed: Writer | None = None  # a writer that died: its `stopped` entry stays
        self._busy = threading.Lock()  # a cycle runs: the final one waits for it
        self._cycle_wall = 0.0  # the wall time of the last cycle's start

    def start(self) -> str | None:
        """Take the lock and write the entry; None on success, else why this process is not the
        writer (the lock is held by another process on this machine)."""
        if self.writer is not None:
            return None
        try:
            held = self.lock.acquire()
        except OSError as e:
            return f"{self.lock.path}: {e}"
        if not held:
            return (
                f"another process on this machine holds the writer's lock ({self.lock.path.name})"
            )
        self._cycle_wall = time.time()
        self.writer = Writer(self.repo, self.version)
        return None

    def _asked(self) -> bool:
        try:
            return lock.wake_path(self.repo.git_dir).stat().st_mtime > self._cycle_wall
        except OSError:
            return False

    def poll(self, now: float) -> None:
        """One look: the election while the lock is not held, then the cycle when due or asked."""
        if self.writer is None and self.start() is not None:
            return
        writer = self.writer
        if writer is None:
            return
        asked = self._asked()
        if asked or writer.due(now):
            with self._busy:
                self._cycle_wall = time.time()
                writer.cycle(now, asked=asked)

    def note_error(self, e: Exception) -> None:
        if self.writer is not None:
            self.writer.note_error(e)

    def _final(self) -> None:
        writer = self.writer
        if writer is None:
            return
        with self._busy:
            try:
                writer.cycle(time.monotonic(), final=True)
            except Exception as e:  # the entry says why; the stop goes on
                writer.note_error(e)

    def stop(self) -> None:
        """The final cycle, limited to `FINAL_S`; then remove the `writer` entry that names this
        process and release the lock. What the cycle did not push stays committed."""
        if self.writer is None:
            self.abort()  # a dead writer's `stopped` entry goes with the server
            return
        if self.writer is not None:
            runner = threading.Thread(target=self._final, name="writer-final", daemon=True)
            runner.start()
            runner.join(times.FINAL_S)
            self.abort()

    def abort(self) -> None:
        """No more cycle: remove the entry and release the lock."""
        for writer in (self.writer, self.failed):
            if writer is not None:
                writer.close()
        self.writer = self.failed = None
        self.lock.release()

    def fail(self, why: str) -> None:
        """The loop died: no more cycle, the lock is let go, and the entry stays, `stopped`, with
        the reason, until the server's end (`abort`), so reads say why writes are refused."""
        writer = self.writer
        if writer is not None:
            writer.record.update(
                state=record.STOPPED,
                reason="writer-stopped",
                text=record.cut(why),
                since=clock.now(),
            )
            writer.publish()
            self.failed, self.writer = writer, None
        self.lock.release()


class WriterThread:
    """`WriterLoop` in a daemon thread. A loop that dies leaves the server serving: its entry is
    turned `stopped` with its reason (so writes are refused) after an error line on stderr."""

    def __init__(self, loop: WriterLoop) -> None:
        self.loop = loop
        self._done = threading.Event()
        self._thread = threading.Thread(target=self._run, name="surface-writer", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        try:
            while True:
                try:
                    self.loop.poll(time.monotonic())
                except Exception as e:  # one bad cycle does not end the writer
                    self.loop.note_error(e)
                if self._done.wait(times.poll_s()):
                    return
        except Exception as e:
            why = " ".join(str(e).split()) or type(e).__name__
            print(f"board: the writer stopped: {why}", file=sys.stderr, flush=True)
            self.loop.fail(why)

    def stop(self) -> None:
        """Stop the thread, then run the final cycle, remove the entry and release the lock."""
        self._done.set()
        if self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(JOIN_S)
        self.loop.stop()

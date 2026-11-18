"""`chantier watch`: wait for the forge events of this project's running batch.

The watcher reads only its project's journal, never the forge, except as the hub (the process
that holds `hub.lock`), and then only through `Hub.cycle`. It ends once `quiet_s()` has passed
with no newer event, measured on its own monotonic clock from when it saw each event."""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

from chantier import __version__
from chantier.board.projects import project_name
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.repo import Repo
from chantier.hub import autostart, journal, lock
from chantier.hub import times as hub_times
from chantier.hub.cycle import Hub, running_batch

EVENTS, NO_BATCH = "events", "no-batch"


class Watch:
    """One watcher: the election, the hub's cycle when it is the hub, its project's journal past
    its cursor. `poll(now)` takes the monotonic time, so a test drives it with no sleep."""

    def __init__(self, repo: Repo, cursor: int, version: str = __version__) -> None:
        self.repo, self.cursor, self.version = repo, cursor, version
        self.project = project_name(repo)
        self.lock = lock.HubLock(repo.git_dir)
        self.session = autostart.session_key()
        self.own = lock.WatcherLock(repo.git_dir, self.project, self.session)
        self.hub: Hub | None = None
        self.events: list[dict[str, Any]] = []
        self.last_new: float | None = None

    def elect(self) -> None:
        """Try the locks, once each, when this watcher does not hold them: its own (so the
        session's `status` sees it) and the hub's."""
        self.own.acquire()
        if self.hub is None and self.lock.acquire():
            self.hub = Hub(self.repo, self.version)

    def start_line(self) -> str:
        self.elect()
        line = f"watch: {self.project} from cursor {self.cursor}"
        if self.hub is not None:
            return f"{line}, the hub"
        other = lock.other_version(lock.live(self.repo.git_dir), self.version)
        return f"{line}; hub is chantier {other}" if other else line

    def poll(self, now: float) -> str | None:
        """One look: the election, the hub's cycle when due, the journal. The reason this watcher
        ends (`events` or `no-batch`), else None."""
        self.elect()
        if self.hub is not None and self.hub.due(now):
            self.hub.cycle(now)
        entries = journal.read(self.repo.changes)[0]
        new = sorted(
            (e for e in entries if type(e.get("seq")) is int and e["seq"] > self.cursor),
            key=lambda e: e["seq"],
        )
        if new:
            self.events += new
            self.cursor = new[-1]["seq"]
            self.last_new = now
        if running_batch(self.repo) is None:
            return NO_BATCH
        if self.last_new is not None and now - self.last_new >= hub_times.quiet_s():
            return EVENTS
        return None

    def lines(self, reason: str) -> list[str]:
        out = [journal.event_text(e) for e in self.events]
        if reason == NO_BATCH:
            return [*out, f"watch: no running batch in {self.project}; ended"]
        batch = running_batch(self.repo)
        name = batch.id if batch is not None else self.project
        return [
            *out,
            f"watch: {name} still running: for the Chief of Staff, start again in the "
            f"background now: {autostart.watch_command(self.repo, self.cursor)}",
        ]

    def close(self) -> None:
        if self.hub is not None:
            self.hub.close()
        self.lock.release()
        self.own.release()


def watch(args: argparse.Namespace) -> list[str]:
    repo = Repo.find()
    name = project_name(repo)
    if running_batch(repo) is None:
        raise ChantierError(
            f"watch: no running batch in {name}: nothing to watch", EXIT_PRECONDITION
        )
    last = journal.last_seq(journal.read(repo.changes)[0])
    if args.after is not None and args.after > last:
        raise ChantierError(
            f"watch: --after {args.after} is past the journal's end ({last})", EXIT_USAGE
        )
    w = Watch(repo, last if args.after is None else args.after)
    try:
        print(w.start_line(), flush=True)
        while (reason := w.poll(time.monotonic())) is None:
            time.sleep(hub_times.poll_s())
        return w.lines(reason)
    finally:
        w.close()
        sys.stdout.flush()

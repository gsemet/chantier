"""`chantier watch`: wait for the events of this project's journal: the forge's (merges, CI red)
and the board's writes and an outside poller's issue events, with a running, a paused or no
batch.

The watcher reads only its project's journal, never the forge, except as the hub (the process
that holds `hub.lock`), and then only through `Hub.cycle`. It reads the lines for it only: its
audience holds `project`, its own `session:<key>` or a `--for` value; the others only move its
cursor. It ends once `quiet_s()` has passed with no newer event for it that wakes, measured on its
own monotonic clock from when it saw each one, and no sooner than `events.wake_every` after its
start, or when the project's seat is another session's. `--once --after SEQ` is the pull path: it
prints the lines past SEQ and takes no lock, reads no forge and starts nothing."""

from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from chantier import __version__
from chantier.board.projects import project_name
from chantier.board.seats import SEAT_CHECK_S
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.files import rel_in
from chantier.core.records import read_batch_json
from chantier.core.repo import Repo
from chantier.core.seat import read_seat
from chantier.hub import autostart, journal, lock, state
from chantier.hub import times as hub_times
from chantier.hub.cycle import Hub
from chantier.plugin_files import read_wake_rules

EVENTS, SEAT = "events", "seat"


def seat_moved(repo: Repo, session: str) -> bool:
    """Whether `seat.json` records a transcript that is not this session's key. No seat, a seat
    with no transcript, an unreadable one or a session keyed `none`: nothing to compare."""
    if session == autostart.NONE:
        return False
    try:
        held = read_seat(repo)
    except ChantierError:
        return False
    kept = re.sub(r"[^A-Za-z0-9-]", "", (held.transcript if held else None) or "")
    return bool(kept) and kept != session


def subscription(session: str, audiences: list[str] | tuple[str, ...] = ()) -> list[str]:
    """The audience values a watcher reads, each once: `project`, its own session (not with the
    key `none`), then the `--for` values in their order."""
    own = [] if session == autostart.NONE else [f"session:{session}"]
    return list(dict.fromkeys([journal.PROJECT, *own, *audiences]))


def open_batch(repo: Repo) -> str | None:
    """The id of the batch running or paused, None with none."""
    path = repo.batches / "batch.json"
    if not repo.store.is_file(rel_in(repo.store.root, path)):
        return None
    try:
        d = read_batch_json(repo.store, path)
    except (OSError, ValueError, ChantierError):
        return None
    return d.id if d.status in ("running", "paused") else None


@dataclass
class Rules:
    """What a watcher is told at its start: the `--for` values, `events.wake_every` in seconds
    (0 for none) and the first configuration problem outside the `events` block, if any."""

    audiences: list[str] = field(default_factory=list)
    wake_every: float = 0.0
    note: str | None = None


class Watch:
    """One watcher: the election, the hub's cycle when it is the hub, its project's journal past
    its cursor. `poll(now)` takes the monotonic time, so a test drives it with no sleep."""

    def __init__(
        self,
        repo: Repo,
        cursor: int,
        version: str = __version__,
        rules: Rules | None = None,
    ) -> None:
        self.repo, self.cursor, self.version = repo, cursor, version
        rules = rules or Rules()
        self.wake_every, self.note = rules.wake_every, rules.note
        self.started: float | None = None
        self.project = project_name(repo)
        self.lock = lock.HubLock(repo.git_dir)
        self.session = autostart.session_key()
        self.own = lock.WatcherLock(repo.git_dir, self.project, self.session)
        self.subscribed = subscription(self.session, rules.audiences)
        self.hub: Hub | None = None
        self.events: list[dict[str, Any]] = []
        self.last_new: float | None = None
        self.seat_at: float | None = None

    def serving(self) -> bool:
        """Whether `server.json` names a live surface server."""
        return state.live_entry(self.repo.git_dir, state.SERVER) is not None

    def elect(self) -> None:
        """Try the locks, once each, when this watcher does not hold them: its own (so the
        session's `status` sees it) and the hub's, only while no live surface server is named."""
        self.own.acquire()
        if self.hub is None and not self.serving() and self.lock.acquire():
            self.hub = Hub(self.repo, self.version)

    def yield_hub(self) -> None:
        """A surface server runs: this watcher is no longer the hub. It removes its `hub` entry
        and lets the lock go, and goes on reading its journal."""
        if self.hub is not None:
            self.hub.close()
            self.hub = None
        self.lock.release()

    def start_line(self) -> str:
        self.elect()
        line = f"watch: {self.project} from cursor {self.cursor} for {', '.join(self.subscribed)}"
        if self.hub is not None:
            line = f"{line}, the hub"
        else:
            other = state.other_version(
                state.live_entry(self.repo.git_dir, state.HUB), self.version
            )
            line = f"{line}; hub is chantier {other}" if other else line
        board = autostart.board_clause(self.repo, self.version)
        if board:
            line += f"; board is chantier {board}: its writes do not reach this watcher, restart it"
        return f"{line}; configuration: {self.note}" if self.note else line

    def poll(self, now: float) -> str | None:
        """One look: the election, the hub's cycle when due, the journal. The reason this watcher
        ends (`events` or `seat`), else None."""
        self.elect()
        if self.hub is not None and self.hub.due(now):
            self.hub.cycle(now)
        if self.hub is not None and self.serving():
            self.yield_hub()
        if self.started is None:
            self.started = now
        entries = journal.read(self.repo.store, self.repo.changes)[0]
        new = sorted(
            (e for e in entries if type(e.get("seq")) is int and e["seq"] > self.cursor),
            key=lambda e: e["seq"],
        )
        if new:
            mine = [e for e in new if journal.for_subscription(e, self.subscribed)]
            self.events += mine
            self.cursor = new[-1]["seq"]  # a line for others is passed, never printed
            if any(journal.waking(e) for e in mine):
                self.last_new = now
        if self.seat_at is None or now - self.seat_at >= SEAT_CHECK_S:
            self.seat_at = now
            if seat_moved(self.repo, self.session):
                return SEAT
        if (
            self.last_new is not None
            and now - self.last_new >= hub_times.quiet_s()
            and now - self.started >= self.wake_every
        ):
            return EVENTS
        return None

    def lines(self, reason: str) -> list[str]:
        out = [journal.event_text(e) for e in self.events]
        if reason == SEAT:
            return [*out, f"watch: the seat of {self.project} is another session's now; ended"]
        name = open_batch(self.repo) or f"{self.project} (no batch)"
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


def once(repo: Repo, after: int, audiences: list[str] | tuple[str, ...] = ()) -> list[str]:
    """The pull path: the lines past `after` that are for it, whether they wake or not, and the
    cursor of the last line read, whoever it was for, with the command for the next message."""
    subscribed = subscription(autostart.session_key(), audiences)
    entries = journal.read(repo.store, repo.changes)[0]
    last = journal.last_seq(entries)
    if after > last:
        raise ChantierError(
            f"watch: --after {after} is past the journal's end ({last})", EXIT_USAGE
        )
    new = sorted(
        (e for e in entries if type(e.get("seq")) is int and e["seq"] > after),
        key=lambda e: e["seq"],
    )
    return [
        *(journal.event_text(e) for e in new if journal.for_subscription(e, subscribed)),
        f"watch: cursor {last}; next, at the user's next message: "
        f"{autostart.pull_command(repo, last)}",
    ]


def watch(args: argparse.Namespace) -> list[str]:
    repo = Repo.find()
    for value in args.audience or []:
        if not journal.audience_ok(value):
            raise ChantierError(
                f'watch: --for "{value}": one of {journal.AUDIENCE_FORMS}', EXIT_USAGE
            )
    if args.once and args.after is None:
        raise ChantierError("watch --once needs --after SEQ", EXIT_USAGE)
    last = journal.last_seq(journal.read(repo.store, repo.changes)[0])
    if args.after is not None and args.after > last:
        raise ChantierError(
            f"watch: --after {args.after} is past the journal's end ({last})", EXIT_USAGE
        )
    if args.once:
        return once(repo, args.after, args.audience or [])
    rules = read_wake_rules(repo)
    if rules["events_problems"]:
        raise ChantierError(
            f"watch: {rules['events_problems'][0]}: fix it, then start the watcher again",
            EXIT_PRECONDITION,
        )
    w = Watch(
        repo,
        last if args.after is None else args.after,
        rules=Rules(args.audience or [], hub_times.wake_every_s(rules["seconds"]), rules["other"]),
    )
    try:
        print(w.start_line(), flush=True)
        while (reason := w.poll(time.monotonic())) is None:
            time.sleep(hub_times.poll_s())
        return w.lines(reason)
    finally:
        w.close()
        sys.stdout.flush()

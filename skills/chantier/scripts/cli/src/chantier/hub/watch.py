"""`chantier watch`: wait for the events of this project, with a running, a paused or no batch:
the forge's (merges, CI red), the board's writes and an outside poller's issue events.

The watcher reads no journal file and no forge: it subscribes to the surface server's `events`
topic for its project from its cursor (`feed.py`), the server being the only forge hub. With no
server running it starts one, detached (`serve --seat <session> --stop-idle`), when the project's
seat is this session's; else it starts nothing and ends with the line that says why. On a running
board it registers the seat when the seat is this session's, so that board follows it too. It
reads the lines for it only: its audience holds `project`, its own `session:<key>` or a `--for`
value; the others only move its cursor. It ends once `quiet_s()` has passed with no newer event
for it that wakes, measured on its own monotonic clock from when it saw each one, and no sooner
than `events.wake_every` after its start; or `idle_end_s()` (2 h) after its start with none, so a
watcher an ended session left behind stops observing the board; or when the project's seat is
another session's. `--once --after SEQ` is the pull path: it prints the journal's lines past SEQ
and takes no lock, reaches no server and starts nothing."""

from __future__ import annotations

import argparse
import contextlib
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from chantier import __version__
from chantier.board import running
from chantier.board.projects import project_name
from chantier.board.seats import SEAT_CHECK_S
from chantier.clients.tui.link import KEY, Event, Linked, Refusal, Refused
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.files import rel_in
from chantier.core.records import read_batch_json
from chantier.core.repo import Repo
from chantier.core.seat import read_seat
from chantier.hub import arrival_mark, autostart, journal, lock
from chantier.hub import times as hub_times
from chantier.hub.feed import Board, Feed, Got, passed_on, serve_argv
from chantier.hub.lines import foreign_build_clause
from chantier.hub.watch_lines import (
    BAD_KEY,
    EVENTS_END,
    IDLE_END,
    NO_KEY,
    NO_SEAT,
    NO_TRANSCRIPT,
    NOT_SERVED,
    NOT_STARTED,
    OTHER_VERSION,
    REFUSED,
    SEAT_LINE,
    UNREADABLE_SEAT,
    Ended,
    told,
)
from chantier.plugin_files import cli_command, read_wake_rules

EVENTS, SEAT, IDLE, END = "events", "seat", "idle", "end"
START_S = 20.0  # a board the watcher starts answers within this, else the watcher ends
SILENT_S = 20.0  # a recorded board links within this, else it holds the surface and is silent
RETRY_S = 5.0  # a lost link is tried again this often
STEP_S = 0.5  # the wait between two looks at a starting board


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
    """One watcher: its lock, its link to the board (started when none runs and the seat is this
    session's), the lines for it past its cursor. `poll(now)` takes the monotonic time and reads
    what the link delivered since the last call, so a test drives it with no sleep, `Board`
    replaced by a fake."""

    def __init__(
        self,
        repo: Repo,
        cursor: int,
        version: str = __version__,
        rules: Rules | None = None,
        board: Board | None = None,
    ) -> None:
        self.repo, self.cursor, self.version = repo, cursor, version
        rules = rules or Rules()
        self.wake_every, self.note = rules.wake_every, rules.note
        self.board = board or Board()
        self.started: float | None = None
        self.project = project_name(repo)
        self.session = autostart.session_key()
        self.own = lock.WatcherLock(repo.git_dir, self.project, self.session)
        self.subscribed = subscription(self.session, rules.audiences)
        self.events: list[dict[str, Any]] = []
        self.last_new: float | None = None
        self.seat_at: float | None = None
        self.feed: Feed | None = None
        self.entry: dict[str, Any] = {}
        self.lost_at: float | None = None
        self.unlinked_since: float | None = None  # links opened that no transport answered yet
        self.end: Ended | None = None

    # the board

    def _texts(self) -> dict[str, str]:
        return {
            "project": self.project,
            "cli": cli_command(self.repo),
            "watch": autostart.watch_command(self.repo, self.cursor),
        }

    def _where(self) -> dict[str, str]:
        pid = self.entry.get("pid")
        return {
            **self._texts(),
            "where": f"{self.entry.get('host')}:{self.entry.get('port')}",
            "stop": running.stop_command(pid) if isinstance(pid, int) else "its stop command",
        }

    def seat_rule(self) -> str:
        """With no server running: the seat's session it starts the board for, else the end that
        says why, in this order: no session key, no seat, a seat with no transcript, another's."""
        texts = self._texts()
        if self.session == autostart.NONE:
            raise Ended(NO_KEY.format(**texts))
        try:
            seat = read_seat(self.repo)
        except ChantierError as e:
            raise Ended(UNREADABLE_SEAT.format(**texts, error=e)) from e
        if seat is None:
            raise Ended(NO_SEAT.format(**texts))
        if not re.sub(r"[^A-Za-z0-9-]", "", seat.transcript or ""):
            raise Ended(NO_TRANSCRIPT.format(**texts))
        if seat.session and autostart.holds_seat(seat.transcript):
            return seat.session
        raise Ended(SEAT_LINE.format(**texts), 0)

    def start_board(self) -> tuple[dict[str, Any], str]:
        """Start the board for this session's seat, detached, and wait for `server.json` to name
        a live one that answers the probe with its key: its entry and the key."""
        session = self.seat_rule()
        self.board.spawn(serve_argv(self.repo, session), self.repo.root)
        deadline = self.board.clock() + START_S
        while True:
            found = self.board.recorded(self.repo.git_dir)
            if found is not None:
                self.entry = found[0]
                answer = self.board.probe(found[0]["host"], found[0]["port"], found[1])
                if isinstance(answer, dict):
                    return found
                if answer == "another-key":
                    raise Ended(BAD_KEY.format(**self._where()))
            if self.board.clock() >= deadline:
                if found is not None:
                    raise Ended(f"watch: {running.silent_text(found[0])}")
                raise Ended(NOT_STARTED.format(cli=cli_command(self.repo), session=session))
            self.board.sleep(STEP_S)

    def register(self, entry: dict[str, Any], key: str) -> None:
        """On a board already running: this session's seat registered, so it follows it too."""
        if self.session == autostart.NONE:
            return
        try:
            seat = read_seat(self.repo)
        except ChantierError:
            return
        if seat is not None and seat.session and autostart.holds_seat(seat.transcript):
            self.board.register(entry, key, self.project, seat.session)

    def connect(self, now: float) -> int | None:
        """The link to the recorded board, or to the one it starts: the started board's PID (its
        own process, from its entry), else None."""
        found = self.board.recorded(self.repo.git_dir)
        started = None
        if found is None:
            found = self.start_board()
            started = int(found[0]["pid"])
            self.unlinked_since = None
        else:
            self.register(*found)
        self.entry = found[0]
        self.feed = self.board.link(found[0], found[1], self.project, self.cursor)
        self.lost_at = None
        if self.unlinked_since is None:
            self.unlinked_since = now
        return started

    def start(self) -> list[str]:
        """Its lock, the link, then the start line and the board's lines to pass on. Raises
        `Ended` when it cannot link."""
        self.own.acquire()
        pid = self.connect(self.board.clock())
        line = f"watch: {self.project} from cursor {self.cursor} for {', '.join(self.subscribed)}"
        if pid is not None:
            line += f"; started the board (PID {pid})"
        if other := autostart.board_clause(self.repo, self.version):
            line += OTHER_VERSION.format(version=other)
        elif foreign := foreign_build_clause(self.repo, self.version):
            line += f"; {foreign}"
        if self.note:
            line += f"; configuration: {self.note}"
        return [line, *passed_on(self.repo, self.entry)]

    # what comes

    def _take(self, item: Got, now: float) -> None:
        if isinstance(item, Refusal):
            text = BAD_KEY if item.kind == KEY else REFUSED
            raise Ended(text.format(**self._where(), sentence=item.sentence))
        if isinstance(item, Refused):
            raise Ended(NOT_SERVED.format(**self._where(), error=f"{item.status} {item.error}"))
        if isinstance(item, Linked):
            if item.transport is not None:
                self.unlinked_since = None
            elif self.feed is not None:
                self.feed.close()
                self.feed, self.lost_at = None, now
            return
        if isinstance(item, Event) and item.topic == "events":
            self._lines(item.data.get("lines") or [], now)

    def _lines(self, lines: list[Any], now: float) -> None:
        new = sorted(
            (
                e
                for e in lines
                if isinstance(e, dict) and type(e.get("seq")) is int and e["seq"] > self.cursor
            ),
            key=lambda e: int(e["seq"]),
        )
        if not new:
            return
        mine = [e for e in new if journal.for_subscription(e, self.subscribed)]
        self.events += mine
        self.cursor = int(new[-1]["seq"])  # a line for others is passed, never printed
        if any(journal.waking(e) for e in mine):
            self.last_new = now

    def _link(self, now: float) -> None:
        if self.feed is None and (self.lost_at is None or now - self.lost_at >= RETRY_S):
            self.connect(now)
        for item in self.feed.drain() if self.feed is not None else []:
            self._take(item, now)
        if self.unlinked_since is not None and now - self.unlinked_since >= SILENT_S:
            raise Ended(f"watch: {running.silent_text(self.entry)}")

    def poll(self, now: float) -> str | None:
        """One look: its lock, what the link delivered, the link again once lost. The reason this
        watcher ends (`events`, `seat`, `idle` or `end`), else None."""
        self.own.acquire()
        if self.started is None:
            self.started = now
        try:
            self._link(now)
        except Ended as e:
            self.end = e
            return END
        if self.seat_at is None or now - self.seat_at >= SEAT_CHECK_S:
            self.seat_at = now
            if seat_moved(self.repo, self.session):
                return SEAT
        if now - self.started < self.wake_every:
            return None
        if self.last_new is not None and now - self.last_new >= hub_times.quiet_s():
            return EVENTS
        if self.last_new is None and now - self.started >= hub_times.idle_end_s():
            return IDLE
        return None

    def lines(self, reason: str) -> list[str]:
        out = [told(e) for e in self.events]
        with contextlib.suppress(OSError, ChantierError):
            arrival_mark.tell_arrivals(self.repo, self.events)
        if reason == END and self.end is not None:
            return [*out, self.end.line]
        if reason == SEAT:
            return [*out, SEAT_LINE.format(project=self.project)]
        name = open_batch(self.repo) or f"{self.project} (no batch)"
        text = IDLE_END if reason == IDLE else EVENTS_END
        return [*out, text.format(name=name, watch=autostart.watch_command(self.repo, self.cursor))]

    def code(self, reason: str) -> int:
        return self.end.code if reason == END and self.end is not None else 0

    def close(self) -> None:
        if self.feed is not None:
            self.feed.close()
            self.feed = None
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
    mine = [e for e in new if journal.for_subscription(e, subscribed)]
    arrival_mark.tell_arrivals(repo, mine)
    return [
        *(journal.event_text(e) for e in mine),
        f"watch: cursor {last}; next, at the user's next message: "
        f"{autostart.pull_command(repo, last)}",
    ]


def run(w: Watch) -> tuple[list[str], int]:
    """Start the watcher, print its start lines, poll until it ends: its last lines and code."""
    try:
        try:
            print("\n".join(w.start()), flush=True)
        except Ended as e:
            return [e.line], e.code
        while (reason := w.poll(time.monotonic())) is None:
            time.sleep(hub_times.poll_s())
        return w.lines(reason), w.code(reason)
    finally:
        w.close()
        sys.stdout.flush()


def watch(args: argparse.Namespace) -> list[str] | tuple[list[str], int]:
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
    return run(
        Watch(
            repo,
            last if args.after is None else args.after,
            rules=Rules(
                args.audience or [], hub_times.wake_every_s(rules["seconds"]), rules["other"]
            ),
        )
    )

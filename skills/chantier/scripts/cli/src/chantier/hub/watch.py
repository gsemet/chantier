"""`chantier watch`: wait for the events of this project, with a running, a paused or no batch.

It reads no journal file and no forge: it subscribes to the surface server's `events` topic for
its project from its cursor (`feed.py`), and reads the lines for it only (its audience holds
`project`, its own `session:<key>` or a `--for` value); the others only move its cursor. With no
server running it starts one, detached, when the project's seat is this session's. It tells the
events it gathered once `quiet_s()` has passed with no newer one that wakes, and no sooner than
`events.wake_every` after its start or last telling: plain, it then ends; with `--stream` (the
form printed on Claude Code, run through `Monitor`) it prints them with one `still watching` line
and runs on. It ends when the seat is another session's, or, while no batch is in flight
(`batch_prs.followed_batch`), `idle_end_s()` (2 h) after the latest of its start, its last waking
line and the last moment it saw a batch in flight.

A watch run by the session that the running or paused batch records as its Foreman is the
Foreman's watcher (`watch_reads.foreman_end`): it reads only that batch's merge, red-CI and
wait-met lines, starts no server and never ends on the seat. `--once --after SEQ` is the pull
path: it prints the journal's lines past SEQ, takes no lock, reaches no server, starts nothing.

At each telling, the steering session's watcher prints its batch's `state:` line just before its
last line (`watch_reads.steering_state`)."""

from __future__ import annotations

import contextlib
import sys
import time
from typing import Any

from chantier import __version__
from chantier.board import running
from chantier.board.projects import project_name
from chantier.board.seats import SEAT_CHECK_S
from chantier.clients.tui.link import KEY, Event, Linked, Refusal, Refused
from chantier.core.errors import ChantierError
from chantier.core.repo import Repo
from chantier.core.seat import read_seat
from chantier.hub import arrival_mark, autostart, batch_prs, journal, lock, state
from chantier.hub import times as hub_times
from chantier.hub import watch_confirm as confirm
from chantier.hub.feed import Board, Feed, Got, passed_on, serve_argv
from chantier.hub.lines import foreign_build_clause
from chantier.hub.watch_lines import (
    BAD_KEY,
    EVENTS_END,
    FOREMAN_EVENTS_END,
    FOREMAN_IDLE_END,
    FOREMAN_NO_SERVER,
    IDLE_END,
    NO_BOARD,
    NOT_SERVED,
    NOT_STARTED,
    OTHER_VERSION,
    REFUSED,
    SEAT_LINE,
    STRAY,
    STREAM_TOLD,
    Ended,
    told,
)
from chantier.hub.watch_reads import (
    Rules,
    foreman_end,
    foreman_lines,
    open_batch,
    seat_moved,
    steering_state,
    subscription,
)
from chantier.hub.watch_seat import seat_rule
from chantier.plugin_files import cli_command

EVENTS, SEAT, IDLE, END = "events", "seat", "idle", "end"
START_S = 20.0  # a board the watcher starts answers within this, else the watcher ends
SILENT_S = 20.0  # a recorded board links within this, else it holds the surface and is silent
RETRY_S = 5.0  # a lost link is tried again this often
STEP_S = 0.5  # the wait between two looks at a starting board


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
        self.build = state.build_source()  # the build this watcher would start a board of
        self.waiting = False  # no board started: a chantier dev session's build serves the surface
        rules = rules or Rules()
        self.wake_every, self.note, self.stream = rules.wake_every, rules.note, rules.stream
        self.board = board or Board()
        self.started: float | None = None
        self.told_at: float | None = None  # the last block told (`--stream`)
        self.woke_at: float | None = None  # the last new line for it that wakes, kept when told
        self.batch_at: float | None = None  # the last read of the batch
        self.in_flight = False  # a batch in flight at that read (`batch_prs.followed_batch`)
        self.flight_at: float | None = None  # the last moment it saw a batch in flight
        self.project = project_name(repo)
        self.session = autostart.session_key()
        self.own = lock.WatcherLock(repo.git_dir, self.project, self.session)
        self.subscribed = subscription(self.session, rules.audiences)
        d = autostart.foreman_batch(repo)  # the batch that records this session as its Foreman
        self.foreman = d.id if d is not None else None
        self.events: list[dict[str, Any]] = []
        self.last_new: float | None = None
        self.seat_at: float | None = None
        self.feed: Feed | None = None
        self.entry: dict[str, Any] = {}
        self.lost_at: float | None = None
        self.unlinked_since: float | None = None  # links opened, none answered by the server
        self.key, self.pid = "", None  # the recorded server this link is for: its key and PID
        self.stray: int | None = None  # the PID of another process that answered the link
        self.checked_at: float | None = None  # the last look at the record, while linked
        self.spawned: int | None = None  # the PID of the process this watcher spawned
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
        """With no server running: the seat's session it starts the board for, else the end."""
        return seat_rule(self.repo, self.session, self._texts())

    def start_board(self) -> tuple[dict[str, Any], str] | None:
        """Start the board for this session's seat, detached, and wait for `server.json` to name
        a live one that answers the probe with its key: its entry and the key. None, with nothing
        spawned, while a chantier dev session of the surface holds its seat with another build
        than this watcher's: that build serves the surface, and this watcher links when its
        board runs."""
        session = self.seat_rule()
        if autostart.other_dev_build(self.repo, self.build) is not None:
            return None
        self.spawned = self.board.spawn(serve_argv(self.repo, session), self.repo.root)
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
        if self.session == autostart.NONE or self.foreman is not None:
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
        self.waiting = False
        if found is None and self.foreman is not None:  # the seat is not its: it starts none
            raise Ended(FOREMAN_NO_SERVER.format(project=self.project))
        if found is None:
            found = self.start_board()
            if found is None:  # no link, no board: tried again as a lost link is
                self.waiting, self.lost_at = True, now
                return None
            started = int(found[0]["pid"])
            if not confirm.started_by(started, self.spawned):
                started = None  # another start won the surface: this one joins its board
            self.unlinked_since = None
        else:
            self.register(*found)
        self.entry, self.key, self.pid = found[0], found[1], found[0].get("pid")
        self.checked_at = now
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
        if self.waiting:
            line += NO_BOARD
        if other := autostart.board_clause(self.repo, self.version):
            line += OTHER_VERSION.format(version=other)
        elif foreign := foreign_build_clause(self.repo, self.version):
            line += f"; {foreign}"
        if self.note:
            line += f"; configuration: {self.note}"
        return [line, *([] if self.waiting else passed_on(self.repo, self.entry))]

    # what comes

    def _take(self, item: Got, now: float) -> None:
        if isinstance(item, Refusal):
            text = BAD_KEY if item.kind == KEY else REFUSED
            raise Ended(text.format(**self._where(), sentence=item.sentence))
        if isinstance(item, Refused):
            raise Ended(NOT_SERVED.format(**self._where(), error=f"{item.status} {item.error}"))
        if isinstance(item, Linked):
            if item.transport is not None:
                answered = confirm.answering_pid(self.board, self.entry, self.key, item)
                self.stray = confirm.other_than_recorded(
                    self.board, self.repo.git_dir, answered, self.pid
                )
                if self.stray is None:
                    self.unlinked_since = None
                elif self.feed is not None:  # not the server that holds the hub: not linked
                    self.feed.close()
                    self.feed, self.lost_at = None, now
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
        if self.foreman is not None:  # only its batch's lines it acts on
            mine = foreman_lines(mine, self.foreman)
        self.events += mine
        self.cursor = int(new[-1]["seq"])  # a line for others is passed, never printed
        if any(journal.waking(e) for e in mine):
            self.last_new = self.woke_at = now

    def _link(self, now: float) -> None:
        if self.feed is None and (self.lost_at is None or now - self.lost_at >= RETRY_S):
            self.connect(now)
        for item in self.feed.drain() if self.feed is not None else []:
            self._take(item, now)
            if self.feed is None:  # lost, or not the recorded server: what follows is dropped
                break
        if self.feed is not None and now - (self.checked_at or 0.0) >= RETRY_S:
            self.checked_at = now
            if confirm.moved(self.board, self.repo.git_dir, self.pid):  # a restart: link again
                self.feed.close()
                self.feed = None
                self.connect(now)
        if self.unlinked_since is not None and now - self.unlinked_since >= SILENT_S:
            if self.stray is None:
                raise Ended(f"watch: {running.silent_text(self.entry)}")
            stop = running.stop_command(self.stray)
            text = {**self._where(), "stray": self.stray, "pid": self.pid, "stop": stop}
            raise Ended(STRAY.format(**text))

    def _flight(self, now: float) -> None:
        """The batch in flight, read at most every `SEAT_CHECK_S`; the last moment it was seen."""
        if self.batch_at is None or now - self.batch_at >= SEAT_CHECK_S:
            self.batch_at = now
            self.in_flight = batch_prs.followed_batch(self.repo) is not None
        if self.in_flight:
            self.flight_at = now

    def _idle(self, now: float, started: float) -> bool:
        """No batch in flight, and `idle_end_s()` passed since the latest of its start, its last
        line that wakes and the last moment it saw a batch in flight."""
        if self.in_flight or self.last_new is not None:
            return False
        since = max(started, self.woke_at or started, self.flight_at or started)
        return now - since >= hub_times.idle_end_s()

    def poll(self, now: float) -> str | None:
        """One look: its lock, what the link delivered, the link again once lost. The reason this
        watcher ends or tells (`events`, `seat`, `idle` or `end`), else None; with `--stream`,
        `events` is a block to tell (`tell`), and the watcher runs on."""
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
            if self.foreman is not None:  # never on the seat: on its batch's record
                self.end = foreman_end(self.repo, self.foreman, self.session)
                if self.end is not None:
                    return END
            elif seat_moved(self.repo, self.session):
                return SEAT
        self._flight(now)
        since = self.started if self.told_at is None else self.told_at
        if now - since < self.wake_every:
            return None
        if self.last_new is not None and now - self.last_new >= hub_times.quiet_s():
            return EVENTS
        return IDLE if self._idle(now, self.started) else None

    def _told(self) -> list[str]:
        out = [told(e) for e in self.events]
        with contextlib.suppress(OSError, ChantierError):
            arrival_mark.tell_arrivals(self.repo, self.events)
        return out

    def _name(self) -> str:
        return open_batch(self.repo) or f"{self.project} (no batch)"

    def tell(self, now: float) -> list[str]:
        """`--stream`: the block of events gathered and the `still watching` line; the block is
        emptied and the next comes no sooner than `events.wake_every` from now."""
        out = [*self._told(), *steering_state(self.repo, self.foreman)]
        out.append(
            STREAM_TOLD.format(
                name=self._name(),
                n=self.cursor,
                watch=autostart.watch_command(self.repo, self.cursor),
            )
        )
        self.events, self.last_new, self.told_at = [], None, now
        return out

    def lines(self, reason: str) -> list[str]:
        out = self._told()
        if reason == END and self.end is not None:
            return [*out, self.end.line]
        if reason == SEAT:
            return [*out, SEAT_LINE.format(project=self.project)]
        if self.foreman is not None:
            text = FOREMAN_IDLE_END if reason == IDLE else FOREMAN_EVENTS_END
        else:
            text = IDLE_END if reason == IDLE else EVENTS_END
        end = text.format(name=self._name(), watch=autostart.watch_command(self.repo, self.cursor))
        return [*out, *steering_state(self.repo, self.foreman), end]

    def code(self, reason: str) -> int:
        return self.end.code if reason == END and self.end is not None else 0

    def close(self) -> None:
        if self.feed is not None:
            self.feed.close()
            self.feed = None
        self.own.release()


def run(w: Watch) -> tuple[list[str], int]:
    """Start the watcher, print its start lines, poll until it ends: its last lines and code.
    With `--stream`, each block of events is printed in one write as it comes, and it polls on."""
    try:
        try:
            print("\n".join(w.start()), flush=True)
        except Ended as e:
            return [e.line], e.code
        while True:
            now = time.monotonic()
            reason = w.poll(now)
            if reason == EVENTS and w.stream:
                print("\n".join(w.tell(now)), flush=True)
            elif reason is not None:
                return w.lines(reason), w.code(reason)
            time.sleep(hub_times.poll_s())
    finally:
        w.close()
        sys.stdout.flush()

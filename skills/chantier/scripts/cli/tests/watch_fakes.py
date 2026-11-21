"""A board for the watcher's tests: `FakeBoard` replaces `hub.feed.Board` whole, so a `Watch`
runs with no server, no process and no sleep. Its feed serves the journal file's lines past the
cursor it was opened with, each told as the server's `events` topic tells it."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from chantier import __version__
from chantier.board.api.topics import _told
from chantier.clients.tui.link import Event, Linked
from chantier.core.repo import Repo
from chantier.hub import journal
from chantier.hub.feed import Board, Feed, Got

PID = 4242  # the board's own process, as `server.json` names it
KEY = "k"


def entry(**changes: Any) -> dict[str, Any]:
    """A `server` entry of `server.json`."""
    return {
        "pid": PID,
        "host": "127.0.0.1",
        "port": 1,
        "version": __version__,
        "files": "notify",
    } | changes


class JournalFeed:
    """A link that answers at the first drain, then gives the journal's new lines each drain;
    `extra` items are given at the next drain, before the lines."""

    def __init__(self, repo: Repo, after: int, transport: str | None = "ws") -> None:
        self.repo, self.after, self.transport = repo, after, transport
        self.extra: list[Got] = []
        self.answered = False
        self.closed = False

    def drain(self) -> list[Got]:
        out: list[Got] = []
        if not self.answered and self.transport is not None:
            out.append(Linked(self.transport))
            self.answered = True
        out += self.extra
        self.extra = []
        if self.closed or any(isinstance(x, Linked) and x.transport is None for x in out):
            return out
        lines = [
            e
            for e in journal.read(self.repo.store, self.repo.changes)[0]
            if type(e.get("seq")) is int and e["seq"] > self.after
        ]
        if lines:
            self.after = int(lines[-1]["seq"])
            out.append(Event("events", "events", {"lines": [_told(e) for e in lines]}, None))
        return out

    def close(self) -> None:
        self.closed = True


class FakeBoard(Board):
    """The recorded server (`running`: its entry, or None), what the probe answers, and what the
    watcher asked of it: the starts, the registrations and the links it opened. `starts` is
    called at each spawn (to record a server, or not); the clock moves only by `sleep`."""

    def __init__(
        self,
        repo: Repo,
        running: dict[str, Any] | None = None,
        answer: dict[str, Any] | str | None = None,
        starts: Callable[[FakeBoard], None] | None = None,
        transport: str | None = "ws",
    ) -> None:
        self.repo, self.running, self.transport = repo, running, transport
        self.answer = {"protocol": 1} if answer is None else answer
        self.starts = starts
        self.now = 0.0
        self.spawned: list[list[str]] = []
        self.registered: list[tuple[str, str]] = []
        self.feeds: list[tuple[int, JournalFeed]] = []

    def recorded(self, git_dir: Path) -> tuple[dict[str, Any], str] | None:
        return None if self.running is None else (self.running, KEY)

    def probe(self, host: str, port: int, key: str) -> dict[str, Any] | str | None:
        return self.answer

    def register(self, entry: dict[str, Any], key: str, project: str, session: str) -> bool:
        self.registered.append((project, session))
        return True

    def link(self, entry: dict[str, Any], key: str, project: str, after: int) -> Feed:
        feed = JournalFeed(self.repo, after, self.transport)
        self.feeds.append((after, feed))
        return feed

    def spawn(self, argv: list[str], cwd: Path) -> None:
        self.spawned.append(argv)
        if self.starts is not None:
            self.starts(self)

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def serving(board: FakeBoard) -> None:
    """A start that records a server at once."""
    board.running = entry()


def served(repo: Repo, **kw: Any) -> FakeBoard:
    """A board already running."""
    return FakeBoard(repo, entry(), **kw)

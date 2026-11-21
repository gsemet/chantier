"""What a request is, and what the routes share: the projects, the key, the seats, and each
project's settled fingerprint (`revs`), which the file watch keeps and the reads use."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chantier.board.costs import Live
from chantier.board.fingerprint import StateCache, fingerprint
from chantier.board.key import KeyFile
from chantier.board.projects import Project, Projects
from chantier.board.prs import ForgeReads
from chantier.board.seats import Seats


@dataclass
class Request:
    method: str
    path: str  # percent-decoded
    query: dict[str, str]
    headers: dict[str, str]  # names in lower case
    body: bytes = b""


@dataclass
class Context:
    projects: Projects
    key: KeyFile
    seats: Seats
    version: str
    stop: Callable[[], None]
    ui: Path | None  # the folder of static files served at `/`; `None`: the API only
    bound: tuple[str, int] | None = None  # the address the board listens on
    cache: StateCache = field(default_factory=StateCache)
    reads: ForgeReads = field(default_factory=ForgeReads)  # the PRs page's forge reads
    # the API's push: per (project, batch) the PR links and the answer of a batch whose PRs are
    # all done, so a watch reads the forge no more until a PR joins
    prs_done: dict[tuple[str, str], tuple[tuple[str, ...], dict[str, Any]]] = field(
        default_factory=dict[tuple[str, str], tuple[tuple[str, ...], dict[str, Any]]]
    )
    push: Any = None  # the API's `PushLoop` (typed there: it imports this module), set when serving
    # the API's open WebSockets, those still waiting for their `hello` too (each has `welcomed`,
    # `credential` and a thread-safe `drop(code)`); changed in the event loop's thread only
    sockets: list[Any] = field(default_factory=list[Any])
    # the `events` topic's reading of each project's journal file, kept while its mark holds
    journal_seen: dict[Path, tuple[tuple[int, int], list[dict[str, Any]]]] = field(
        default_factory=dict[Path, tuple[tuple[int, int], list[dict[str, Any]]]]
    )
    # each project's fingerprint as it was at its last settle: the reads use it and walk nothing
    revs: dict[str, str] = field(default_factory=dict[str, str])
    _lives: dict[str, Live] = field(default_factory=dict[str, Live])
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def live(self, project: Project) -> Live:
        """The project's live figure, made at its first use."""
        with self._lock:
            if project.id not in self._lives:
                self._lives[project.id] = Live(project.repo)
            return self._lives[project.id]

    def settle(self, project: Project) -> str:
        """Walk the project's files once (`fingerprint`), keep the result, and wake the push
        loop when it moved: what the file watch does once a change settles, and a board's write
        does after it wrote."""
        rev = fingerprint(project.repo.store, project.repo.changes)
        with self._lock:
            moved = self.revs.get(project.id) != rev
            self.revs[project.id] = rev
        if moved and self.push is not None:
            self.push.wake()
        return rev

    def rev(self, project: Project) -> str:
        """The project's kept fingerprint; one walk, kept, for a project with none yet."""
        with self._lock:
            kept = self.revs.get(project.id)
        return kept if kept is not None else self.settle(project)

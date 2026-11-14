"""What a request is, and what the routes share: the projects, the key, the seats."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from chantier.board.costs import Live
from chantier.board.fingerprint import StateCache
from chantier.board.key import KeyFile
from chantier.board.projects import Project, Projects
from chantier.board.seats import Seats


@dataclass
class Request:
    method: str
    path: str  # percent-decoded
    query: dict[str, str]
    headers: dict[str, str]  # names in lower case
    body: bytes = b""


@dataclass
class LastPush:
    """The last push time a running process saw: the tool records none, so a board that watches
    remembers the latest `synced` time it read."""

    _at: float | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def see(self, seen: float | None) -> float | None:
        with self._lock:
            if seen is not None and (self._at is None or seen > self._at):
                self._at = seen
            return self._at


@dataclass
class Context:
    projects: Projects
    key: KeyFile
    seats: Seats
    version: str
    stop: Callable[[], None]
    cache: StateCache = field(default_factory=StateCache)
    last_push: LastPush = field(default_factory=LastPush)
    _lives: dict[str, Live] = field(default_factory=dict[str, Live])
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def live(self, project: Project) -> Live:
        """The project's live figure, made at its first use."""
        with self._lock:
            if project.id not in self._lives:
                self._lives[project.id] = Live(project.repo)
            return self._lives[project.id]

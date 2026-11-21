"""The hub's cycle: for every project of the surface that the interest registry holds a PR for,
one forge read through the connector of its forge, the providers judging what it shows, and the
events appended to the project's journal. It runs no git command, records nothing in a batch,
messages no agent and writes nothing but the journals and the `hub` entry of `server.json`.

`connectors.read` is the one seam: tests replace it."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from chantier import __version__, connectors
from chantier.board.projects import project_name
from chantier.connectors.base import OPTIONAL_FACTS
from chantier.core import clock
from chantier.core.errors import ChantierError
from chantier.core.repo import Repo, surface_projects
from chantier.hub import interests, journal, state, waits
from chantier.hub import times as hub_times


class Hub:
    """What the surface server does as the hub, the hub lock held (`loop.py`; no other process
    takes that lock, a watcher included): its cycle and its `hub` entry. An entry that cannot be
    written is written again at the next cycle; the lock is kept."""

    def __init__(self, repo: Repo, version: str = __version__) -> None:
        self.repo = repo
        self.git_dir: Path = repo.git_dir
        self.record = state.hub_record(version)
        self.last: float | None = None  # the monotonic time of the last cycle
        self._repos: dict[str, Repo] = {}
        self.publish()

    def publish(self) -> None:
        """Write the `hub` entry; a failed write is left to the next cycle."""
        with contextlib.suppress(OSError):
            state.write_hub(self.git_dir, self.record)

    def set_idle(self, idle: bool) -> None:
        """No client observes (`idle`): the entry says so once, and the next cycle comes at once
        when one does."""
        if idle and not self.record.get("idle"):
            self.record["idle"] = True
            self.last = None
            self.publish()

    def due(self, now: float) -> bool:
        return self.last is None or now - self.last >= hub_times.cycle_s()

    def projects(self) -> list[Repo]:
        """Every project of the surface, read again at each cycle (a project is built once: it
        costs two git calls); the one project of a repository."""
        if not self.repo.external:
            return [self.repo]
        root = self.repo.surface_root
        found = {}
        for name in surface_projects(root):
            if name not in self._repos:
                self._repos[name] = Repo._external(root, str(root / "projects" / name))
            found[name] = self._repos[name]
        return list(found.values())

    def cycle(self, now: float) -> None:
        """One cycle: each project in turn; a forge error goes in the `hub` entry and the cycle goes
        on. An event its type's model refuses (from what the forge returned) is set aside, the
        others are written, and the entry's `error` is `skipped: <message>` beside its `read_at`."""
        self.last = now
        self.record.pop("idle", None)
        for repo in self.projects():
            self._project(repo)
        self.publish()

    def _project(self, repo: Repo) -> None:
        """One project: what the registry holds, read in one call, judged by each provider."""
        wanted = interests.collect(repo, kinds={interests.PR})
        name = project_name(repo)
        if not wanted:
            if name in self.record["projects"]:  # no wait is open any more
                self.record["projects"][name]["waits_unseen"] = []
            return
        entry = self.record["projects"].setdefault(
            name, {"read_at": None, "error": None, "error_at": None, "waits_unseen": []}
        )
        links = list(dict.fromkeys(i.ref for i in wanted))
        claimed = [x for x in links if connectors.connector_for(x) is not None]
        left_out = next((x for x in links if x not in claimed), None)
        facts = frozenset().union(*(i.facts for i in wanted)) & OPTIONAL_FACTS
        read: dict[str, Any] = {}
        try:
            if claimed:
                got = connectors.read(claimed, facts)
                read = {x: got[self._number(x)] for x in claimed}
        except (ChantierError, OSError) as e:
            self._fail(entry, str(e))
            return
        if left_out is not None:
            self._fail(entry, connectors.UNCLAIMED.format(link=left_out))
        else:
            entry["error"] = entry["error_at"] = None
        if claimed:
            entry["read_at"] = clock.now()
        events: list[dict[str, Any]] = []
        for provider in interests.PROVIDERS:
            mine = [i for i in wanted if i.provider == provider.name]
            if mine:
                events.extend(provider.judge(repo, mine, read))
        waiting = [i for i in wanted if i.provider == waits.PROVIDER.name]
        entry["waits_unseen"] = waits.unseen(waiting, read)  # replaced at each successful read
        accepted, refused = journal.set_aside(events)
        journal.append(repo, accepted, "hub")
        if refused:
            entry["error"], entry["error_at"] = journal.skipped(refused), clock.now()

    @staticmethod
    def _number(link: str) -> int:
        connector = connectors.connector_for(link)
        assert connector is not None, link
        return connector.number(link)

    @staticmethod
    def _fail(entry: dict[str, Any], text: str) -> None:
        entry["error"] = " ".join(text.split()) or "error"
        entry["error_at"] = clock.now()

    def note_error(self, e: Exception) -> None:
        """A cycle that raised outside a forge read: every project's entry carries the error."""
        for entry in self.record["projects"].values():
            entry["error"] = " ".join(str(e).split()) or type(e).__name__
            entry["error_at"] = clock.now()
        self.publish()

    def close(self) -> None:
        with contextlib.suppress(OSError):  # an entry left behind names a dead process
            state.remove_entry(self.git_dir, state.HUB, self.record["pid"])

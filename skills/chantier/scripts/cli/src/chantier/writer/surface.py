"""The projects of the writer's surface: their locks and the journal lines the writer tells."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from chantier.core.errors import ChantierError
from chantier.core.repo import Repo, surface_projects
from chantier.core.seat import read_seat
from chantier.hub import journal
from chantier.lifecycle.stages import changes_lock


class Surface:
    """What the writer's cycle holds of the surface (a mixin: `Writer` sets these)."""

    root: Path
    projects: dict[str, Repo]
    events: list[tuple[list[Repo], dict[str, Any]]]

    def _projects(self) -> list[Repo]:
        """Every project of the surface, in sorted order, built again at each cycle (the
        `checkout.yml` of a project may change)."""
        found: dict[str, Repo] = {}
        for name in surface_projects(self.root):
            found[name] = Repo._external(self.root, str(self.root / "projects" / name))
        self.projects = found
        return list(found.values())

    @contextlib.contextmanager
    def _locked(self) -> Iterator[None]:
        with contextlib.ExitStack() as stack:
            for repo in self.projects.values():
                stack.enter_context(changes_lock(repo))
            yield

    def _tell(self, event: dict[str, Any], repos: list[Repo] | None = None) -> None:
        """Queue a journal line for these projects, by default those that have a seat."""
        if repos is None:
            repos = [r for r in self.projects.values() if self._seated(r)]
        self.events.append((repos, event))

    @staticmethod
    def _seated(repo: Repo) -> bool:
        try:
            return read_seat(repo) is not None
        except (ChantierError, OSError, ValueError):
            return False

    def _holding(self, files: list[str]) -> list[Repo]:
        """The projects whose folder holds one of these paths (relative to the surface)."""
        return [
            r
            for name, r in self.projects.items()
            if any(f.startswith(f"projects/{name}/") for f in files)
        ]

    def _flush(self) -> None:
        events, self.events = self.events, []
        for repos, event in events:
            for repo in repos:
                with contextlib.suppress(ChantierError, OSError):
                    journal.append(repo, [event], "writer")

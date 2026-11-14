"""The served folder: one project in-project, every project of a planning surface."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path

from chantier.core.errors import ChantierError
from chantier.core.git import git
from chantier.core.repo import Repo, SurfaceChoice, surface_projects


def project_name(repo: Repo) -> str:
    """The project's id: its folder's name under `projects/`, else the repository folder's."""
    return (repo.project_dir or repo.root).name


@dataclass
class Project:
    id: str
    repo: Repo


class Projects:
    """The projects of the served folder, each read through its own `Repo`."""

    def __init__(self, home: Repo, surface: Path | None, others: list[Project]) -> None:
        self.home = home  # the project the start URL opens on: `--project`, else the first
        self.surface = surface  # the surface's root; None in-project
        self._items = {p.id: p for p in [Project(project_name(home), home), *others]}
        self._lock = threading.Lock()

    @property
    def surface_mode(self) -> bool:
        return self.surface is not None

    @property
    def home_id(self) -> str:
        return project_name(self.home)

    @property
    def served(self) -> Path:
        """The planning folder in-project, the surface's root on a surface."""
        return (self.surface or self.home.changes).resolve()

    def get(self, project_id: str) -> Project | None:
        return self._items.get(project_id)

    def all(self) -> list[Project]:
        return sorted(self._items.values(), key=lambda p: p.id)

    def refresh(self) -> None:
        """Read the list of projects again when a surface's changes (`Repo._external` runs `git`
        twice per project, so a project already known is kept)."""
        if self.surface is None:
            return
        names = surface_projects(self.surface)
        with self._lock:
            if names == sorted(self._items):
                return
            self._items = {n: self._items.get(n) or _project(n) for n in names}


def _project(name: str) -> Project:
    return Project(name, Repo.find(project=name, readonly=True))


def _surface_root() -> Path:
    cwd = Path(os.environ.get("CHANTIER_ROOT") or os.getcwd())
    common = git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=cwd)
    return Path(common).resolve().parent


def open_projects() -> Projects:
    """The served folder, found as every command finds it (`CHANTIER_ROOT`, the working folder,
    `--project`); a surface with several projects is served whole."""
    try:
        home = Repo.find(readonly=True)
    except SurfaceChoice as e:
        surface = _surface_root()
        first = _project(e.names[0])
        return Projects(first.repo, surface, [_project(n) for n in e.names[1:]])
    if not home.external:
        return Projects(home, None, [])
    surface = home.surface_root
    mine = project_name(home)
    names = [n for n in surface_projects(surface) if n != mine]
    return Projects(home, surface, [_project(n) for n in names])


def check_planning(projects: Projects) -> None:
    if not projects.home.changes.is_dir():
        raise ChantierError(f"no planning folder at {projects.home.changes}")

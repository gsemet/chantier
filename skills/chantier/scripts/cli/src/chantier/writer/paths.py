"""The writer's paths: the pathspec (what it may stage), the checkout folders it leaves out, the
parsing of `git status --porcelain=v1 -z`, the nested repositories and the changes' fingerprint."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from chantier.core.repo import Repo
from chantier.store.base import CONFIG_FILES

PROJECTS = "projects"
GITLINK = "160000"


def _posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def excluded(root: Path, projects: list[Repo]) -> list[str]:
    """The checkout paths of each project (its `repo:` and `worktrees:`, or `core/repo.py`'s
    defaults, as `Repo` resolved them) that fall inside the surface's working tree, relative to
    its root. A path outside it needs no exclusion."""
    root = root.resolve()
    found: set[str] = set()
    for repo in projects:
        for folder in (repo.clone_dir, repo.worktrees_dir):
            if folder is None:
                continue
            place = folder.resolve()
            if place != root and place.is_relative_to(root):
                found.add(_posix(place, root))
    return sorted(found)


@dataclass(frozen=True)
class Paths:
    """What the writer stages: `projects/` and the root configuration files, less the excluded
    checkout folders."""

    exclude: tuple[str, ...]

    @property
    def spec(self) -> list[str]:
        return [PROJECTS, *CONFIG_FILES, *(f":(exclude){e}" for e in self.exclude)]

    def under_exclusion(self, path: str) -> bool:
        path = path.rstrip("/")
        return any(path == e or path.startswith(e + "/") for e in self.exclude)

    def owns(self, path: str) -> bool:
        """Whether the writer stages this path: under `projects/` or a root configuration file,
        and not in an excluded checkout folder."""
        path = path.rstrip("/")
        mine = path in CONFIG_FILES or path.startswith(PROJECTS + "/")
        return mine and not self.under_exclusion(path)


def parse_status(raw: str, paths: Paths) -> tuple[list[str], list[str]]:
    """(changed paths, nested repository paths) of `status --porcelain=v1 -z` output: an untracked
    entry that ends with `/` is a folder git did not enter, a nested repository. A rename or copy
    entry carries its origin as the next field, a path to stage as well."""
    fields = raw.split("\0")
    changed: list[str] = []
    nested: list[str] = []
    i = 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        if len(entry) < 4:  # noqa: PLR2004 (`XY ` and a path)
            continue
        code, path = entry[:2], entry[3:]
        origin = None
        if "R" in code or "C" in code:
            origin = fields[i] if i < len(fields) else None
            i += 1
        if code == "??" and path.endswith("/"):
            if not paths.under_exclusion(path):
                nested.append(path.rstrip("/"))
            continue
        for p in (path, origin):
            if p and not paths.under_exclusion(p) and p not in changed:
                changed.append(p)
    return changed, nested


def gitlinks(raw: str, paths: Paths) -> list[str]:
    """The gitlinks (mode 160000) of `ls-files --stage -z` output outside the excluded folders."""
    found = []
    for entry in raw.split("\0"):
        meta, _, path = entry.partition("\t")
        if meta.startswith(GITLINK) and path and not paths.under_exclusion(path):
            found.append(path)
    return found


def fingerprint(root: Path, changed: list[str]) -> tuple[tuple[str, int, int] | tuple[str], ...]:
    """The changes with each path's size and mtime: it moves when a file is written again."""
    out: list[tuple[str, int, int] | tuple[str]] = []
    for p in sorted(changed):
        try:
            st = os.stat(root / p)
        except OSError:
            out.append((p,))
        else:
            out.append((p, st.st_size, st.st_mtime_ns))
    return tuple(out)


SHOWN = 20  # paths named in a commit message


def message(changed: list[str]) -> str:
    """The commit message: the projects touched, the count and the first paths."""
    names = sorted({p.split("/")[1] if p.startswith("projects/") else p for p in changed})
    more = [f"and {len(changed) - SHOWN} more"] if len(changed) > SHOWN else []
    head = f"chantier: {', '.join(names)}: {len(changed)} files"
    return "\n".join([head, "", *changed[:SHOWN], *more])

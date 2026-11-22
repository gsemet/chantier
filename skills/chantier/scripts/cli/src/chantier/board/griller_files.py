"""What the board's Griller turn does to a CR's folder, read from the disk: the folder's listing
before and after a turn (its `wrote`), where the folder went when another session moved it, and
the cleanup of the files that appeared at its old path. Nothing here writes but `clean`."""

from __future__ import annotations

import os
import re
from pathlib import Path

from chantier.core.repo import Repo
from chantier.lifecycle.stages import PRIORITIES, stage_layout

Listing = dict[str, tuple[int, int]]  # a file's path from the folder, `/`-separated: (size, mtime)


def listing(folder: Path) -> Listing:
    """Each file under `folder`: its relative path, size and modification time (ns)."""
    found: Listing = {}
    for here, _dirs, names in os.walk(folder):
        for name in names:
            path = Path(here) / name
            try:
                st = path.stat()
            except OSError:  # gone since the walk read the folder
                continue
            found[path.relative_to(folder).as_posix()] = (st.st_size, st.st_mtime_ns)
    return found


def changed(before: Listing, after: Listing) -> list[str]:
    """The files added, changed or removed between two listings, sorted."""
    return sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))


def _stages(repo: Repo) -> list[Path]:
    paths = stage_layout(repo)
    return [
        paths["inbox"],
        *(paths["backlog"] / p for p in PRIORITIES),
        paths["ready"],
        paths["pending"],
        paths["actives"],
        paths["done"],
        paths["archives"],
        paths["trash"],
    ]


def _named(name: str, slug: str) -> bool:
    return name == slug or re.fullmatch(rf"\d+-{re.escape(slug)}", name) is not None


def locate(repo: Repo, slug: str) -> list[Path]:
    """Every folder of a CR called `slug` in a stage of the planning folder (a CR of a batch is
    `<id>-<slug>`; an archive holds its CRs one level down)."""
    found: list[Path] = []
    for stage in _stages(repo):
        if not stage.is_dir():
            continue
        for entry in sorted(stage.iterdir()):
            if not entry.is_dir():
                continue
            if _named(entry.name, slug):
                found.append(entry)
            elif stage.name == "5-archives":
                found += [c for c in sorted(entry.iterdir()) if c.is_dir() and _named(c.name, slug)]
    return found


def stage_of(repo: Repo, folder: Path) -> str:
    """The stage folder that holds `folder`, as a path from the planning folder."""
    return folder.parent.relative_to(repo.changes.resolve()).as_posix()


def moved_text(repo: Repo, slug: str, elsewhere: list[Path]) -> str:
    """The turn's one line when its CR's folder moved: where it went, found by its slug."""
    where = f"{slug} is now in {stage_of(repo, elsewhere[0])}" if elsewhere else f"{slug} is gone"
    return f"the CR's folder moved during the turn: {where}"


def has_moved(repo: Repo, slug: str, folder: Path, before: Listing, gone_before: bool) -> bool:
    """Whether the CR's folder is no longer at `folder`: the path is gone (a second time running:
    `gone_before`), or holds none of the files the turn started with (a folder made again there)
    while the CR is somewhere else. A path made again with the CR's files in it has not moved."""
    if not folder.is_dir():
        return gone_before
    if not before or set(before) & set(listing(folder)):
        return False
    return any(p != folder for p in locate(repo, slug))


def clean(folder: Path, before: Listing, since_ns: int) -> list[str]:
    """After a move: remove, at the old path, the files that appeared after the turn started (none
    of them the CR's own: those moved), then the folders left empty, the old path included; the
    files it leaves (older than the turn) are returned, relative to the old path."""
    if not folder.is_dir():
        return []
    left: list[str] = []
    for rel, (size, mtime) in sorted(listing(folder).items()):
        if before.get(rel) == (size, mtime) or mtime < since_ns:
            left.append(rel)
        else:
            (folder / rel).unlink(missing_ok=True)
    for here, _dirs, _names in os.walk(folder, topdown=False):
        try:
            Path(here).rmdir()  # only an empty folder goes
        except OSError:
            continue
    return left

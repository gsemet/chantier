"""Arrivals: a CR that ends in `1-inbox` or `2-backlog/P<n>` in a stage it was not in before (the
`arrived@1` lines of `schemas.py`). One pure function, `arrivals`, serves both writers of the line:
the surface's writer (stages read from git's trees, after an integration of the upstream) and the
`file` and `triage` commands (the stage before and after one move).

A CR is identified by its slug (its folder's name). A CR that was in `4-batch`, `5-archives` or
`6-trash` before the change is not an arrival (a restore, the owning Chief of Staff's own doing),
and a CR that ends in `3-ready` or `4-batch` is none either."""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chantier.core.errors import ChantierError
from chantier.core.repo import Repo
from chantier.core.seat import read_seat
from chantier.hub import autostart

INBOX = "1-inbox"
READY = "3-ready"
BACKLOG = "2-backlog"
PRIORITIES = ("P1", "P2", "P3", "P4")
STAGES = (INBOX, *(f"{BACKLOG}/{p}" for p in PRIORITIES), READY)  # the three stages, in order
ELSEWHERE = ("4-batch/1-pending", "4-batch/2-actives", "4-batch/3-done", "5-archives", "6-trash")
ELSEWHERE_ROOTS = ("4-batch", "5-archives", "6-trash")
_STAMP = re.compile(r"^(?:\d{6}-\d{4}-)+")


@dataclass(frozen=True)
class Arrival:
    slug: str
    stage: str  # `1-inbox` or `2-backlog/P<n>`
    was: str | None  # the stage before, None for a new CR

    @property
    def folder(self) -> str:
        return f"{self.stage}/{self.slug}"

    @property
    def before(self) -> str | None:
        return None if self.was is None else f"{self.was}/{self.slug}"


def arriving(stage: str) -> bool:
    """Whether a CR that ends in this stage may be an arrival."""
    return stage == INBOX or stage.startswith(f"{BACKLOG}/")


def arrivals(
    before: Mapping[str, str], after: Mapping[str, str], elsewhere: Collection[str] = ()
) -> list[Arrival]:
    """The arrivals between two maps of slug to stage, in slug order. `elsewhere`: the slugs held
    in `4-batch`, `5-archives` or `6-trash` before the change; a CR of it that is in none of
    `before`'s stages is not new, it is back, and tells nobody."""
    found = []
    for slug in sorted(after):
        stage = after[slug]
        was = before.get(slug)
        if not arriving(stage) or was == stage or (was is None and slug in elsewhere):
            continue
        found.append(Arrival(slug, stage, was))
    return found


def elsewhere_slugs(names: Collection[str]) -> set[str]:
    """The slugs of folder names of `4-batch`, `5-archives` and `6-trash`: the name as it is, the
    name without its stamps, and without its CR number."""
    out: set[str] = set()
    for name in names:
        bare = _STAMP.sub("", name)
        out |= {name, bare, re.sub(r"^(?:CR-)?\d+-", "", bare, flags=re.I)}
    return out


def event(project: str, a: Arrival, via: str, upstream: str | None = None) -> dict[str, Any]:
    """The `arrived@1` event of one arrival."""
    return {
        "type": "arrived@1",
        "project": project,
        "folder": a.folder,
        "stage": a.stage,
        "before": a.before,
        "via": via,
        "upstream": upstream,
    }


def stage_of(repo: Repo, folder: Path) -> str:
    """The stage a CR folder's parent is, relative to the planning folder (`1-inbox`)."""
    return folder.parent.resolve().relative_to(repo.changes.resolve()).as_posix()


def own_session(repo: Repo) -> bool:
    """Whether this CLI run is chantier's own session: the one that holds the project's seat."""
    try:
        seat = read_seat(repo)
    except (ChantierError, OSError, ValueError):
        return False
    return seat is not None and autostart.holds_seat(seat.transcript)

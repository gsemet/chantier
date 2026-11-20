"""The writer's preconditions (the spec's C.6): which one fails, in the order the spec names."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from chantier.autosync import records
from chantier.autosync.site import STATE_FOLDER
from chantier.procs import alive
from chantier.writer import paths as wpaths
from chantier.writer.git_ops import Git

NAMED = 3  # paths named in a blocked text


@dataclass
class Look:
    """What a cycle's reads found."""

    branch: str = ""
    upstream: tuple[str, str] | None = None
    changed: list[str] = field(default_factory=list[str])
    nested: list[str] = field(default_factory=list[str])
    paths: wpaths.Paths = field(default_factory=lambda: wpaths.Paths(()))


def foreign_autosync(git_dir: Path) -> bool:
    """The surface's autosync tool still runs, its watcher alive and its control on."""
    group = records.read_group(git_dir / STATE_FOLDER)
    leader = group.watcher.pid if group.watcher else None
    on = group.control is None or group.control.on
    return bool(group.exists and on and leader is not None and alive(leader))


def blocking(
    g: Git, look: Look, default: str, seen: set[str], foreign: bool
) -> tuple[str, str, list[str]] | None:
    """The first failing precondition as (reason, text, paths), or None."""
    named = sorted(seen)
    found: tuple[str, str, list[str]] | None = None
    if not look.branch or look.branch != default:
        if not default:
            found = (
                "not-a-branch",
                "the default branch cannot be read (origin/HEAD is unset): "
                "run `git remote set-head origin -a` in the surface's checkout",
                [],
            )
        else:
            what = "HEAD is detached" if not look.branch else f"HEAD is on {look.branch}"
            tail = "" if not look.branch else f", not on the default branch {default}"
            found = "not-a-branch", what + tail, []
    elif look.upstream is None:
        found = "no-upstream", f"{look.branch} has no upstream", []
    elif g.busy():
        found = "git-busy", "a rebase, merge, cherry-pick or revert is in progress", []
    elif look.nested:
        found = "nested-repo", look.nested[0], look.nested
    elif seen:
        found = "staged", ", ".join(named[:NAMED]), named
    elif foreign:
        found = "foreign-autosync", "the surface's autosync tool still runs", []
    return found

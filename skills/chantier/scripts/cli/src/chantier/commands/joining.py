"""A prepared CR joins the batch: its folder moves into `1-pending`, its entry is added (or, for
a CR that came back to its own batch, reopened)."""

from __future__ import annotations

import re
from pathlib import Path

from chantier.commands.came_back import came_back, came_back_line, holds, reopen
from chantier.core.batch import Batch, next_cr_number
from chantier.core.clock import now
from chantier.core.records import CrEntry
from chantier.core.repo import Repo
from chantier.lifecycle.filing import slugify
from chantier.lifecycle.stages import ensure_unclaimed, prepared_cr, stage_layout


def new_entry(b: Batch, cr_id: str, title: str, kind: str) -> CrEntry:
    return CrEntry(
        id=cr_id,
        title=title,
        kind=kind,
        status="queued",
        order=max((x.order for x in b.record.crs), default=0) + 1,
        round=0,
        agent=None,
        pr=None,
        branch=f"chantier/{b.id}/{cr_id.lower()}-{slugify(title)}",
        worktree=str(b.repo.worktrees / f"{b.id}-{cr_id}"),
        notes=[],
        updated=now(),
    )


def join_paths(repo: Repo, directories: list[Path]) -> list[Path]:
    """Every published path that joining these prepared folders, in order, touches: each source,
    its target in `1-pending` (numbered as `join_cr` will, one after the other) and the
    `formerly.json` of a CR that came back. Read-only: a command passes it to `check_publish`
    once, before the first move."""
    paths = stage_layout(repo)
    roots = (paths["archives"], paths["trash"], paths["pending"], paths["actives"], paths["done"])
    previous = next_cr_number(repo, roots) - 1
    touched: list[Path] = []
    for directory in directories:
        came = came_back(directory)
        previous = max(previous, int(came.cr[3:])) if came else previous + 1
        number = int(came.cr[3:]) if came else previous
        slug = re.sub(r"^(?:CR-)?\d+-", "", directory.name, flags=re.I)
        cdir = paths["pending"] / f"{number:03d}-{slugify(slug)}"
        touched += [directory, cdir, *([cdir / "formerly.json"] if came else [])]
    return touched


def check_joins(repo: Repo, items: list[str], extra: tuple[Path, ...] = ()) -> None:
    """`check_publish` on every path joining these items touches, before the first move."""
    directories = [prepared_cr(repo, item, stage_layout(repo)).directory for item in items]
    repo.check_publish([*extra, *join_paths(repo, directories)])


def join_cr(b: Batch, item: str, kind: str = "change") -> tuple[CrEntry, str | None]:
    """`add_cr`, and the line a CR that came back (`formerly.json`) adds: it keeps its number,
    and its branch and PR while its branch exists."""
    repo = b.repo
    paths = stage_layout(repo)
    prepared = prepared_cr(repo, item, paths)
    ensure_unclaimed(repo, prepared.directory)
    came = came_back(prepared.directory)
    held = holds(b, came, prepared.directory) if came else None
    if came:
        cr_id, number = came.cr, int(came.cr[3:])
    else:
        number = next_cr_number(
            repo,
            (paths["archives"], paths["trash"], paths["pending"], paths["actives"], paths["done"]),
        )
        cr_id = f"CR-{number}"
    slug = re.sub(r"^(?:CR-)?\d+-", "", prepared.directory.name, flags=re.I)
    cdir = paths["pending"] / f"{number:03d}-{slugify(slug)}"
    origin = repo.rel(prepared.directory)
    b.move(prepared.directory, cdir)
    title = prepared.title
    spec = prepared.specification.relative_to(prepared.directory).as_posix()
    if held is not None:
        reopen(b, held)
        c = held
        b.touch(c, title=title, kind=kind, path=repo.rel(cdir), specification=spec)
    else:
        c = new_entry(b, cr_id, title, kind)
        c.path, c.specification = repo.rel(cdir), spec
        b.record.append("crs", c)
    if not came:
        b.log("add", cr_id, title=title, path=c.path, origin=origin)
        return c, None
    line = came_back_line(b, c, came, title)
    b.consume(cdir / "formerly.json")
    b.log("add", cr_id, title=title, path=c.path, origin=origin, came_back=True)
    return c, line


def add_cr(b: Batch, item: str, kind: str = "change") -> CrEntry:
    """Move a prepared CR into `1-pending` and name its branch and worktree: the Driver creates
    them, on the fresh default branch, as its first step."""
    return join_cr(b, item, kind)[0]

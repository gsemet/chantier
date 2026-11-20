"""A CR taken out of the batch by `order drop`: its folder goes to the trash, the inbox or the
backlog, whole, with its work; the inbox and the backlog keep its number."""

from __future__ import annotations

import json
import re
from pathlib import Path

from chantier.core.batch import RESTORED_NUMBER_FILE, Batch
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.files import write_file
from chantier.core.records import (
    TRASH,
    CrEntry,
    read_restored_number,
    write_restored_number,
)
from chantier.core.repo import Repo
from chantier.lifecycle.stages import (
    PRIORITIES,
    cr_directory,
    cr_slug,
    relocate,
    stage_layout,
    trash_cr,
)


def folder_taken(
    repo: Repo, name: str, batch_crs: list[str], slug: str | None = None
) -> str | None:
    """What already uses the name `name` for a CR folder: a folder of that name in `1-inbox`,
    `2-backlog/P1..P4` or `3-ready`, else a CR of the open batch with the slug (`slug`, else the
    name; `batch_crs` holds the other CRs' slugs); None when it is free."""
    paths = stage_layout(repo)
    taken = [
        paths["inbox"] / name,
        paths["ready"] / name,
        *(paths["backlog"] / p / name for p in PRIORITIES),
    ]
    found = next((t for t in taken if t.exists()), None)
    if found is not None:
        try:
            return found.relative_to(repo.session_root).as_posix()
        except ValueError:
            return found.as_posix()
    return f"a CR of the open batch ({name})" if (slug or name) in batch_crs else None


def remember_cr(repo: Repo, target: Path, cr_id: str, batch_id: str) -> None:
    """Note on the folder what it was, and never give its number again."""
    number = re.fullmatch(r"CR-(\d+)", cr_id)
    if number:  # the number is never given again, even once the batch is closed
        path = repo.changes / RESTORED_NUMBER_FILE
        write_restored_number(path, max(read_restored_number(path), int(number[1])))
    intent = target / "01-intent.md"
    with open(intent if intent.is_file() else target / "notes.md", "a", encoding="utf-8") as f:
        f.write(f"\nformerly {cr_id} of {batch_id}\n")


def move_out_cr(batch: Batch, cr: CrEntry, to: str) -> None:
    """The CR leaves the batch for `1-inbox` or `2-backlog/P<n>` (`to`), whole, with its work and
    without a date: `<number>-<slug>`. `formerly.json` records where it came from, the folder's
    note says it, and its number is reserved. A folder that is not in the batch's `1-pending` or
    `2-actives` (moved before) stays."""
    if not cr.path:
        return
    paths = stage_layout(batch.repo)
    source = cr_directory(batch.repo, cr)
    if source.parent not in (paths["pending"], paths["actives"]):
        return
    target = (
        paths["inbox"] if to == "1-inbox" else paths["backlog"] / to.split("/")[1]
    ) / source.name
    relocate(batch, cr, target)
    write_file(
        target / "formerly.json",
        json.dumps(
            {
                "cr": cr.id,
                "batch": batch.id,
                "branch": cr.branch,
                "worktree": cr.worktree,
                "pr": cr.shown_pr(),
                "pr_draft": cr.pr_draft,
            },
            indent=2,
        )
        + "\n",
    )
    remember_cr(batch.repo, target, cr.id, batch.id)


def check_drop_free(batch: Batch, cr: CrEntry, to: str) -> None:
    """A drop to the inbox or the backlog is refused, before anything changes, when its folder
    name is taken (the same test as `restore`'s)."""
    if to == TRASH or not cr.path:
        return
    name = Path(cr.path).name
    others = [cr_slug(Path(x.path).name) for x in batch.record.crs if x.path and x.id != cr.id]
    clash = folder_taken(batch.repo, name, others, cr_slug(name))
    if clash:
        raise ChantierError(
            f"cannot drop {cr.id} to {to}: the name {name} is already used by {clash}",
            EXIT_PRECONDITION,
        )


def close_pr_clause(batch: Batch, cr: CrEntry) -> str:
    """`; close its PR <link>`: a CR dropped to the trash outside a stack, whose PR the steering
    session closes (the CLI runs no forge command); none in a stack, where the stack driver does,
    nor when the CR has no PR or goes elsewhere."""
    link = cr.shown_pr()
    if cr.left_to != TRASH or batch.record.mode == "stack" or not link:
        return ""
    return f"; close its PR {link}"


def leave_batch(batch: Batch, cr: CrEntry) -> None:
    """The dropped CR's folder goes where `left_to` says, once: to `6-trash` (also for a drop
    an older record holds with no destination), or to the inbox or the backlog."""
    if cr.left_to is None or cr.left_to == TRASH:
        trash_cr(batch, cr)
    else:
        move_out_cr(batch, cr, cr.left_to)

"""A CR taken out of the batch by `order drop`: its folder goes to the trash, the inbox or the
backlog, whole, with its work; the inbox and the backlog keep its number."""

from __future__ import annotations

import json
import re
from pathlib import Path

from chantier.core.batch import RESTORED_NUMBER_FILE, Batch
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.records import (
    TRASH,
    CrEntry,
    read_restored_number,
    restored_bytes,
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
        last = max(read_restored_number(repo.changes / RESTORED_NUMBER_FILE), int(number[1]))
        repo.store.write_bytes(RESTORED_NUMBER_FILE, restored_bytes(last))
    intent = target / "01-intent.md"
    note = intent if intent.is_file() else target / "notes.md"
    old = note.read_bytes() if note.is_file() else None
    line = f"formerly {cr_id} of {batch_id}\n"
    if old is not None:  # appended in the file's own line endings, after a blank line
        crlf = old.count(b"\r\n") * 2 > old.count(b"\n")
        line = ("\n" + line).replace("\n", "\r\n" if crlf else "\n")
    repo.store.write_bytes(repo.rel(note), (old or b"") + line.encode("utf-8"))


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
    batch.repo.check_publish(
        [
            source,
            target,
            target / "formerly.json",
            target / "01-intent.md",
            target / "notes.md",
            batch.repo.changes / RESTORED_NUMBER_FILE,
        ]
    )
    relocate(batch, cr, target)
    batch.repo.store.write_text(
        batch.repo.rel(target / "formerly.json"),
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

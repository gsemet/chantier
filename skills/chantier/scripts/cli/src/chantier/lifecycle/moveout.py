"""A CR taken out of the batch by `order drop`: its folder goes to the trash, the backlog or the
next batch (`3-ready`), whole, with its work; the backlog and `3-ready` keep its number."""

from __future__ import annotations

import json
import re
from pathlib import Path

from chantier.core import leases, waits
from chantier.core.batch import RESTORED_NUMBER_FILE, Batch
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.files import rel_in
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
    found = next((t for t in taken if repo.store.exists(rel_in(repo.store.root, t))), None)
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
        last = max(
            read_restored_number(repo.store, repo.changes / RESTORED_NUMBER_FILE), int(number[1])
        )
        repo.store.write_bytes(RESTORED_NUMBER_FILE, restored_bytes(last))
    store = repo.store
    intent = target / "01-intent.md"
    note = intent if store.is_file(rel_in(store.root, intent)) else target / "notes.md"
    old = (
        store.read_bytes(rel_in(store.root, note))
        if store.is_file(rel_in(store.root, note))
        else None
    )
    line = f"formerly {cr_id} of {batch_id}\n"
    if old is not None:  # appended in the file's own line endings, after a blank line
        crlf = old.count(b"\r\n") * 2 > old.count(b"\n")
        line = ("\n" + line).replace("\n", "\r\n" if crlf else "\n")
    repo.store.write_bytes(repo.rel(note), (old or b"") + line.encode("utf-8"))


def _destination(paths: dict[str, Path], to: str) -> Path:
    """The folder `to` names: `3-ready`, `2-backlog/P<n>` or, only for a `left_to` recorded before
    the drop stopped going to the inbox, `1-inbox`."""
    if to == "1-inbox":
        return paths["inbox"]
    if to == "3-ready":
        return paths["ready"]
    return paths["backlog"] / to.split("/")[1]


def move_out_cr(batch: Batch, cr: CrEntry, to: str) -> None:
    """The CR leaves the batch for `3-ready` (the next batch) or `2-backlog/P<n>` (`to`; a `1-inbox`
    an older record holds is still read), whole, with its work and without a date:
    `<number>-<slug>`. `formerly.json` records where it came from, the folder's note says it, and
    its number is reserved; its open waits go to the folder's `waits.json`. A folder that is not in
    the batch's `1-pending` or `2-actives` (moved before) stays."""
    if not cr.path:
        return
    paths = stage_layout(batch.repo)
    source = cr_directory(batch.repo, cr)
    if source.parent not in (paths["pending"], paths["actives"]):
        return
    target = _destination(paths, to) / source.name
    open_waits = waits.open_of(cr.waits)
    batch.repo.check_publish(
        [
            source,
            target,
            target / "formerly.json",
            *([target / waits.FILE] if open_waits else []),
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
                "pr_draft": None if cr.pr_draft is False else cr.pr_draft,
            },
            indent=2,
        )
        + "\n",
    )
    if open_waits:
        batch.repo.store.write_text(
            batch.repo.rel(target / waits.FILE), waits.file_text(open_waits)
        )
    remember_cr(batch.repo, target, cr.id, batch.id)


def check_drop_free(batch: Batch, cr: CrEntry, to: str) -> None:
    """A drop to the backlog or the next batch (`3-ready`) is refused, before anything changes,
    when its folder name is taken (the same test as `restore`'s)."""
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


def pr_clause(batch: Batch, cr: CrEntry) -> str:
    """The PR's clause of a drop outside a stack, which the steering session runs (the CLI closes no
    PR): `; close its PR <link>` for the trash, `; turn its PR to draft <link>` for the
    backlog or `3-ready` when the record says the PR is out of draft. Empty in a stack, where the
    stack driver does it, with no PR, and with the draft state not out of draft."""
    link = cr.shown_pr()
    if batch.record.mode == "stack" or not link:
        return ""
    if cr.left_to == TRASH:
        return f"; close its PR {link}"
    if cr.left_to and cr.pr_draft is False:
        return f"; turn its PR to draft {link}"
    return ""


def leave_batch(batch: Batch, cr: CrEntry) -> None:
    """The dropped CR's folder goes where `left_to` says, once: to `6-trash` (also for a drop
    an older record holds with no destination), or to the backlog or the next batch
    (`3-ready`). The CR's lease ends, live or not confirmed: its old Driver's next command is
    `claim lost`."""
    leases.end(cr.lease)
    if cr.left_to is None or cr.left_to == TRASH:
        trash_cr(batch, cr)
    else:
        move_out_cr(batch, cr, cr.left_to)

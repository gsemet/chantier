"""`order merged`, before its record: check, then stop the CR's running gate and wait for it."""

from __future__ import annotations

import argparse

from chantier.commands.gate_run import stop_and_wait, stopped_line
from chantier.core.batch import Batch, check_epoch, resolve_batch
from chantier.core.errors import ChantierError
from chantier.core.files import LOCK_TIMEOUT_S
from chantier.core.records import BatchRecord, CrEntry
from chantier.core.repo import Repo
from chantier.gate_slots import slot_of
from chantier.lifecycle.session import RenderedBatch
from chantier.lifecycle.stages import changes_lock
from chantier.rails import ENDED
from chantier.stacks import chain

STOP_WAIT_S: float = LOCK_TIMEOUT_S  # how long the order waits for a stopped gate to end


def open_ids(b: Batch, cr_id: str) -> list[str]:
    """The CRs, other than this one and its fixes, neither merged nor cancelled."""
    return [
        x.id for x in b.record.crs if x.id != cr_id and x.kind != "fix" and x.status not in ENDED
    ]


def check_merged(b: Batch, c: CrEntry) -> bool:
    """The refusals of `order merged`, changing nothing; True when the CR is already merged."""
    if c.status == "merged":
        return True
    if c.status == "cancelled":
        raise ChantierError(f"cannot mark cancelled {c.id} merged")
    open_ = open_ids(b, c.id) if c.kind == "release" else []
    if open_:
        raise ChantierError(
            f"order merged: {', '.join(open_)} not merged or cancelled: the release PR merges last"
        )
    return False


def stop_before_merge(repo: Repo, args: argparse.Namespace, actor: str) -> list[str]:
    """Steps 1 and 2 of `order merged <cr>`: under the locks, the order's refusals, changing
    nothing; then, with the locks released (the stopped gate needs the batch lock to log its
    `stopped`), stop the CR's running gate and wait for its command to end, so the folder moves
    with no process on it. Returns the line of the gate it stopped, none when it stopped none."""
    cr_id = args.cr
    with (
        changes_lock(repo),
        RenderedBatch(repo, resolve_batch(repo, args.batch), actor=actor) as b,
    ):
        check_epoch(b, args.epoch)
        if check_merged(b, b.cr(cr_id)):
            return []
    v = slot_of(repo, cr_id)
    if v is None or v.holder is None:
        return []
    s = stop_and_wait(repo.store, v.slot, v.holder, STOP_WAIT_S)
    if s is None:
        return []
    return [stopped_line(cr_id, s.pg)]


def chain_above(d: BatchRecord, c: CrEntry) -> list[str]:
    """Before `order merged <c>`, in a stack batch: the ids of the open CRs above `c` in the chain
    that have a PR, bottom first; [] for a release, a fix, a CR outside the chain or any other
    mode. The CRs that stood on its branch, which a restack owes."""
    if d.mode != "stack" or c.kind in {"release", "fix"}:
        return []
    order = chain(d)
    ids = [x.id for x in order]
    if c.id not in ids:
        return []
    return [x.id for x in order[ids.index(c.id) + 1 :] if x.pr]


def restack_line(d: BatchRecord, cr_id: str, above: list[str]) -> list[str]:
    """The `restack owed:` line of `order merged <cr_id>`, or []: who restacks `above`."""
    if not above:
        return []
    head = f"restack owed: {', '.join(above)} stood on {cr_id}'s branch; "
    if d.stack_agent:
        return [
            head + f"the stack driver {d.stack_agent} restacks them in one pass: "
            f"send it the note `merged: {cr_id}` (`help stack-merge`)"
        ]
    return [
        head + "the stack driver restacks them in one pass: one `take stack --epoch <n>` "
        "once every CR this merge merged is recorded (`help stack-merge`)"
    ]

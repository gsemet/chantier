"""`chantier order drop`: a CR leaves the batch for the trash, the inbox or the backlog."""

from __future__ import annotations

from chantier.commands.orders_word import Word, target
from chantier.core import leases
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.records import LIVE, TRASH, BatchRecord, CrEntry
from chantier.lifecycle.moveout import check_drop_free, close_pr_clause, leave_batch
from chantier.rails import apart, is_parked
from chantier.stack_apart import dependents


def _apart_line(d: BatchRecord, c: CrEntry, to: str | None) -> str:
    """What dropping a held or parked CR says about the CRs that wait with it: none, no stack
    driver is needed; else who takes its commits out of their branches (park-live-Q16)."""
    kind = "parked" if is_parked(c) else "held"
    waiting = dependents(d.crs, c, d.mode)  # worked out while it is still apart
    if not waiting:
        return f"{c.id} was {kind}: no stack driver needed"
    tail = (
        f'the stack driver takes it out of their branches (`take stack --note "drop: {c.id} to '
        f'{to}"`)'
        if d.mode == "stack"
        else "their Drivers rebase to take its commits out "
        f"(the Foreman's note `rebase: {c.id} dropped`)"
    )
    return f"{c.id} was {kind}; waiting with it: {', '.join(x.id for x in waiting)}: {tail}"


def drop(w: Word) -> list[str]:
    """`order drop <cr> --note <folder>`: the CR leaves the batch for `6-trash`, `1-inbox` or
    `2-backlog/P<n>`, its work kept; a live CR only records where, `cancel` moves it."""
    b, c, cr_id, to = w.b, target(w), w.cr_id, w.note
    if c.status == "merged":
        raise ChantierError(f"cannot drop {cr_id}: it is already merged")
    if c.status == "cancelled":
        raise ChantierError(f"{cr_id} is already dropped: {c.path}", EXIT_PRECONDITION)
    if to != TRASH and c.kind in {"release", "fix"}:
        what = "a release CR" if c.kind == "release" else "a fix CR"
        raise ChantierError(
            f"{cr_id} is {what}: it leaves the batch only to the trash (--note trash)",
            EXIT_PRECONDITION,
        )
    check_drop_free(b, c, to)
    out = []
    if apart(c):
        out.append(_apart_line(b.record, c, to))
        c.unset("held")
        c.unset("parked")
    c.left_to = to
    w.clause = close_pr_clause(b, c)
    if c.status in LIVE:
        leases.end(c.lease)  # its old Driver's next command is `claim lost`
        b.touch(c)
        return [
            f"{cr_id} is live: the Foreman stops its Driver, then `chantier cancel {cr_id}`",
            *out,
        ]
    leave_batch(b, c)
    b.touch(c, status="cancelled")
    w.ended = True  # `end_of_batch` pauses the batch, or says what keeps it open
    here = "" if to == TRASH else f" to {to}"
    out.append(f"dropped {cr_id}{here}: {c.path}")
    if w.clause and b.record.steering == "direct":
        out.append(w.clause.removeprefix("; "))
    return out

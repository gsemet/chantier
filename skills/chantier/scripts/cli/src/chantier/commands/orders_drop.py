"""`chantier order drop`: a CR leaves the batch for the trash, the inbox or the backlog."""

from __future__ import annotations

from chantier.commands.orders_word import Word, target
from chantier.core import leases
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.records import LIVE, TRASH
from chantier.lifecycle.moveout import check_drop_free, close_pr_clause, leave_batch
from chantier.rails import all_merged
from chantier.stacks import is_held


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
    if is_held(c):
        c.unset("held")
        out.append(f"{cr_id} was held: no stack driver needed")
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
    w.ended = all_merged(b.record)
    here = "" if to == TRASH else f" to {to}"
    out.append(f"dropped {cr_id}{here}: {c.path}")
    if w.clause and b.record.steering == "direct":
        out.append(w.clause.removeprefix("; "))
    return out

"""`order hold` and `order unhold`: a ready CR kept out of a stack, and put back on top."""

from __future__ import annotations

from chantier.commands.orders_word import Word, target
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.rails import ENDED, is_held
from chantier.stack_apart import leave_stack_starts


def hold(w: Word) -> list[str]:
    """`order hold <cr>`: a ready CR of a stack stays in the batch, outside the stack, until
    `order unhold`."""
    b, c, cr_id = w.b, target(w), w.cr_id
    if b.record.mode != "stack":
        raise ChantierError(
            f"order hold: batch {b.id} is not a stack: only a stack has an order to hold a CR "
            "out of",
            EXIT_PRECONDITION,
        )
    if c.kind in {"release", "fix"}:
        raise ChantierError(
            f"order hold: {cr_id} is {'the release CR' if c.kind == 'release' else 'a fix CR'}: "
            + (
                "the release is the top piece of the stack"
                if c.kind == "release"
                else "a fix already sits outside the stack"
            ),
            EXIT_PRECONDITION,
        )
    if is_held(c):
        raise ChantierError(f"{cr_id} is already held (order {c.held})", EXIT_PRECONDITION)
    if c.status != "ready":
        raise ChantierError(
            f"order hold: {cr_id} is {c.status}; only a CR handed back ready is held out of "
            "the stack",
            EXIT_PRECONDITION,
        )
    waiting = [x.id for x in b.record.crs if x.status not in ENDED and cr_id in x.after]
    if waiting:
        raise ChantierError(
            f"order hold: {waiting[0]} depends on {cr_id}: it cannot stand in the stack without it",
            EXIT_PRECONDITION,
        )
    c.held = w.order_id  # held first, so the shared helper reads it apart
    leave_stack_starts(b, c)
    b.touch(c, held=w.order_id, stacked=False)
    b.log("hold", cr_id, order=w.order_id)
    return [
        f"{cr_id} held out of the stack (order {w.order_id}): the Foreman takes the stack "
        f"driver to take it out of the forge stack; `order unhold {cr_id}` puts it back"
    ]


def unhold(w: Word) -> list[str]:
    """`order unhold <cr>`: the CR is back in the stack, on top (under the release)."""
    b, c, cr_id = w.b, target(w), w.cr_id
    if not is_held(c):
        raise ChantierError(f"order unhold: {cr_id} is not held", EXIT_PRECONDITION)
    c.unset("held")
    b.touch(c, order=max(x.order for x in b.record.crs) + 1)
    b.log("unhold", cr_id, order=w.order_id)
    return [f"{cr_id} back in the stack, on top: the Foreman takes the stack driver to place it"]

"""`order hold` and `order unhold`: a live CR, or a ready CR of a stack, kept out of the slots and
the order, and put back on top."""

from __future__ import annotations

from chantier.commands.orders_word import Word, target
from chantier.commands.park import place_on_top
from chantier.core import leases
from chantier.core.batch import Batch
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.records import CrEntry
from chantier.rails import ENDED, is_held
from chantier.stack_apart import dependents, leave_stack_starts


def _refuse(cr_id: str, text: str) -> ChantierError:
    return ChantierError(f"order hold: {cr_id} {text}", EXIT_PRECONDITION)


def _check_holdable(b: Batch, c: CrEntry, mode: str | None) -> None:
    """The refusals of `order hold`, in order, nothing written: the release or a fix CR, a CR
    already held, the status (a ready CR only in a stack), then a ready CR's dependents."""
    cr_id = c.id
    if c.kind in {"release", "fix"}:
        raise _refuse(
            cr_id,
            f"is {'the release CR' if c.kind == 'release' else 'a fix CR'}: "
            + (
                "the release is the top piece of the stack"
                if c.kind == "release"
                else "a fix already sits outside the stack"
            ),
        )
    if is_held(c):
        raise ChantierError(f"{cr_id} is already held (order {c.held})", EXIT_PRECONDITION)
    if c.status == "ready" and mode != "stack":
        raise _refuse(
            cr_id,
            f"is ready in a {mode} batch: a ready CR holds no slot; only a stack holds a ready "
            "CR out of its order",
        )
    if c.status not in {"working", "ready"}:
        raise _refuse(cr_id, f"is {c.status}; only a live CR, or a ready CR of a stack, is held")
    if c.status == "ready":
        waiting = [x.id for x in b.record.crs if x.status not in ENDED and cr_id in x.after]
        if waiting:
            raise ChantierError(
                f"order hold: {waiting[0]} depends on {cr_id}: it cannot stand in the stack "
                "without it",
                EXIT_PRECONDITION,
            )


def hold(w: Word) -> list[str]:
    """`order hold <cr>`: a live CR in any mode, or a ready CR of a stack, stays in the batch,
    outside the slots and the order, until the user's `order unhold`."""
    b, c, cr_id = w.b, target(w), w.cr_id
    mode = b.record.mode
    _check_holdable(b, c, mode)
    live = c.status == "working"
    agent = c.agent
    if live:
        leases.end(c.lease)  # the old Driver's next leased command is `claim lost`
        b.touch(c, status="blocked", blocked_reason=f"held: order {w.order_id}")
    b.touch(c, held=w.order_id, stacked=False)
    leave_stack_starts(b, c)  # with `held` set: a series successor started on it is a dependent
    b.log("hold", c.id, order=w.order_id, **({"from": "working"} if live else {}))
    if not live:
        return [
            f"{cr_id} held out of the stack (order {w.order_id}): the Foreman takes the stack "
            f"driver to take it out of the forge stack; `order unhold {cr_id}` puts it back"
        ]
    steps = []
    if agent:
        steps.append(f"the Foreman stops its Driver, then `agents set {cr_id} - --epoch <n>`")
    if mode == "stack":
        who = "" if steps else "the Foreman "
        steps.append(f'{who}takes the stack driver (`take stack --note "hold {cr_id}"`)')
    done = f"`order done {w.order_id}`"
    todo = f"{', '.join(steps)} and {done}" if steps else f"the Foreman ends the order: {done}"
    return [
        f"{cr_id} held (order {w.order_id}): it was live; its slot is free: {todo}; "
        f"`order unhold {cr_id}` brings it back"
    ]


def unhold(w: Word) -> list[str]:
    """`order unhold <cr>`: the CR is back, on top (in a series, after the CRs already started),
    its dependents right above it; a CR held while live comes back `blocked`, to be taken back."""
    b, c, cr_id = w.b, target(w), w.cr_id
    if not is_held(c):
        raise ChantierError(f"order unhold: {cr_id} is not held", EXIT_PRECONDITION)
    crs, mode = b.record.crs, b.record.mode
    deps = dependents(crs, c, mode)  # with `held` still set
    c.unset("held")
    place_on_top(b, c, deps)
    b.log("unhold", cr_id, order=w.order_id)
    if c.status != "blocked":
        return [
            f"{cr_id} back in the stack, on top: the Foreman takes the stack driver to place it"
        ]
    b.touch(c, blocked_reason=f"unheld: order {w.order_id}")
    where = "back in the series after its started CRs" if mode == "series" else "back on top"
    then = ", then the stack driver places it" if mode == "stack" else ""
    above = [x.id for x in sorted(deps, key=lambda x: x.order)]
    tail = f"; its dependents above it: {', '.join(above)}" if above else ""
    return [
        f"{cr_id} unheld (order {w.order_id}): {where}; the Foreman takes it back before any "
        f'queued CR (`take {cr_id} --note "unhold: {w.order_id}" --epoch <n>`){then}{tail}'
    ]

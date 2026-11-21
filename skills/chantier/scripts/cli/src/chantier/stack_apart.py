"""A CR held or parked out of the stack: the refusals, its dependents, the lines `status` prints.

Read by the stack's readers (`stacks`) and by the commands, so it lives beside them."""

from __future__ import annotations

from typing import TYPE_CHECKING

from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.records import BatchRecord, CrEntry
from chantier.core.waits import hhmm, open_counted, what
from chantier.rails import ENDED, apart, apart_owner, is_parked, out_of_order

if TYPE_CHECKING:
    from chantier.core.batch import Batch


def refuse_parked_waiting(c: CrEntry) -> None:
    """`take <cr>` of a parked CR while a wait is open: refused, its wait is cleared first."""
    if is_parked(c) and (mine := open_counted(c)):
        raise ChantierError(
            f"{c.id} is parked, waiting for {'; '.join(what(w) for w in mine)}: "
            f"`wait {c.id} clear {mine[0]['id']} --epoch <n>` first",
            EXIT_PRECONDITION,
        )


def refuse_out_of_stack(d: BatchRecord, c: CrEntry) -> None:
    """`stack <crs>` and `stack --out-of-draft` of a parked CR, or of a dependent of a held or
    parked one: refused, it stays out of the stack until the apart CR is back."""
    if is_parked(c):
        raise ChantierError(
            f"{c.id} is parked out of the stack (since {hhmm(c.parked or '')}): "
            "it comes back with `take`",
            EXIT_PRECONDITION,
        )
    if not apart(c) and out_of_order(d.crs, c, d.mode):
        owner = apart_owner(d.crs, c, d.mode)
        raise ChantierError(
            f"{c.id} waits with {waits_with(d, c)}: it stays out of the stack until "
            f"{owner.id} is back",
            EXIT_PRECONDITION,
        )


def dependents(crs: list[CrEntry], c: CrEntry, mode: str | None) -> list[CrEntry]:
    """The open CRs waiting with the apart CR `c` (their apart owner), in order."""
    return sorted(
        (
            x
            for x in crs
            if x.id != c.id
            and not apart(x)
            and out_of_order(crs, x, mode)
            and apart_owner(crs, x, mode).id == c.id
        ),
        key=lambda x: x.order,
    )


def leave_stack_starts(b: Batch, c: CrEntry) -> None:
    """`c` (held, or parked with `parked` already set) leaves the stack: it starts on the default
    branch, and so does every open CR that started on its branch or on a dependent's, unless it
    is a dependent itself (then its base stays). Shared by `order hold` and `park`."""
    d = b.record
    branches = {c.branch} | {x.branch for x in dependents(d.crs, c, d.mode)}
    for x in d.crs:
        if (
            x.id != c.id
            and x.status not in ENDED
            and x.start_on in branches
            and not out_of_order(d.crs, x, d.mode)
        ):
            x.unset("start_on")
            b.touch(x)
    c.unset("start_on")


def waits_with(d: BatchRecord, c: CrEntry) -> str:
    """`parked <p>` or `held <p> (order <O-n>)`: the apart CR a dependent waits with."""
    owner = apart_owner(d.crs, c, d.mode)
    return f"parked {owner.id}" if is_parked(owner) else f"held {owner.id} (order {owner.held})"


def parked_text(c: CrEntry) -> str:
    """What a parked CR waits for: its open waits, else that they are cleared."""
    mine = open_counted(c)
    return "; ".join(what(w) for w in mine)


def parked_lines(b_data: BatchRecord) -> list[str]:
    """One `status` line per parked CR, in every mode: the cleared ones first, then those that
    still wait, each with the CRs that wait with it."""
    parked = [c for c in sorted(b_data.crs, key=lambda x: x.order) if is_parked(c)]
    cleared, waiting = [], []
    for c in parked:
        deps = dependents(b_data.crs, c, b_data.mode)
        with_it = f"; waiting with it: {', '.join(x.id for x in deps)}" if deps else ""
        if not open_counted(c):
            cleared.append(
                f"parked: {c.id} wait cleared: take it back before any queued CR "
                f'(`take {c.id} --note "wait cleared: <what>" --epoch <n>`)'
            )
            continue
        place = " and the stack" if b_data.mode == "stack" else ""
        waiting.append(
            f"parked: {c.id} since {hhmm(c.parked or '')}, waits for {parked_text(c)}; "
            f"out of the slots{place}{with_it}"
        )
    return [*cleared, *waiting]

"""What the steering session has due, read from the record and the events only: the `state:`
line counts it (`status --since`, the steering watcher). `restack owed` is not a kind yet: it is
not held in the record (`order merged` prints it), and child 12 (`next-advice`) adds it here."""

from __future__ import annotations

from typing import NamedTuple

from chantier.core import leases
from chantier.core.records import BatchRecord, CrEntry, EventRecord, Lease
from chantier.core.repo import Repo
from chantier.rails import held, is_held, is_parked, qa_open, slot_free, waits_all
from chantier.stacks import stack_due


class Due(NamedTuple):
    kind: str
    unit: str
    text: str


def _takes(d: BatchRecord) -> list[Due]:
    """Each queued CR a free slot can take, in `order`, at most one per free slot."""
    if d.status != "running" or d.mode == "stack" or not slot_free(d):
        return []
    free = d.slots - len(held(d))
    takeable = [
        c
        for c in sorted(d.crs, key=lambda c: c.order)
        if c.status == "queued"
        and not waits_all(d.crs, c, d.mode)
        and not is_held(c)
        and not is_parked(c)
    ]
    return [Due("take", c.id, f"take {c.id} (slot free)") for c in takeable[:free]]


def _unasked(d: BatchRecord, c: CrEntry, events: list[EventRecord]) -> bool:
    """A ready CR with no ask after its last hand-back; in a stack batch any ask counts."""
    last = max(
        (n for n, e in enumerate(events) if e.kind == "handback" and e.cr == c.id), default=-1
    )
    stack = d.mode == "stack"
    return not any(e.kind == "ask" and (stack or e.cr == c.id) for e in events[last + 1 :])


def _reclaims(repo: Repo, d: BatchRecord) -> list[Due]:
    units: list[tuple[str, Lease | None]] = [
        (c.id, c.lease) for c in sorted(d.crs, key=lambda c: c.order) if c.status == "working"
    ]
    units.append(("stack", d.stack_lease))
    units += [(o.id, o.lease) for o in qa_open(d)]
    out = []
    for unit, lease in units:
        if lease is not None and (late := leases.not_confirmed(repo, unit, lease)):
            out.append(
                Due(
                    "reclaim",
                    unit,
                    f"{unit}: {late}; {leases.reclaim_command(unit, lease, short=True)}",
                )
            )
    return out


def due(repo: Repo, d: BatchRecord, events: list[EventRecord]) -> list[Due]:
    """The steering session's due items, in order: take, take stack, judge, order, reclaim."""
    out = _takes(d)
    if stack_due(d):
        out.append(Due("take", "stack", "take stack (first stack due)"))
    out += [
        Due("judge", c.id, f"judge {c.id} (handed back, no ask yet)")
        for c in sorted(d.crs, key=lambda c: c.order)
        if c.status == "ready" and _unasked(d, c, events)
    ]
    out += [
        Due("order", o.id, f"order {o.id} {o.kind}{'' if o.cr == '-' else ' ' + o.cr} not done")
        for o in d.orders
        if not o.done
    ]
    return out + _reclaims(repo, d)

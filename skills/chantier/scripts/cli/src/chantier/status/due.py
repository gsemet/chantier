"""What the steering session has due, read from the record and the events only: `next --epoch`
prints it, one `due:` line each, and the `state:` line counts it (`status --since`, the steering
watcher). Advice: a safety step stays its command's refusal, and a live lease is never named."""

from __future__ import annotations

from typing import NamedTuple

from chantier.core import leases
from chantier.core.records import BatchRecord, EventRecord, Lease, OrderRecord
from chantier.core.repo import Repo
from chantier.rails import held, qa_open, slot_free
from chantier.rails_release import STACK_READINESS, readiness_key
from chantier.stack_words import PR_IN_DRAFT, ready_word
from chantier.stacks import chain, stack_due
from chantier.status.words import next_to_start

TAKE_STACK = "`take stack --epoch <n>`"


class Due(NamedTuple):
    kind: str  # take, judge, order, restack, reclaim
    unit: str
    text: str  # the line, without its `due: `


def order_words(o: OrderRecord) -> str:
    """An order as `status` and `next` name it: its id, kind, CR and the note's start."""
    cr = f" {o.cr}" if o.cr != "-" else ""
    return f"{o.id} {o.kind}{cr}{' ' + o.note[:40] if o.note else ''}"


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


def _takes(d: BatchRecord) -> list[Due]:
    """A free slot and the CR `take` gives it first; the batch's first `take stack`."""
    out = []
    first = next_to_start(d) if d.status == "running" and slot_free(d) else None
    if first:
        out.append(
            Due(
                "take",
                first,
                f"a free slot ({len(held(d))} of {d.slots} held): take {first} "
                f"(`take {first} --epoch <n>`)",
            )
        )
    if due := stack_due(d):
        ids = ", ".join(x.id for x in due)
        text = f"take stack now: {ids} ready with a PR, no stack made yet ({TAKE_STACK})"
        out.append(Due("take", "stack", text))
    return out


def _handed_back(events: list[EventRecord], crs: set[str]) -> str:
    """The time of the last ready hand-back of these CRs; empty when none is recorded."""
    return max(
        (e.t for e in events if e.kind == "handback" and e.cr in crs and e.result == "ready"),
        default="",
    )


def _asked(d: BatchRecord, key: tuple[str, str], since: str) -> bool:
    """An ask of this readiness key (read or not) sent at or after `since`."""
    ids = [c.id for c in d.crs]
    return any(
        a.sent is not None and a.sent >= since and readiness_key(a.text, ids) == key for a in d.asks
    )


def _judges(repo: Repo, d: BatchRecord, events: list[EventRecord]) -> list[Due]:
    """Each CR handed back ready with no ask since; in a stack batch the chain as one item."""
    stack = chain(d)
    in_chain = {c.id for c in stack}
    out = []
    for c in sorted(d.crs, key=lambda c: c.order):
        if c.status != "ready" or c.id in in_chain:
            continue
        if not _asked(d, ("cr", c.id), _handed_back(events, {c.id})):
            word = (ready_word(d, c, repo) or PR_IN_DRAFT).replace(" ", "-").lower()
            text = f'{c.id} handed back {word}, no ask yet (`asks "{word} {c.id} …"`)'
            out.append(Due("judge", c.id, text))
    pieces = [c for c in stack if c.kind != "release"]
    if pieces and all(c.status == "ready" for c in pieces):
        ids = {c.id for c in pieces}
        if not _asked(d, ("stack", ""), _handed_back(events, ids)):
            text = (
                f"{', '.join(c.id for c in pieces)} handed back {STACK_READINESS}, no ask yet "
                f'(`asks "{STACK_READINESS} …"`)'
            )
            out.append(Due("judge", "stack", text))
    return out


def _orders(d: BatchRecord) -> list[Due]:
    out = []
    for o in d.orders:
        if o.done:
            continue
        done = f"`order done {o.id} --epoch <n>`"
        how = f"the CLI applied it; {done}" if o.applied else f"pending; do your part, then {done}"
        out.append(Due("order", o.id, f"order {order_words(o)}: {how}"))
    return out


def _restacks(d: BatchRecord, events: list[EventRecord]) -> list[Due]:
    """The open CRs of the chain with a PR whose last `ship` came before the last merge of a CR
    below them: the merge moved their base."""
    order = {c.id: c.order for c in d.crs}
    merges = [
        (i, e.cr)
        for i, e in enumerate(events)
        if e.kind == "order" and e.order_kind == "merged" and e.cr in order
    ]
    owed: list[str] = []
    by = ""
    for c in chain(d):
        below = [(i, cr) for i, cr in merges if c.kind == "release" or order[cr] < c.order]
        ships = [i for i, e in enumerate(events) if e.kind == "ship" and e.cr == c.id]
        shipped = max(ships, default=-1)
        if c.pr and below and shipped < below[-1][0]:
            owed.append(c.id)
            by = max(by, below[-1][1], key=lambda x: order.get(x, -1))
    return [Due("restack", "stack", x) for x in restack_line(d, by, owed)]


def _reclaims(repo: Repo, d: BatchRecord) -> list[Due]:
    units: list[tuple[str, Lease | None]] = [
        (c.id, c.lease) for c in sorted(d.crs, key=lambda c: c.order) if c.status == "working"
    ]
    if d.stack_agent:
        units.append(("stack", d.stack_lease))
    units += [(o.id, o.lease) for o in qa_open(d)]
    out = []
    for unit, lease in units:
        if lease is not None and (late := leases.not_confirmed(repo, unit, lease)):
            text = (
                f"{unit}: {late}; check with the host that its Driver ended, then "
                f"`{leases.reclaim_command(unit, lease)}`"
            )
            out.append(Due("reclaim", unit, text))
    return out


def due(repo: Repo, d: BatchRecord, events: list[EventRecord]) -> list[Due]:
    """The steering session's due items, in order: a free slot to take (and the first stack), a
    CR handed back with no ask, an order not done, a restack owed, a lease not confirmed. The
    commands carry the batch's own `--epoch`."""
    found = [*_takes(d), *_judges(repo, d, events), *_orders(d), *_restacks(d, events)]
    found += _reclaims(repo, d)
    epoch = f"--epoch {d.foreman_epoch}"
    return [x._replace(text=x.text.replace("--epoch <n>", epoch)) for x in found]

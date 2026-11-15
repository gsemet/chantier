"""`chantier order waive`: a long gate waived, recorded as a fact on each CR it covers."""

from __future__ import annotations

from pathlib import Path

from chantier.core.batch import Batch
from chantier.core.errors import ChantierError
from chantier.core.records import CrEntry, GateWaiver
from chantier.lifecycle.backlog import backlog_folder
from chantier.rails import ENDED
from chantier.stacks import chain, stack_top

USAGE = (
    'order waive stack --note "<the user\'s words>" | order waive <cr> --note '
    '"<the user\'s words>" --follow-up <backlog folder> (--note - withdraws)'
)


def stack_waiver(b: Batch) -> GateWaiver | None:
    """The stack waiver that stands: that of an open CR of the chain, in a stack batch."""
    for x in chain(b.record):
        if x.gate_waiver is not None and x.gate_waiver.scope == "stack":
            return x.gate_waiver
    return None


def waive_stack(b: Batch, note: str, follow_up: str | None, oid: str) -> list[str]:
    """One long gate on the stack's top only: every open CR of the chain but the release and the
    fixes takes the waiver (the top's gate validates it); `note` `-` withdraws it."""
    if b.record.mode != "stack":
        raise ChantierError(
            f"order waive stack: {b.id} is a {b.record.mode} batch, not a stack: one long "
            "gate on the top PR needs a stack (`order waive <cr> --follow-up <folder>` "
            "waives one CR's gate)"
        )
    crs = [x for x in chain(b.record) if x.kind not in {"release", "fix"}]
    if note == "-":
        gone = [x for x in crs if x.gate_waiver and x.gate_waiver.scope == "stack"]
        for x in gone:
            x.unset("gate_waiver")
            b.touch(x)
        return [f"stack waiver withdrawn on {', '.join(x.id for x in gone) or 'no CR'}"]
    if follow_up:
        raise ChantierError("order waive stack: the top's gate validates, no --follow-up")
    covered = [x for x in crs if not (x.gate_waiver and x.gate_waiver.scope == "cr")]
    for x in covered:
        x.gate_waiver = GateWaiver(order=oid, scope="stack", note=note)
        b.touch(x)
    top = stack_top(b.record)
    return [
        f"long gate waived on {', '.join(x.id for x in covered) or 'no CR'} ({oid}): "
        f"validated by the gate of {top.id if top else 'the stack top'}"
    ]


def waive_cr(b: Batch, c: CrEntry, note: str, follow_up: str | None, oid: str) -> list[str]:
    """One CR's long gate, with nothing in the batch to validate it: the backlog folder of the CR
    that runs it on main afterwards is required and must exist; `note` `-` withdraws."""
    if note == "-":
        if c.gate_waiver is not None and c.gate_waiver.scope == "stack":
            raise ChantierError(
                f"order waive {c.id}: its long gate is waived by the stack waiver "
                f"({c.gate_waiver.order}), not by a waiver of its own: withdraw that one for "
                "the whole stack with `order waive stack --note -`"
            )
        c.unset("gate_waiver")
        b.touch(c)
        return [f"{c.id}: long gate waiver withdrawn, it needs its long gate again"]
    if c.kind in {"release", "fix"} or c.status in ENDED:
        raise ChantierError(
            f"order waive: {c.id} is a {c.kind} CR, {c.status}: a waiver covers an open change CR"
        )
    if not follow_up:
        raise ChantierError(
            f"order waive {c.id}: --follow-up <backlog folder> names the CR that runs the long "
            "gate on main afterwards (file it first: `file`)"
        )
    folder = backlog_folder(b.repo, Path(follow_up.replace("\\", "/")).name).name
    c.gate_waiver = GateWaiver(order=oid, scope="cr", note=note, follow_up=folder)
    b.touch(c)
    return [f"{c.id}: long gate waived ({oid}): follow-up {folder}"]

"""The shape of a stack batch: what makes a per-CR ready ask a stack matter (`shape_blockers`),
the next step of its Foreman (`next_step`) and the `status --refresh` line that shows both
(`shape_line`). Read from the record only."""

from __future__ import annotations

from chantier.core.records import BatchRecord, CrEntry
from chantier.plugin_files import skill_dir
from chantier.stacks import FORMING, chain, forming


def shape_blockers(b_data: BatchRecord, cr: str | None = None) -> list[CrEntry]:
    """The CRs that make a per-CR ready ask for `cr` a stack matter, in `chain` order: every CR
    of the chain but `cr` with a PR, and every CR of the chain with `stacked` set (`cr` included).
    A fix CR, a held CR, a merged or a cancelled one is not in the chain, so never listed. With
    `cr=None`, the batch as a whole."""
    return [x for x in chain(b_data) if (x.pr and x.id != cr) or x.stacked]


def next_step(b_data: BatchRecord) -> str:
    """The step a stack batch's Foreman is next due for, as the shape line and the refusal of a
    per-CR ready ask say it."""
    if b_data.stack_agent:
        return "note to the stack driver"
    order = chain(b_data)
    stacked = any(x.stacked for x in order)
    if not stacked and len(forming(b_data)) >= FORMING:
        return "take stack"
    waiting = [
        x
        for x in order
        if x.kind not in {"release", "fix"} and not x.stacked and x.status == "ready" and x.pr
    ]
    if stacked and waiting:
        return "take stack"
    if stacked:
        return "take stack at the next ready CR or merge"
    return f"parallel until {FORMING} ready with a PR"


def shape_line(b_data: BatchRecord) -> list[str]:
    """The `status --refresh` line that shows a stack batch's shape, read from the record only;
    [] for any batch that is not a stack."""
    if b_data.mode != "stack":
        return []
    order = chain(b_data)
    native = [x.id for x in order if x.stacked]
    with_pr = [x for x in order if x.pr]
    if native or len(with_pr) >= FORMING:
        alone = "refused"
    elif with_pr:
        alone = f"allowed for {with_pr[0].id} only"
    else:
        alone = "allowed"
    present = f"present ({', '.join(native)})" if native else "absent"
    rules = f"{skill_dir().as_posix()}/references/foreman-stack.md (reread after a compaction)"
    return [
        f"shape stack: next {next_step(b_data)}; stack driver: {b_data.stack_agent or 'none'}; "
        f"native stack: {present}; alone asks: {alone}; rules: {rules}"
    ]

"""The long gate of a CR as every surface shows it: one `gate` object, one text.

`chantier status`, STATUS.md, STATUS.json, the pane and the web board all read what this builds,
so a CR says the same thing everywhere. The waiver comes from the record (`stacks`), the rest
from the CR's events and the gate lock."""

from __future__ import annotations

import re
from typing import Any

from chantier.commands.crs import carry_at
from chantier.core.heads import gate_passed, same_head
from chantier.core.records import LIVE, BatchRecord, CrEntry, EventRecord
from chantier.core.repo import Repo
from chantier.gate_queue import gate_state
from chantier.stacks import validated_ids, validating_cr, waived_gate

STATES = ("none", "queued", "running", "passed", "carried", "failed", "waived", "exempt")


def pr_number(url: str | None) -> str:
    """`#12` for a PR URL ending in its number, else an empty string."""
    m = re.search(r"(\d+)/?$", url or "")
    return f"#{m[1]}" if m else ""


def _handback(events: list[EventRecord], c: CrEntry) -> EventRecord | None:
    """The CR's last `handback` event that said `ready`."""
    found = [e for e in events if e.cr == c.id and e.kind == "handback" and e.result == "ready"]
    return found[-1] if found else None


def _validator(d: BatchRecord, cr: str | None) -> dict[str, str | None] | None:
    c = next((x for x in d.crs if x.id == cr), None)
    return {"cr": cr, "pr": c.pr if c else None} if cr else None


def gate_text(g: dict[str, Any]) -> str:
    """The words of the "Long gate" column and step, from a `gate` object."""
    state, head = g["state"], g["head"] or ""
    word = {
        "none": "-",
        "queued": "queued",
        "running": "running",
        "passed": f"passed {head}",
        "carried": f"carried from {head}",
        "failed": f"failed {head}",
        "exempt": f"exempt: {g['waiver']}",
    }.get(state, "")
    if state == "waived":
        by, follow = g["validated_by"], g.get("follow_up")
        n = pr_number(by["pr"]) if by else ""
        target = (f"{by['cr']}{' (' + n + ')' if n else ''}") if by else f"follow-up {follow}"
        word = f"waived → {target}" if by or follow else "waived"
    if g["validates"]:
        word = ("" if state == "none" else word + "; ") + f"validates {', '.join(g['validates'])}"
    return word


def step_text(g: dict[str, Any], order: str | None = None) -> str:
    """The CR's "Long gate" step, for a handed-back CR: the waiver with its order, or the pass
    carried over a rebase, or the exemption."""
    if g["state"] == "waived":
        by, follow = g["validated_by"], g.get("follow_up")
        n = pr_number(by["pr"]) if by else ""
        why = (
            f"validated by {by['cr']}{' (' + n + ')' if n else ''}" if by else f"follow-up {follow}"
        )
        return f"waived ({order}): {why}" if order else f"waived: {why}"
    return gate_text({**g, "validates": []})


def event_step(d: BatchRecord, e: EventRecord) -> str | None:
    """What a `handback ready` event says of the long gate, for the CR's "Long gate" step: the
    exemption, the waiver or the carried pass; None when the CR was handed back on a pass."""
    if e.no_gate:
        return f"exempt: {e.no_gate}"
    if e.gate_waiver:
        g = {
            "state": "waived",
            "validated_by": _validator(d, e.validated_by),
            "follow_up": e.follow_up,
        }
        return step_text(g, str(e.gate_waiver))
    return f"carried from {str(e.gate_from)[:7]}" if e.gate_from else None


def gate_view(
    repo: Repo, d: BatchRecord, c: CrEntry, events: list[EventRecord], live: bool = True
) -> dict[str, Any]:
    """The `gate` object of one CR: its state, the head it rests on, the waiver's words, the CR
    whose gate validates it (a covered CR) and the CRs its own validates (a waived stack's top).
    `events` are the batch's (or the CR's); `live` reads the gate lock for queued and running."""
    mine = [e for e in events if e.cr == c.id]
    handed = _handback(mine, c) if c.status in {"ready", "merged"} else None
    w = c.gate_waiver
    g: dict[str, Any] = {
        "state": "none",
        "head": None,
        "waiver": None,
        "validated_by": None,
        "follow_up": None,
        "validates": validated_ids(d, c),
    }
    covered = waived_gate(d, c)
    top = validating_cr(d, c)
    if handed is not None and handed.no_gate is not None:
        g.update(state="exempt", waiver=handed.no_gate)
    elif handed is not None and handed.gate_waiver and (c.status == "merged" or covered is None):
        by = handed.validated_by
        note = handed.waiver_note or (w.note if w else None)
        g.update(state="waived", waiver=note, follow_up=handed.follow_up)
        g["validated_by"] = _validator(d, by)
    elif covered is not None:
        g.update(state="waived", waiver=covered.note, follow_up=covered.follow_up)
        g["validated_by"] = _validator(d, top.id if top else None)
    elif live and c.status in LIVE and (state := gate_state(repo, c.id)):
        g["state"] = "running" if state.startswith("gate running") else "queued"
    elif c.head and gate_passed(mine, c.head):
        g.update(state="passed", head=c.head[:7])
    elif c.head and (carried := carry_at(mine, c.head, "gate_from")):
        g.update(state="carried", head=str(carried.gate_from)[:7])
    elif handed is not None and handed.gate_from:
        g.update(state="carried", head=str(handed.gate_from)[:7])
    elif c.head and any(e.kind == "gate" and same_head(e.head, c.head) for e in mine):
        g.update(state="failed", head=c.head[:7])
    g["text"] = gate_text(g)
    return g

"""The steps of a CR's page: what its log says it went through, then what is still ahead."""

from __future__ import annotations

from typing import Any

from chantier.core.records import BatchRecord, CrEntry, EventRecord
from chantier.status.gate import event_step
from chantier.status.words import ENDED

AHEAD = ("Shipped", "Handed back")


def step_entries(
    e: EventRecord, d: BatchRecord, c: CrEntry, out: list[dict[str, Any]]
) -> list[tuple[str, str, str]]:
    """The steps (name, verdict, note) one event of the log makes."""
    kind, note = e.kind, e.note or ""
    head = (e.head or "")[:7]  # display only
    result = e.result if e.result is not None else ""
    plain = {
        "round": (f"Round {e.round}", "", note),
        "note": ("Note", "", note),
        "gate": ("Long gate", result, head),
        "verdict": ("Verdict", result, head),
        "ship": ("Shipped", "", e.pr if e.pr is not None else ""),
    }
    if kind in plain:
        return [plain[kind]]
    if kind == "handback":
        if result != "ready":
            return [("Blocked", "", note)]
        # handed back with no long gate pass of its own: the exemption, the waiver or the
        # carried pass is shown, in the words of the "Long gate" column
        says = event_step(d, e)
        return [*([("Long gate", says, "")] if says else []), ("Handed back", "", "")]
    merged = kind == "order" and e.order_kind == "merged"
    if merged and not any(s["name"] == "Merged" for s in out):
        return [("Merged", "", c.pr or "")]
    return []


def steps(d: BatchRecord, c: CrEntry, events: list[EventRecord]) -> list[dict[str, Any]]:
    """What the CR went through, from its log, then what is still ahead of it."""
    out: list[dict[str, Any]] = []
    for e in events:
        for name, verdict, note in step_entries(e, d, c, out):
            out.append({"name": name, "done": True, "verdict": verdict, "note": note, "at": e.t})
    if c.status not in ENDED and c.kind != "release":
        seen = {s["name"] for s in out}
        out += [
            {"name": name, "done": False, "verdict": "", "note": "", "at": ""}
            for name in AHEAD
            if name not in seen
        ]
    return out

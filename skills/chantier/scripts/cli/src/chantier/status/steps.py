"""What a CR went through, from its log, then what is still ahead of it."""

from __future__ import annotations

from typing import Any

from chantier.core.records import CrEntry, EventRecord
from chantier.status.words import ENDED

AHEAD = ("Shipped", "Handed back")


def _step_entries(
    e: EventRecord, c: CrEntry, out: list[dict[str, Any]]
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
        # handed back with no long gate: the reason is shown
        waived = [("Long gate", f"waived: {e.no_gate}", "")] if e.no_gate else []
        return [*waived, ("Handed back", "", "")]
    merged = kind == "order" and e.order_kind == "merged"
    if merged and not any(s["name"] == "Merged" for s in out):
        return [("Merged", "", c.pr or "")]
    return []


def steps(c: CrEntry, events: list[EventRecord]) -> list[dict[str, Any]]:
    """What the CR went through, from its log, then what is still ahead of it."""
    out: list[dict[str, Any]] = []
    for e in events:
        for name, verdict, note in _step_entries(e, c, out):
            out.append({"name": name, "done": True, "verdict": verdict, "note": note, "at": e.t})
    if c.status not in ENDED and c.kind != "release":
        seen = {s["name"] for s in out}
        out += [
            {"name": name, "done": False, "verdict": "", "note": "", "at": ""}
            for name in AHEAD
            if name not in seen
        ]
    return out

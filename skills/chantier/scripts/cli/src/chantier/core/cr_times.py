"""When a CR ended, by the one rule the board's times and the close's record share."""

from __future__ import annotations

from typing import Any

from chantier.core.records import CrEntry, EventRecord


def last_event(own: list[EventRecord], kind: str, **where: Any) -> EventRecord | None:
    """The latest event of that kind (with those attributes) among a CR's own events."""
    found = [e for e in own if e.kind == kind and all(getattr(e, k) == v for k, v in where.items())]
    return found[-1] if found else None


def ended(own: list[EventRecord], c: CrEntry) -> str | None:
    """When the CR finished: merged, or cancelled; `None` for any other state."""
    if c.status == "merged":
        if c.merged_at:
            return c.merged_at
        found = [
            e.t
            for e in (
                last_event(own, "handback", result="merged"),
                last_event(own, "order", order_kind="merged"),
            )
            if e
        ]
        return max(found) if found else None
    if c.status == "cancelled":
        found = [
            e.t
            for e in (last_event(own, "cancel"), last_event(own, "order", order_kind="drop"))
            if e
        ]
        return max(found) if found else None
    return None

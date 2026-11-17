"""What stops the automatic pause at a batch's end."""

from __future__ import annotations

from chantier.core.records import BatchRecord


def end_blockers(d: BatchRecord) -> list[str]:
    """What stops the automatic pause: an order the CLI did not apply in full, a stack driver.
    (An order the CLI applied in full does not: the pause ends it.)"""
    pending = [o.id for o in d.orders if not o.done and not o.applied]
    return [
        *([f"orders pending {', '.join(pending)}"] if pending else []),
        *([f"stack driver {d.stack_agent}"] if d.stack_agent else []),
    ]

"""The `state:` line: where the batch stands in one line, for the steering session (the first
line of `status --since`, and the steering watcher's told blocks). It reads only."""

from __future__ import annotations

from collections import Counter

from chantier.core.records import BatchRecord, EventRecord
from chantier.core.repo import Repo
from chantier.rails import held
from chantier.status.due import due

STATE = "state: {batch} {status} e{epoch} | {counts} | slots {held}/{slots} | due {due}"
ORDER = ("working", "ready", "blocked", "queued", "merged", "cancelled")


def counts(d: BatchRecord) -> str:
    """The CRs by record status, known ones first, then the others alphabetically; `no CR`."""
    n = Counter(c.status for c in d.crs)
    keys = [k for k in ORDER if n[k]] + sorted(k for k in n if k not in ORDER)
    return ", ".join(f"{k} {n[k]}" for k in keys) or "no CR"


def state_line(repo: Repo, d: BatchRecord, events: list[EventRecord]) -> str:
    return STATE.format(
        batch=d.id,
        status=d.status,
        epoch=d.foreman_epoch,
        counts=counts(d),
        held=len(held(d)),
        slots=d.slots,
        due=len(due(repo, d, events)),
    )

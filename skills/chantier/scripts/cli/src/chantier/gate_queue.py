"""The long gate's queue: one ticket per waiting gate in `.long-gate.queue/`, named by arrival,
content `<cr> pid <pid>`. The order: the tickets of the CR the user merges next (the batch's
record), then those a marker `first-<ticket name>` moved to the head, then arrival; a ticket
is never rewritten."""

from __future__ import annotations

import contextlib
import re
import time
from pathlib import Path

from chantier import procs
from chantier.core.errors import ChantierError
from chantier.core.records import read_batch_json
from chantier.core.repo import Repo
from chantier.gate_slots import holder_alive, list_slots, mtime
from chantier.stacks import next_merge

QUEUE = ".long-gate.queue"
MARK = "first-"


def read_ticket(p: Path) -> tuple[str, int] | None:
    """The CR and pid a queue ticket names; None if it is gone or stays unreadable. It deletes
    nothing."""
    for _ in range(5):  # the other side may be writing it
        try:
            m = re.fullmatch(r"(\S+) pid (\d+)", p.read_text(encoding="utf-8").strip())
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            m = None
        if m:
            return m[1], int(m[2])
        time.sleep(0.05)
    return None


def ticket_cr(p: Path, drop: bool) -> str | None:
    """The CR of a live ticket. A dead one is deleted when `drop` (a waiting gate does; a reader
    that only looks does not)."""
    t = read_ticket(p)
    if t is None:
        return None
    if procs.alive_since(t[1], mtime(p), True):
        return t[0]
    if drop:
        with contextlib.suppress(OSError):
            p.unlink()
    return None


def next_merge_cr(queue: Path) -> str | None:
    """The CR the user merges next, read from the batch's `batch.json` beside the queue (none in
    a parallel batch, or with no batch). It only reads."""
    path = queue.parent / "4-batch" / "batch.json"
    if not path.is_file():
        return None
    try:
        c = next_merge(read_batch_json(path))
    except ChantierError:
        return None
    return c.id if c else None


def ordered(queue: Path, drop: bool = False) -> list[Path]:
    """The tickets in queue order: those of the next merge, then the marked ones, then arrival.
    A marker whose ticket is gone is ignored, and deleted when `drop`."""
    tickets = sorted(queue.glob("[0-9]*"))
    marks = {p.name for p in queue.glob(f"{MARK}*")}
    if drop:
        names = {t.name for t in tickets}
        for m in marks:
            if m[len(MARK) :] not in names:
                (queue / m).unlink(missing_ok=True)
    nxt = next_merge_cr(queue)

    def is_next(p: Path) -> bool:
        t = read_ticket(p) if nxt else None
        return t is not None and t[0] == nxt

    return sorted(tickets, key=lambda p: (not is_next(p), f"{MARK}{p.name}" not in marks, p.name))


def queued_crs(repo: Repo) -> list[str]:
    """The CRs of the live tickets, in queue order. It only reads: `status` must not change the
    queue."""
    crs = (ticket_cr(p, False) for p in ordered(repo.changes / QUEUE))
    return [cr for cr in crs if cr is not None]


def move_first(repo: Repo, cr: str) -> list[str] | None:
    """Put each live ticket of `cr` at the head. The CRs that were ahead of the first one (empty
    when it was first), or None when no live ticket names `cr`."""
    queue = repo.changes / QUEUE
    live = [(p, ticket_cr(p, False)) for p in ordered(queue)]
    mine = [p for p, c in live if c == cr]
    if not mine:
        return None
    ahead = [c for p, c in live[: live.index((mine[0], cr))] if c and c != cr]
    for p in mine:
        (queue / f"{MARK}{p.name}").touch()
    return ahead


def gate_state(repo: Repo, cr: str) -> str | None:
    """`gate running` when a slot names the CR and its command or suite still lives;
    `gate queued behind <crs>` (the live holders, else the first ticket; bare `gate queued` when
    it is next) for a live ticket; else None."""
    live = []
    for v in list_slots(repo):
        if v.holder and holder_alive(v.slot.lock, v.holder, True):
            live.append(v.holder.cr)
    if cr in live:
        return "gate running"
    queue = queued_crs(repo)
    if cr not in queue:
        return None
    if live:
        return f"gate queued behind {', '.join(live)}"
    return f"gate queued behind {queue[0]}" if queue.index(cr) else "gate queued"

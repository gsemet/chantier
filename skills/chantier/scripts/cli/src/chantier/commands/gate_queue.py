"""The long gate's queue: one ticket per waiting gate in `.long-gate.queue/`, named by arrival,
content `<cr> pid <pid>`. A marker `first-<ticket name>` puts that ticket at the head; a ticket
is never rewritten."""

from __future__ import annotations

import contextlib
import re
import time
from pathlib import Path

from chantier import procs
from chantier.commands.gate_slots import mtime
from chantier.core.repo import Repo

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


def ordered(queue: Path, drop: bool = False) -> list[Path]:
    """The tickets in queue order: the marked ones first, then arrival. A marker whose ticket is
    gone is ignored, and deleted when `drop`."""
    tickets = sorted(queue.glob("[0-9]*"))
    marks = {p.name for p in queue.glob(f"{MARK}*")}
    if drop:
        names = {t.name for t in tickets}
        for m in marks:
            if m[len(MARK) :] not in names:
                (queue / m).unlink(missing_ok=True)
    return sorted(tickets, key=lambda p: (f"{MARK}{p.name}" not in marks, p.name))


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

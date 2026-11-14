"""The long gate's slots: one lock file per long gate that may run at once, each with its run file
and its stop marker. Slot 1 keeps the names of a single-slot lock."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from chantier import procs
from chantier.core.repo import Repo


class Slot(NamedTuple):
    n: int  # 1 or more
    lock: Path  # byte 0 is the OS lock, the holder's text follows
    run: Path  # the running gate's run file
    stop: Path  # the stopper's marker


def slot(repo: Repo, n: int) -> Slot:
    mid = "" if n == 1 else f".{n}"
    return Slot(
        n,
        repo.changes / f".long-gate{mid}.lock",
        repo.changes / f".long-gate{mid}.run",
        repo.changes / f".long-gate{mid}.stop",
    )


class Holder(NamedTuple):
    cr: str
    pid: int  # the `gate` command
    pg: int | None  # its suite's process group, once started


def parse_holder(text: str) -> Holder | None:
    """The one reading of the lock's text, `<cr> pid <n>[ pg<m>]`; None for any other text."""
    m = re.fullmatch(r"(\S+) pid (\d+)(?: pg(\d+))?", text)
    return Holder(m[1], int(m[2]), int(m[3]) if m[3] else None) if m else None


def mtime(path: Path) -> float:
    """When the file was last written; 0 if it is gone, which no live process predates."""
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def lock_text(path: Path) -> str:
    """Who holds this lock, from its file: `<cr> pid <n> pg<m>`, or empty."""
    try:
        with open(path, encoding="utf-8") as f:
            f.seek(1)  # byte 0 is the lock: Windows refuses to read it
            return f.read().strip()
    except OSError:
        return ""


def holder_alive(lock: Path, h: Holder, unreadable: bool) -> bool:
    """Whether the gate command or its suite named in the lock is still that process: the lock's
    text was written after both existed."""
    recorded = mtime(lock)
    return any(procs.alive_since(p, recorded, unreadable) for p in (h.pid, h.pg) if p is not None)


@dataclass(frozen=True)
class SlotView:
    slot: Slot
    text: str

    @property
    def holder(self) -> Holder | None:
        return parse_holder(self.text)


def list_slots(repo: Repo) -> list[SlotView]:
    """Each existing lock file with its holder text, in slot order. It globs the files: it does
    not need the number of slots, so a stop works whatever the key says now."""
    found = []
    for p in repo.changes.glob(".long-gate*.lock"):
        m = re.fullmatch(r"\.long-gate(?:\.(\d+))?\.lock", p.name)
        if m:
            found.append(int(m[1]) if m[1] else 1)
    return [SlotView(s, lock_text(s.lock)) for s in (slot(repo, n) for n in sorted(found))]


def slot_of(repo: Repo, cr: str) -> SlotView | None:
    """The slot whose holder names this CR."""
    for v in list_slots(repo):
        if v.holder and v.holder.cr == cr:
            return v
    return None


def running_crs(repo: Repo) -> list[str]:
    """The CRs the slots name, in slot order."""
    return [v.holder.cr for v in list_slots(repo) if v.holder]

"""The long gate's lock: first come first served."""

from __future__ import annotations

import contextlib
import os
import re
import time
from pathlib import Path
from typing import NamedTuple

from chantier import procs
from chantier.core.errors import ChantierError
from chantier.core.files import try_lock, unlock
from chantier.core.repo import Repo

LONG_GATE_WAIT_S = 3600


def lock_holder(repo: Repo) -> str:
    """Who holds the long gate, from its lock file: `<cr> pid <n> pg<m>`, or empty."""
    try:
        with open(repo.changes / ".long-gate.lock", encoding="utf-8") as f:
            f.seek(1)  # byte 0 is the lock: Windows refuses to read it
            return f.read().strip()
    except OSError:
        return ""


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


def lock_mtime(repo: Repo) -> float:
    return mtime(repo.changes / ".long-gate.lock")


def holder_alive(repo: Repo, h: Holder, unreadable: bool) -> bool:
    """Whether the gate command or its suite named in the lock is still that process: the lock's
    text was written after both existed."""
    recorded = lock_mtime(repo)
    return any(procs.alive_since(p, recorded, unreadable) for p in (h.pid, h.pg) if p is not None)


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


def queued_crs(repo: Repo) -> list[str]:
    """The CRs of the live tickets, in arrival order. It only reads: `status` must not change the
    queue."""
    out = []
    for p in sorted((repo.changes / ".long-gate.queue").glob("[0-9]*")):
        t = read_ticket(p)
        if t and procs.alive_since(t[1], mtime(p), True):
            out.append(t[0])
    return out


def gate_state(repo: Repo, cr: str) -> str | None:
    """`gate running` when the lock names the CR and its command or suite still lives;
    `gate queued behind <cr>` (bare `gate queued` when it is next) for a live ticket; else None."""
    h = parse_holder(lock_holder(repo))
    live = h if h and holder_alive(repo, h, True) else None
    if live and live.cr == cr:
        return "gate running"
    queue = queued_crs(repo)
    if cr not in queue:
        return None
    if live:
        return f"gate queued behind {live.cr}"
    return f"gate queued behind {queue[0]}" if queue.index(cr) else "gate queued"


class LongGateLock:
    """One long gate at a time in the repository: two full suites at once break each other
    (app windows, ports, shared caches). The lock file names who holds it and the suite's
    process: when the `gate` command dies, the OS frees the lock, but the suite may live on,
    so the next gate waits for that process too."""

    def __init__(self, repo: Repo, cr: str, log: Path):
        self.path = repo.changes / ".long-gate.lock"
        self.repo, self.cr, self.log = repo, cr, log

    def _wait_note(self, holder: str) -> None:
        with open(self.log, "a", encoding="utf-8") as f:
            f.write(f"waiting for the long gate of {holder}\n")

    # The queue: one ticket per waiting gate in `.long-gate.queue/`, named by arrival, content
    # `<cr> pid <pid>`. A gate tries the OS lock only when its ticket is the first live one; a
    # ticket whose pid is gone (a waiting `gate` command that ended) is deleted by whoever reads it.
    def _ticket_cr(self, p: Path) -> str | None:
        t = read_ticket(p)
        if t is None:
            return None
        if procs.alive_since(t[1], mtime(p), True):
            return t[0]
        with contextlib.suppress(OSError):
            p.unlink()
        return None

    def _ahead(self) -> list[str]:
        """The CRs of the live tickets before this gate's own."""
        out = []
        for p in sorted(self.queue.glob("[0-9]*")):
            if p.name >= self.ticket.name:
                break
            cr = self._ticket_cr(p)
            if cr is not None:
                out.append(cr)
        return out

    @staticmethod
    def _key(text: str) -> str:
        """The holder without its suite's `pg<m>`: a gate starting a command is not a new holder."""
        return re.sub(r"\s+pg\d+\b", "", text)

    def __enter__(self) -> LongGateLock:
        self.f = open(self.path, "a+", encoding="utf-8")
        self.queue = self.repo.changes / ".long-gate.queue"
        self.queue.mkdir(exist_ok=True)
        self.ticket = self.queue / f"{time.time_ns():020d}-{os.getpid()}"
        tmp = self.queue / f".{self.ticket.name}.tmp"  # atomic: a reader never sees half a ticket
        tmp.write_text(f"{self.cr} pid {os.getpid()}", encoding="utf-8")
        os.replace(tmp, self.ticket)
        self.locked = False
        try:
            self._acquire()
        except BaseException:
            if self.locked:
                unlock(self.f)
            self.f.close()
            raise
        finally:
            self.ticket.unlink(missing_ok=True)
        return self

    def _acquire(self) -> None:
        since, current, noted = time.monotonic(), None, None
        while True:
            ahead = self._ahead()
            if not ahead and try_lock(self.f):
                self.locked = True
                break
            text = lock_holder(self.repo)
            if self._key(text) and self._key(text) != current:  # a new holder: its hour starts
                current, since = self._key(text), time.monotonic()
            note = (current, tuple(ahead))
            if note != noted:
                noted = note
                queued = f"; queued ahead: {', '.join(ahead)}" if ahead else ""
                self._wait_note(f"{text or 'another CR'}{queued}")
            if time.monotonic() - since > LONG_GATE_WAIT_S and (text or not ahead):
                who = re.fullmatch(r"(\S+) pid (\d+)(?: pg\d+)?", text)
                more = f" and {', '.join(ahead)}" if ahead else ""
                if who:
                    raise ChantierError(
                        f"the long gate of {who[1]} (pid {who[2]}) has held the "
                        "lock for over an hour: check it; this gate was queued "
                        f"behind it{more}"
                    )
                raise ChantierError(
                    "the long gate lock has been held for over an hour by a "
                    "process that names no CR: check it"
                )
            time.sleep(1)
        self._wait_suite()
        self.holding(f"{self.cr} pid {os.getpid()}")

    def _wait_suite(self) -> None:
        """A gate that died without cleaning up: its suite may run on, if it is still the process
        the lock named."""
        left = lock_holder(self.repo)
        h, recorded = parse_holder(left), lock_mtime(self.repo)
        if h is None or h.pg is None or not procs.alive_since(h.pg, recorded, True):
            return
        self._wait_note(f"{left} (its command still runs)")
        since = time.monotonic()
        while procs.alive_since(h.pg, recorded, True):
            if time.monotonic() - since > LONG_GATE_WAIT_S:
                raise ChantierError(
                    f"the long gate of {h.cr} has ended but its suite "
                    f"(pg{h.pg}) still runs after an hour: check it"
                )
            time.sleep(1)

    def holding(self, text: str) -> None:
        self.f.seek(0)
        self.f.truncate()
        self.f.write(f" {text}")
        self.f.flush()

    def __exit__(self, *exc: object) -> None:
        try:
            self.holding("")
        finally:
            unlock(self.f)
            self.f.close()

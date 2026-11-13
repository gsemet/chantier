"""The long gate's lock: first come first served."""

from __future__ import annotations

import contextlib
import os
import re
import time
from pathlib import Path

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
        for _ in range(5):  # the other side may be writing it
            try:
                m = re.fullmatch(r"(\S+) pid (\d+)", p.read_text(encoding="utf-8").strip())
            except FileNotFoundError:
                return None
            except (OSError, ValueError):
                m = None
            if m:
                if procs.alive(int(m[2])):
                    return m[1]
                with contextlib.suppress(OSError):
                    p.unlink()
                return None
            time.sleep(0.05)
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

    def __enter__(self):
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
        left = lock_holder(self.repo)  # a gate that died without cleaning up: its suite may run on
        m = re.search(r"\bpg(\d+)\b", left)
        if m and procs.alive(int(m[1])):
            self._wait_note(f"{left} (its command still runs)")
            since = time.monotonic()
            while procs.alive(int(m[1])):
                if time.monotonic() - since > LONG_GATE_WAIT_S:
                    cr = lock_holder(self.repo).split()[0:1] or ["another CR"]
                    raise ChantierError(
                        f"the long gate of {cr[0]} has ended but its suite "
                        f"(pg{m[1]}) still runs after an hour: check it"
                    )
                time.sleep(1)
        self.holding(f"{self.cr} pid {os.getpid()}")

    def holding(self, text: str) -> None:
        self.f.seek(0)
        self.f.truncate()
        self.f.write(f" {text}")
        self.f.flush()

    def __exit__(self, *exc):
        try:
            self.holding("")
        finally:
            unlock(self.f)
            self.f.close()

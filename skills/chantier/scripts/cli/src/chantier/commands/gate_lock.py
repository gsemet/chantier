"""The long gate's lock: first come first served, as many at once as the project allows."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import IO

from chantier import procs
from chantier.commands.gate_queue import MARK, QUEUE, ordered, queued_crs, ticket_cr
from chantier.commands.gate_slots import (
    Slot,
    holder_alive,
    list_slots,
    lock_text,
    mtime,
    parse_holder,
    slot,
)
from chantier.core.errors import ChantierError
from chantier.core.files import try_lock, unlock
from chantier.core.repo import Repo

LONG_GATE_WAIT_S = 3600


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


def _key(text: str) -> str:
    """The holder without its suite's `pg<m>`: a gate starting a command is not a new holder."""
    return re.sub(r"\s+pg\d+\b", "", text)


def _refusal(texts: list[str], ahead: list[str]) -> ChantierError:
    whos = [m for m in (re.fullmatch(r"(\S+) pid (\d+)(?: pg\d+)?", t) for t in texts) if m]
    more = f" and {', '.join(ahead)}" if ahead else ""
    if not whos:
        return ChantierError(
            "the long gate lock has been held for over an hour by a process that names no CR: "
            "check it"
        )
    named = " and ".join(f"{m[1]} (pid {m[2]})" for m in whos)
    one = len(whos) == 1
    return ChantierError(
        f"the long gate{'' if one else 's'} of {named} {'has' if one else 'have'} held the "
        f"lock for over an hour: check {'it' if one else 'them'}; this gate was queued "
        f"behind {'it' if one else 'them'}{more}"
    )


class LongGateLock:
    """As many long gates at once as `chantier.yaml`'s `long_gate.parallel` admits (one by
    default): two full suites at once may break each other (app windows, ports, shared caches),
    unless the project's gate is isolated per worktree. A slot's lock file names who holds it and
    the suite's process: when the `gate` command dies, the OS frees the lock, but the suite may
    live on, so the next gate in that slot waits for that process too."""

    def __init__(self, repo: Repo, cr: str, log: Path, parallel: int = 1):
        self.repo, self.cr, self.log, self.parallel = repo, cr, log, parallel
        self.f: IO[str] | None = None
        self.slot: Slot = slot(repo, 1)

    def _wait_note(self, holder: str) -> None:
        with open(self.log, "a", encoding="utf-8") as f:
            f.write(f"waiting for the long gate of {holder}\n")

    # The queue: a gate tries the OS lock only when its ticket is the first live one; a ticket
    # whose pid is gone (a waiting `gate` command that ended) is deleted by whoever reads it.
    def _ahead(self) -> list[str]:
        """The CRs of the live tickets before this gate's own, in queue order."""
        out = []
        for p in ordered(self.queue, drop=True):
            if p.name == self.ticket.name:
                break
            cr = ticket_cr(p, True)
            if cr is not None:
                out.append(cr)
        return out

    def __enter__(self) -> LongGateLock:
        self.queue = self.repo.changes / QUEUE
        self.queue.mkdir(exist_ok=True)
        self.ticket = self.queue / f"{time.time_ns():020d}-{os.getpid()}"
        tmp = self.queue / f".{self.ticket.name}.tmp"  # atomic: a reader never sees half a ticket
        tmp.write_text(f"{self.cr} pid {os.getpid()}", encoding="utf-8")
        os.replace(tmp, self.ticket)
        try:
            self._acquire()
        except BaseException:
            self._release()
            raise
        finally:
            self.ticket.unlink(missing_ok=True)
            (self.queue / f"{MARK}{self.ticket.name}").unlink(missing_ok=True)
        return self

    def _take(self) -> bool:
        """Try the slots 1 to N in order; the first free one is this gate's."""
        for n in range(1, self.parallel + 1):
            s = slot(self.repo, n)
            f = open(s.lock, "a+", encoding="utf-8")  # noqa: SIM115 - held while the gate runs
            if try_lock(f):
                self.f, self.slot = f, s
                return True
            f.close()
        return False

    def _acquire(self) -> None:
        since, current, noted = time.monotonic(), None, None
        while True:
            ahead = self._ahead()
            if not ahead and self._take():
                break
            texts = [lock_text(slot(self.repo, n).lock) for n in range(1, self.parallel + 1)]
            keys = tuple(_key(t) for t in texts)
            if any(keys) and keys != current:  # a new holder in any slot: its hour starts
                current, since = keys, time.monotonic()
            note = (current, tuple(ahead))
            if note != noted:
                noted = note
                queued = f"; queued ahead: {', '.join(ahead)}" if ahead else ""
                self._wait_note(f"{' and '.join(t for t in texts if t) or 'another CR'}{queued}")
            if time.monotonic() - since > LONG_GATE_WAIT_S and (any(texts) or not ahead):
                raise _refusal(texts, ahead)
            time.sleep(1)
        self._wait_suite()
        self.holding(f"{self.cr} pid {os.getpid()}")

    def _wait_suite(self) -> None:
        """A gate that died without cleaning up: its suite may run on, if it is still the process
        the lock named. Only the slot this gate took counts."""
        left = lock_text(self.slot.lock)
        h, recorded = parse_holder(left), mtime(self.slot.lock)
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
        assert self.f is not None
        self.f.seek(0)
        self.f.truncate()
        self.f.write(f" {text}")
        self.f.flush()

    def _release(self) -> None:
        if self.f is not None:
            unlock(self.f)
            self.f.close()
            self.f = None

    def __exit__(self, *exc: object) -> None:
        try:
            self.holding("")
        finally:
            self._release()

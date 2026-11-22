"""The long gate's run file and its stop, shared by `gate --stop` and `order merged`."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import NamedTuple

from chantier import procs
from chantier.core.batch import Batch
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.records import RunRecord
from chantier.gate_slots import Holder, Slot, mtime
from chantier.store import PlanStore


# A slot's run file (`.long-gate.run` for slot 1, `.long-gate.<k>.run` after; planning folder,
# ignored like the lock) tells a `gate <cr> --stop` what the running gate is (run id, head,
# command, log, suite group) and tells the running gate it was stopped. The ask is a separate
# marker, `.long-gate.stop`, that the stopper creates and the gate never rewrites (the gate
# removes it when it starts and ends), so no write of the run file can lose it: the gate checks
# it before and right after each start, and after each wait, and then records `stopped`, never
# `fail`.
def stop_asked(s: Slot) -> bool:
    return s.stop.exists()


def run_read(s: Slot) -> RunRecord | None:
    for _ in range(5):  # the other side may be writing it
        try:
            return RunRecord.model_validate_json(s.run.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            time.sleep(0.05)
    return None


REPLACE_TRIES = 5


def run_write(s: Slot, record: RunRecord) -> None:
    tmp = s.run.with_name(f"{s.run.name}.tmp")
    tmp.write_text(json.dumps(record.to_data()), encoding="utf-8")
    for i in range(REPLACE_TRIES):  # atomic: the stopper never reads half a file
        try:
            os.replace(tmp, s.run)
            return
        except PermissionError:  # Windows: a reader holds the file
            if i == REPLACE_TRIES - 1:
                raise
            time.sleep(0.05)


class Stopped(NamedTuple):
    head: str
    pg: int | None  # the suite group that was stopped
    acted: bool  # something was stopped or recorded


def ask_stop(store: PlanStore, s: Slot, h: Holder) -> tuple[bool, int | None]:
    """Ask the gate the slot's lock names to stop and stop its suite, each only while it is
    still the process the lock recorded. Returns whether the command lives and the group."""
    recorded = mtime(store, s.lock)
    gate_alive = procs.alive_since(h.pid, recorded, False)
    pg = h.pg if h.pg is not None and procs.alive_since(h.pg, recorded, False) else None
    if gate_alive:
        s.stop.write_text("stop", encoding="utf-8")  # the running gate records it
    if pg is not None:
        procs.stop_group(pg)
    return gate_alive, pg


def stopped_line(cr_id: str, pg: int | None) -> str:
    return f"stopped the long gate of {cr_id}" + (f" (pg{pg})" if pg is not None else "")


def stop_and_wait(store: PlanStore, s: Slot, h: Holder, timeout_s: float) -> Stopped | None:
    """Stop the gate of the slot as `stop_gate` does, then wait for its command to end, so it
    records its own `stopped` with its folder in place. None when it was not running; a gate
    still running at the bound is refused. It logs no event and takes no batch."""
    run = run_read(s)
    gate_alive, pg = ask_stop(store, s, h)
    if not gate_alive:
        return None
    if not procs.wait_gone(h.pid, mtime(store, s.lock), timeout_s):
        raise ChantierError(
            f"order merged {h.cr}: its long gate (pid {h.pid}) did not end within "
            f"{timeout_s:g} s after its stop: nothing recorded; run the order again once it ends",
            EXIT_PRECONDITION,
        )
    return Stopped((run.head if run else ""), pg, True)


def stop_gate(s: Slot, h: Holder, b: Batch, fallback_head: str) -> Stopped:
    """Stop the long gate the slot's lock names (`h`): ask its command to stop and stop its
    suite, each only while it is still the process the lock recorded. The run is recorded
    `stopped`: no pass, no failure. When the command is gone, the stopper records it, in `b`'s
    write. The other slots are not touched."""
    run = run_read(s)
    head = (run.head if run else "") or fallback_head
    gate_alive, pg = ask_stop(b.repo.store, s, h)
    if not gate_alive and run is not None and run.cr == h.cr:  # no run: the lock was stale
        if run.log and Path(run.log).exists():
            with open(run.log, "a", encoding="utf-8") as f:
                f.write(f"result: stopped at {head}: no pass\n")
        on = {"base": run.base} if run.base else {}
        b.log("gate", h.cr, result="stopped", head=head, command=run.command, run=run.run, **on)
        s.run.unlink(missing_ok=True)
        return Stopped(head, pg, True)
    return Stopped(head, pg, gate_alive or pg is not None)

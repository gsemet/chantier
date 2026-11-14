"""The long gate's run file and its stop, shared by `gate --stop` and `order merged`."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import NamedTuple

from chantier import procs
from chantier.commands.gate_slots import Holder, Slot, mtime
from chantier.core.batch import Batch
from chantier.core.records import RunRecord


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


def stop_gate(s: Slot, h: Holder, b: Batch, fallback_head: str) -> Stopped:
    """Stop the long gate the slot's lock names (`h`): ask its command to stop and stop its
    suite, each only while it is still the process the lock recorded. The run is recorded
    `stopped`: no pass, no failure. When the command is gone, the stopper records it, in `b`'s
    write. The other slots are not touched."""
    run = run_read(s)
    head = (run.head if run else "") or fallback_head
    recorded = mtime(s.lock)
    gate_alive = procs.alive_since(h.pid, recorded, False)
    pg = h.pg if h.pg is not None and procs.alive_since(h.pg, recorded, False) else None
    if gate_alive:
        s.stop.write_text("stop", encoding="utf-8")  # the running gate records it
    if pg is not None:
        procs.stop_group(pg)
    if not gate_alive and run is not None and run.cr == h.cr:  # no run: the lock was stale
        if run.log and Path(run.log).exists():
            with open(run.log, "a", encoding="utf-8") as f:
                f.write(f"result: stopped at {head}: no pass\n")
        b.log("gate", h.cr, result="stopped", head=head, command=run.command, run=run.run)
        s.run.unlink(missing_ok=True)
        return Stopped(head, pg, True)
    return Stopped(head, pg, gate_alive or pg is not None)

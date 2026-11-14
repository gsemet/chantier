"""The long gate's run file and its stop, shared by `gate --stop` and `order merged`."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import NamedTuple

from chantier import procs
from chantier.commands.gate_lock import Holder, lock_mtime
from chantier.core.batch import Batch
from chantier.core.records import RunRecord
from chantier.core.repo import Repo


# The run file `.long-gate.run` (planning folder, ignored like the lock) tells a `gate <cr> --stop`
# what the running gate is (run id, head, command, log, suite group) and tells the running gate it
# was stopped. The ask is a separate marker, `.long-gate.stop`, that the stopper creates and the
# gate never rewrites (the gate removes it when it starts and ends), so no write of the run file
# can lose it: the gate checks it before and right after each start, and after each wait, and
# then records `stopped`, never `fail`.
def run_file(repo: Repo) -> Path:
    return repo.changes / ".long-gate.run"


def stop_file(repo: Repo) -> Path:
    return repo.changes / ".long-gate.stop"


def stop_asked(repo: Repo) -> bool:
    return stop_file(repo).exists()


def run_read(repo: Repo) -> RunRecord | None:
    for _ in range(5):  # the other side may be writing it
        try:
            return RunRecord.model_validate_json(run_file(repo).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            time.sleep(0.05)
    return None


REPLACE_TRIES = 5


def run_write(repo: Repo, record: RunRecord) -> None:
    tmp = run_file(repo).with_name(".long-gate.run.tmp")
    tmp.write_text(json.dumps(record.to_data()), encoding="utf-8")
    for i in range(REPLACE_TRIES):  # atomic: the stopper never reads half a file
        try:
            os.replace(tmp, run_file(repo))
            return
        except PermissionError:  # Windows: a reader holds the file
            if i == REPLACE_TRIES - 1:
                raise
            time.sleep(0.05)


class Stopped(NamedTuple):
    head: str
    pg: int | None  # the suite group that was stopped
    acted: bool  # something was stopped or recorded


def stop_gate(repo: Repo, h: Holder, b: Batch, fallback_head: str) -> Stopped:
    """Stop the long gate the lock names (`h`): ask its command to stop and stop its suite, each
    only while it is still the process the lock recorded. The run is recorded `stopped`: no pass,
    no failure. When the command is gone, the stopper records it, in `b`'s write."""
    run = run_read(repo)
    head = (run.head if run else "") or fallback_head
    recorded = lock_mtime(repo)
    gate_alive = procs.alive_since(h.pid, recorded, False)
    pg = h.pg if h.pg is not None and procs.alive_since(h.pg, recorded, False) else None
    if gate_alive:
        stop_file(repo).write_text("stop", encoding="utf-8")  # the running gate records it
    if pg is not None:
        procs.stop_group(pg)
    if not gate_alive and run is not None and run.cr == h.cr:  # no run: the lock was stale
        if run.log and Path(run.log).exists():
            with open(run.log, "a", encoding="utf-8") as f:
                f.write(f"result: stopped at {head}: no pass\n")
        b.log("gate", h.cr, result="stopped", head=head, command=run.command, run=run.run)
        run_file(repo).unlink(missing_ok=True)
        return Stopped(head, pg, True)
    return Stopped(head, pg, gate_alive or pg is not None)

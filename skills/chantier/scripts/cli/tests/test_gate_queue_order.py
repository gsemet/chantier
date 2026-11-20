"""The long gate queue's order: the next merge's tickets, then the moved ones, then arrival."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from chantier.commands.gate_lock import LongGateLock
from chantier.gate_queue import MARK, QUEUE, ordered, ticket_cr

# (label, batch mode, CRs as (id, order, status, kind), tickets by arrival, marked, expected)
ONE, TWO, THREE = "CR-1", "CR-2", "CR-3"
OPEN = [
    (ONE, 1, "working", "change"),
    (TWO, 2, "working", "change"),
    (THREE, 3, "working", "change"),
]
CASES = [
    (
        "stack: the bottom CR first, then the marked, then arrival",
        "stack",
        OPEN,
        [THREE, TWO, ONE],
        [TWO],
        [ONE, TWO, THREE],
    ),
    ("series: the same", "series", OPEN, [TWO, THREE, ONE], [], [ONE, TWO, THREE]),
    (
        "stack: a merged CR is not the next merge",
        "stack",
        [(ONE, 1, "merged", "change"), *OPEN[1:]],
        [THREE, TWO, ONE],
        [],
        [TWO, THREE, ONE],
    ),
    (
        "stack: a cancelled CR is not either",
        "stack",
        [(ONE, 1, "cancelled", "change"), *OPEN[1:]],
        [THREE, TWO],
        [],
        [TWO, THREE],
    ),
    (
        "stack: a fix CR and the release do not count",
        "stack",
        [
            (ONE, 1, "working", "fix"),
            (TWO, 2, "working", "change"),
            (THREE, 9, "working", "release"),
        ],
        [THREE, ONE, TWO],
        [],
        [TWO, THREE, ONE],
    ),
    (
        "parallel: no next merge, the marked first, then arrival",
        "parallel",
        OPEN,
        [THREE, TWO, ONE],
        [ONE],
        [ONE, THREE, TWO],
    ),
    (
        "stack: the marked one of the next merge stays first",
        "stack",
        OPEN,
        [TWO, ONE],
        [TWO],
        [ONE, TWO],
    ),
]


def prepare(
    root: Path, mode: str, crs: list[tuple[str, int, str, str]], arrivals: list[str]
) -> Path:
    """`changes/4-batch/batch.json` and a queue of tickets named by arrival."""
    batch = root / "4-batch"
    batch.mkdir(parents=True)
    rows = [{"id": i, "order": o, "status": s, "kind": k} for i, o, s, k in crs]
    (batch / "batch.json").write_text(json.dumps({"mode": mode, "crs": rows}), encoding="utf-8")
    queue = root / ".long-gate.queue"
    queue.mkdir()
    for n, cr in enumerate(arrivals):
        (queue / f"{n:020d}-1").write_text(f"{cr} pid 1", encoding="utf-8")
    return queue


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_the_queue_runs_the_next_merge_then_the_moved_then_arrival(
    tmp_path: Path, case: tuple[Any, ...]
) -> None:
    label, mode, crs, arrivals, marked, expected = case
    queue = prepare(tmp_path, mode, crs, arrivals)
    for cr in marked:
        ticket = next(p for p in sorted(queue.glob("[0-9]*")) if p.read_text().startswith(cr))
        (queue / f"{MARK}{ticket.name}").touch()
    seen = [p.read_text().split()[0] for p in ordered(queue)]
    assert seen == expected, label


def test_a_queue_with_no_batch_record_keeps_the_marked_then_arrival_order(tmp_path: Path) -> None:
    queue = tmp_path / ".long-gate.queue"
    queue.mkdir()
    for n, cr in enumerate([THREE, TWO, ONE]):
        (queue / f"{n:020d}-1").write_text(f"{cr} pid 1", encoding="utf-8")
    (queue / f"{MARK}{n:020d}-1").touch()
    assert [p.read_text().split()[0] for p in ordered(queue)] == [ONE, THREE, TWO]


def _refuse(real: Any, target: Path | None, times: int) -> Any:
    """`real` (a Path method), refusing with a sharing violation `times` times on `target` (any
    path with `None`); `times < 0`: always."""
    left = [times]

    def wrapper(self: Path, *a: Any, **k: Any) -> Any:
        if (target is None or self == target) and left[0] != 0:
            left[0] -= 1
            raise PermissionError(32, "being used by another process")
        return real(self, *a, **k)

    return wrapper


def test_a_sharing_violation_on_a_ticket_or_a_mark_stops_no_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    # Reader: a ticket that raises on read is gone for the pass, and is not deleted.
    queue = tmp_path / QUEUE
    queue.mkdir()
    a, b = queue / f"{1:020d}-1", queue / f"{2:020d}-1"
    for p, cr in ((a, ONE), (b, TWO)):
        p.write_text(f"{cr} pid {os.getpid()}", encoding="utf-8")
    (queue / f"{MARK}{3:020d}-1").touch()  # an orphan mark
    with monkeypatch.context() as m:
        m.setattr(Path, "read_text", _refuse(Path.read_text, a, -1))
        m.setattr(Path, "unlink", _refuse(Path.unlink, queue / f"{MARK}{3:020d}-1", -1))
        assert ordered(queue, drop=True) == [a, b]
        assert ticket_cr(a, True) is None
        assert ticket_cr(b, True) == TWO
    assert a.exists()
    # Owner: the unlink fails a few times, then goes.
    repo: Any = SimpleNamespace(changes=tmp_path / "owner")
    repo.changes.mkdir()
    log = tmp_path / "gate.log"
    with monkeypatch.context() as m:
        m.setattr(Path, "unlink", _refuse(Path.unlink, None, 3))
        with LongGateLock(repo, ONE, log):
            assert not list((repo.changes / QUEUE).glob("[0-9]*"))
    # Owner: the unlink always fails in `__enter__`; the gate goes on, `__exit__` tries again.
    with monkeypatch.context() as m:
        m.setattr(Path, "unlink", _refuse(Path.unlink, None, -1))
        lock = LongGateLock(repo, ONE, log)
        lock.__enter__()
        assert lock.left
        assert list((repo.changes / QUEUE).glob("[0-9]*"))
    lock.__exit__()
    assert not list((repo.changes / QUEUE).glob("[0-9]*"))

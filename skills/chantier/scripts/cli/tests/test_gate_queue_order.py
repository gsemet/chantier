"""The long gate queue's order: the next merge's tickets, then the moved ones, then arrival."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from chantier.gate_queue import MARK, ordered

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

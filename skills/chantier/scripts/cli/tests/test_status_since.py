"""`status --since <seq>`: only what changed since a line of the batch's `events.jsonl`, merged
and cancelled CRs as counts, the next sequence last, nothing written; plain `status` unchanged;
the due list the `state:` line counts. Prepared records, the CLI called in-process."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from conftest import Chantier

from chantier.core.errors import EXIT_USAGE
from chantier.core.records import BatchRecord, CrEntry, EventRecord, Lease, OrderRecord
from chantier.core.repo import Repo
from chantier.status.due import due
from chantier.status.state_line import STATE, state_line

BATCH = "batch-01"
PAST = "2020-01-01T00:00:00Z"
FUTURE = "2999-01-01T00:00:00Z"
LAST = 6  # the events' last line
CRS: list[dict[str, Any]] = [
    {"id": "CR-1", "order": 1, "status": "working"},
    {"id": "CR-2", "order": 2, "status": "queued"},
    {"id": "CR-3", "order": 3, "status": "ready", "pr": "https://github.com/o/r/pull/3"},
    {"id": "CR-4", "order": 4, "status": "merged"},
]
ORDERS = [
    {"id": "O-1", "kind": "note", "cr": "CR-2", "note": "look"},
    {"id": "O-2", "kind": "merged", "cr": "CR-4", "done": PAST},
]
# line 1: the batch; 2: CR-1; 3: CR-3 back; 4: an order; 5: CR-4 merged; 6: CR-1 again
EVENTS: list[dict[str, Any]] = [
    {"kind": "open"},
    {"kind": "take", "cr": "CR-1"},
    {"kind": "handback", "cr": "CR-3", "result": "ready"},
    {"kind": "order", "order": "O-1"},
    {"kind": "order", "cr": "CR-4", "order": "O-2"},
    {"kind": "round", "cr": "CR-1"},
]


def changes(repo: Path) -> Path:
    return repo / ".agents" / "changes"


def write(
    repo: Path,
    crs: list[dict[str, Any]] | None = None,
    events: Sequence[dict[str, Any] | str] | None = None,
) -> None:
    folder = changes(repo) / "4-batch"
    folder.mkdir(parents=True, exist_ok=True)
    data = {"id": BATCH, "status": "running", "slots": 2, "crs": crs or CRS, "orders": ORDERS}
    (folder / "batch.json").write_text(json.dumps(data), encoding="utf-8")
    lines = [
        e if isinstance(e, str) else json.dumps({"t": PAST, "actor": "driver", **e})
        for e in (EVENTS if events is None else events)
    ]
    (folder / "events.jsonl").write_text("".join(f"{x}\n" for x in lines), encoding="utf-8")


def rows(out: list[str]) -> list[str]:
    return [x.split(" ")[0] for x in out if x.startswith("CR-")]


@pytest.mark.parametrize(
    ("since", "want_rows", "heads"),
    [(0, ["CR-1", "CR-3"], (True, True)), (3, ["CR-1"], (False, True)), (LAST, [], (False, False))],
)
def test_the_listing_holds_only_what_changed_since_the_sequence(
    repo: Path, chantier: Chantier, since: int, want_rows: list[str], heads: tuple[bool, bool]
) -> None:
    batch, order = heads  # the batch's two head lines; the order line
    write(repo)
    code, out, _ = chantier("status", "--since", since)
    assert code == 0 and out[0].startswith(f"state: {BATCH} running e0 | ")
    assert rows(out) == want_rows  # CR-4 changed (line 5) but is merged: no row
    assert any(x.startswith(f"{BATCH} running steering") for x in out) == batch
    assert any(x.startswith("batch: shape") for x in out) == batch
    assert any(x.startswith("orders pending: O-1 note CR-2") for x in out) == order
    assert any(x.startswith("handed back:") for x in out) == ("CR-3" in want_rows)
    assert (f"no change since {since}" in out) == (since == LAST)
    assert out[-1] == f"since {since}, now {LAST}: next time `status --since {LAST}`"


@pytest.mark.parametrize(
    ("merged", "since", "line"),
    [
        (None, 0, "merged: 0 (0 since 0)"),
        (2, 3, "merged: 1 (0 since 3)"),
        (5, 3, "merged: 1 (1 since 3)"),
    ],
)
def test_the_merged_count_is_exact_and_the_cancelled_one_only_above_zero(
    repo: Path, chantier: Chantier, merged: int | None, since: int, line: str
) -> None:
    crs = [{**c, "status": "queued"} if c["id"] == "CR-4" else c for c in CRS]
    events = [*EVENTS[:4], {"kind": "note", "cr": "CR-1"}, EVENTS[5]]  # no merge yet
    if merged is not None:
        crs = [*CRS, {"id": "CR-5", "order": 5, "status": "cancelled"}]
        events[merged - 1] = {"kind": "order", "cr": "CR-4", "order": "O-2"}
    write(repo, crs, events)
    out = chantier("status", "--since", since)[1]
    assert line in out
    cancelled = [x for x in out if x.startswith("cancelled:")]
    assert cancelled == ([] if merged is None else [f"cancelled: 1 (0 since {since})"])


def test_a_half_written_middle_line_counts_in_the_sequence(repo: Path, chantier: Chantier) -> None:
    write(repo, events=[EVENTS[0], '{"t": "half', EVENTS[1]])
    out = chantier("status", "--since", 2)[1]
    assert rows(out) == ["CR-1"] and out[-1].startswith("since 2, now 3:")


@pytest.mark.parametrize(("since", "text"), [(-1, "a sequence is 0 or more"), (7, "stop at 6")])
def test_a_sequence_below_zero_or_past_the_last_line_is_refused(
    repo: Path, chantier: Chantier, since: int, text: str
) -> None:
    write(repo)
    code, out, err = chantier("status", "--since", since)
    assert code == EXIT_USAGE and out == []
    assert f"status --since {since}" in err and text in err


def snapshot(repo: Path) -> dict[str, bytes]:
    return {str(p): p.read_bytes() for p in changes(repo).rglob("*") if p.is_file()}


def test_since_writes_nothing_and_plain_status_is_unchanged(repo: Path, chantier: Chantier) -> None:
    write(repo)
    Repo.find()  # every command's first write, plain `status`'s too: the planning `.gitignore`
    before = snapshot(repo)
    assert chantier("status", "--since", 0)[0] == 0
    assert snapshot(repo) == before  # batch.json, events.jsonl, no arrivals-told.json moved
    out = chantier("status")[1]
    assert not any(x.startswith(("state:", "since ")) for x in out)
    assert rows(out) == ["CR-1", "CR-2", "CR-3", "CR-4"]


def lease(expires: str) -> Lease:
    return Lease(n=1, taken=PAST, renewed=PAST, expires=expires)


def event(kind: str, cr: str) -> EventRecord:
    return EventRecord(t=PAST, actor="driver", kind=kind, cr=cr)


READY = {"status": "ready", "pr": "https://github.com/o/r/pull/1"}
# (the batch's fields, its CRs, the events, the due (kind, unit) list)
DUE: list[Any] = [
    ({}, [{"status": "queued"}], [], [("take", "CR-1")]),
    ({"slots": 1}, [{"status": "queued"}, {"status": "working"}], [], []),
    (
        {"mode": "stack"},
        [READY, READY],
        [],
        [("take", "stack"), ("judge", "CR-1"), ("judge", "CR-2")],
    ),
    ({}, [READY], [event("handback", "CR-1")], [("judge", "CR-1")]),
    ({}, [READY], [event("handback", "CR-1"), event("ask", "CR-1")], []),
    ({"orders": [OrderRecord(id="O-1", kind="note")]}, [], [], [("order", "O-1")]),
    ({}, [{"status": "working", "lease": lease(PAST)}], [], [("reclaim", "CR-1")]),
    ({}, [{"status": "working", "lease": lease(FUTURE)}], [], []),
]


@pytest.mark.parametrize(("fields", "crs", "events", "want"), DUE)
def test_each_due_kind_shows_in_due_and_in_the_state_lines_count(
    repo: Path,
    fields: dict[str, Any],
    crs: list[dict[str, Any]],
    events: list[EventRecord],
    want: list[tuple[str, str]],
) -> None:
    write(repo)
    found = Repo.find()
    entries = [CrEntry(id=f"CR-{n}", order=n, **c) for n, c in enumerate(crs, start=1)]
    d = BatchRecord(**{"id": BATCH, "status": "running", "slots": 2, "crs": entries, **fields})
    items = due(found, d, events)
    assert [(x.kind, x.unit) for x in items] == want
    if want and want[-1][0] == "reclaim":
        assert items[-1].text.endswith("take CR-1 --reclaim ...")
    line = state_line(found, d, events)
    assert line.endswith(f"| due {len(want)}")
    assert line.startswith(STATE.split("{batch}")[0] + BATCH)

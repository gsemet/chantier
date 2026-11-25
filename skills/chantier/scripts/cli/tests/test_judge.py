"""`chantier judge`: the steering session's ask to the user, worded whole from prepared records;
a stack's top, a blocked hand-back and the refusals say why they give no ask; nothing is written
without `--record`; `--record` records what `asks` records, with the one sentence. No git, no
network."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import changes
from conftest import Chantier
from test_ready_line import FROM, HEAD, PASS, REPO, URL, _batch, _cr, _event, _ready

from chantier.core.errors import EXIT_CONFLICT, EXIT_PRECONDITION
from chantier.core.records import EventRecord, OrderRecord
from chantier.status.judge_words import ask_text
from chantier.status.ready_line import gaps, owed

SLUG = "CR-1 the-slug"
WAIT = {"id": "w1", "type": "merge", "ref": "CR-9", "since": "2026-11-15T10:00:00Z"}
ORDER = OrderRecord(id="O-1", kind="note", cr="CR-1")
GAPS = "https://x/1 gaps: no Windows run;\n  the docs   not read"
FAIL = _event(head=HEAD, result="fail", run=1)
BASE = f"ready-to-merge {SLUG} {URL}"
LOCAL = f"{BASE} local gate CR-1 at abc1234"
# (id, the CR's fields, the batch's fields, the events, local_gate, the ask whole)
CASES: list[Any] = [
    ("ready", {}, {}, [PASS], False, BASE),
    (
        "gaps collapsed",
        {},
        {},
        [PASS, _ready(GAPS)],
        False,
        f"{BASE} gaps: no Windows run; the docs not read",
    ),
    (
        "draft",
        {"pr_draft": True},
        {},
        [PASS],
        False,
        f"pr-in-draft {SLUG} {URL} on main: waits for its turn out of draft",
    ),
    ("locally", {"pr": None, "pr_draft": None}, {}, [PASS], False, f"ready-locally {SLUG}"),
    ("exempt", {}, {}, [_ready(no_gate="docs only")], False, f"{BASE} no long gate: docs only"),
    (
        "follow-up",
        {},
        {},
        [_ready(gate_waiver="O-2", follow_up="gate-main")],
        False,
        f"{BASE} long gate waived: follow-up gate-main",
    ),
    (
        "validated",
        {},
        {},
        [_ready(gate_waiver="O-2", validated_by="CR-9")],
        False,
        f"{BASE} long gate waived: validated by CR-9",
    ),
    ("local passed", {}, {}, [PASS], True, f"{LOCAL}: passed"),
    (
        "local carried",
        {},
        {},
        [_ready(gate_from=FROM)],
        True,
        f"{LOCAL}: passed (carried from def5678)",
    ),
    (
        "local failed",
        {},
        {},
        [FAIL],
        True,
        f"{LOCAL}: failed owed before the merge: its long gate passes at abc1234 (the Foreman)",
    ),
    (
        "local not run",
        {},
        {},
        [_ready(no_gate="x")],
        True,
        f"{BASE} no long gate: x local gate CR-1 at abc1234: not run",
    ),
    (
        "local no head",
        {"head": None},
        {},
        [],
        True,
        f"{BASE} local gate CR-1: not run (no head recorded)",
    ),
    (
        "order",
        {},
        {"orders": [ORDER]},
        [PASS],
        False,
        f"{BASE} owed before the merge: O-1 note is applied (the Foreman)",
    ),
    (
        "merge wait",
        {"waits": [WAIT]},
        {},
        [PASS],
        False,
        f"{BASE} do not merge: open waits: w1 merge on CR-9 since 10:00",
    ),
]


@pytest.mark.parametrize(
    ("cr", "batch", "events", "local", "ask"), [c[1:] for c in CASES], ids=[c[0] for c in CASES]
)
def test_the_ask_is_worded_whole_and_drops_no_gap_or_owed_item(
    cr: dict[str, Any], batch: dict[str, Any], events: list[EventRecord], local: bool, ask: str
) -> None:
    d = _batch(_cr(**cr), **batch)
    c = d.crs[0]
    assert ask_text(REPO, d, c, events, set(), local) == ask
    items = [*gaps(events, c).split("; "), *owed(REPO, d, c, events, set())]
    assert all(" ".join(i.split()) in ask for i in items if i)


def test_no_local_gate_clause_without_the_flag() -> None:
    d = _batch(_cr())
    assert "local gate" not in str(ask_text(REPO, d, d.crs[0], [PASS], set(), False))


# the command, on a prepared record


def put(
    repo: Path, crs: list[dict[str, Any]], events: list[dict[str, Any]] | None = None, **kw: Any
) -> None:
    folder = changes(repo) / "4-batch"
    folder.mkdir(parents=True, exist_ok=True)
    rows = [
        {"id": f"CR-{n}", "order": n, "path": f"4-batch/2-actives/{n}-the-slug", **c}
        for n, c in enumerate(crs, start=1)
    ]
    data = {"id": "batch-01", "status": "running", "slots": 4, "foreman_epoch": 1, "crs": rows}
    (folder / "batch.json").write_text(json.dumps({**data, **kw}), encoding="utf-8")
    lines = [
        {"t": "2026-11-15T10:00:00Z", "actor": "driver", "cr": "CR-1", **e} for e in events or []
    ]
    (folder / "events.jsonl").write_text(
        "".join(json.dumps(e) + "\n" for e in lines), encoding="utf-8"
    )


def files(repo: Path) -> tuple[bytes, bytes]:
    folder = changes(repo) / "4-batch"
    return (folder / "batch.json").read_bytes(), (folder / "events.jsonl").read_bytes()


def events_of(repo: Path) -> list[dict[str, Any]]:
    path = changes(repo) / "4-batch" / "events.jsonl"
    return [json.loads(x) for x in path.read_text("utf-8").splitlines()]


def bare(chantier: Chantier, *args: object) -> tuple[int, list[str], str]:
    return chantier.bare(*args)  # type: ignore[attr-defined, no-any-return]


READY = {"status": "ready", "head": HEAD, "pr": URL, "pr_draft": False}
GATE = {"kind": "gate", "head": HEAD, "result": "pass", "run": 1}
HAND = {"kind": "handback", "result": "ready", "note": GAPS}


def test_judge_words_the_ask_and_writes_nothing_without_record(
    repo: Path, chantier: Chantier
) -> None:
    put(repo, [READY], [GATE, HAND])
    before = files(repo)
    code, out, err = bare(chantier, "judge", "CR-1", "--epoch", 1)
    assert code == 0, err
    assert out[0] == f"ask: {BASE} gaps: no Windows run; the docs not read"
    assert out[1].startswith("handed back: ") and out[-1].startswith("decide: ")
    assert "the merge is the user's" in out[-1] and "take CR-1 --note" in out[-1]
    assert files(repo) == before


def test_record_records_the_printed_ask_with_the_sentence_and_clears_the_due_item(
    repo: Path, chantier: Chantier
) -> None:
    old = {"id": "A-1", "text": f"ready-to-merge CR-1 {URL}", "sent": "2020-01-01T00:00:00Z"}
    put(repo, [READY], [GATE, HAND], asks=[old])
    assert any("CR-1 handed back" in x for x in bare(chantier, "next", "--epoch", 1)[1])
    printed = bare(chantier, "judge", "CR-1", "--epoch", 1)[1][0].removeprefix("ask: ")
    code, out, err = bare(chantier, "judge", "CR-1", "--record", "one sentence", "--epoch", 1)
    assert code == 0, err
    assert out[0] == f"[foreman→chief-of-staff] ask A-2: {printed} | note: one sentence"
    assert out[1] == "A-1 superseded by A-2 (marked read)"
    data = json.loads((changes(repo) / "4-batch" / "batch.json").read_text("utf-8"))
    assert data["asks"][-1]["text"] == f"{printed} | note: one sentence"
    assert data["asks"][0]["read"]
    assert any(e["kind"] == "ask" and e["cr"] == "CR-1" for e in events_of(repo))
    assert not any("CR-1 handed back" in x for x in bare(chantier, "next", "--epoch", 1)[1])
    code, out, _ = bare(chantier, "judge", "CR-1", "--record", "--epoch", 1)
    assert out == [
        f"[foreman→chief-of-staff] ask A-3: {printed}",
        "A-2 superseded by A-3 (marked read)",
    ]


def stacked(*status: str) -> list[dict[str, Any]]:
    return [
        {**READY, "status": s, "pr": f"https://github.com/o/r/pull/{n}"}
        for n, s in enumerate(status, start=1)
    ]


def test_a_stacks_top_gets_the_pairs_and_no_record_while_others_are_open(
    repo: Path, chantier: Chantier
) -> None:
    put(repo, stacked("ready", "ready", "ready"), [{**GATE, "cr": "CR-3"}], mode="stack")
    before = files(repo)
    code, out, err = bare(chantier, "judge", "CR-3", "--local-gate", "--epoch", 1)
    assert code == 0, err
    assert out[0].startswith("no ask: CR-3 is in batch-01's stack and not alone (open: CR-1, CR-2)")
    assert "`forge-stack show`" in out[0]
    pull = "https://github.com/o/r/pull"
    assert out[1] == f"for the stack's ask: CR-1={pull}/1 CR-2={pull}/2 CR-3={pull}/3"
    assert out[2] == "local gate CR-3 at abc1234: passed"
    code, out, err = bare(chantier, "judge", "CR-3", "--record", "--epoch", 1)
    assert code == EXIT_PRECONDITION and out == [] and "no ask to record (in the stack)" in err
    assert files(repo) == before


def test_a_stacks_top_alone_gets_a_per_cr_ask_with_the_local_gate(
    repo: Path, chantier: Chantier
) -> None:
    put(repo, stacked("merged", "merged", "ready"), [{**GATE, "cr": "CR-3"}], mode="stack")
    code, out, err = bare(chantier, "judge", "CR-3", "--local-gate", "--epoch", 1)
    assert code == 0, err
    assert out[0].startswith("ask: ready-to-merge CR-3 ")
    assert out[0].endswith(" local gate CR-3 at abc1234: passed")


def test_a_blocked_hand_back_prints_the_facts_and_refuses_record(
    repo: Path, chantier: Chantier
) -> None:
    note = {"kind": "handback", "result": "blocked", "note": "the base moved"}
    put(repo, [{**READY, "status": "blocked"}], [note])
    before = files(repo)
    code, out, err = bare(chantier, "judge", "CR-1", "--epoch", 1)
    assert code == 0, err
    assert out[0].startswith("no ask: CR-1 handed back blocked; taking it back or carrying it")
    assert out[1] == "blocked: the base moved"
    code, out, err = bare(chantier, "judge", "CR-1", "--record", "x", "--epoch", 1)
    assert code == EXIT_PRECONDITION and "no ask to record (blocked)" in err
    assert files(repo) == before


@pytest.mark.parametrize(
    ("args", "code", "text"),
    [
        (("CR-1", "--epoch", 1), EXIT_PRECONDITION, "CR-1 is working, not handed back"),
        (("CR-2", "--epoch", 1), EXIT_PRECONDITION, "CR-2 is queued, not handed back"),
        (("CR-3", "--epoch", 1), EXIT_PRECONDITION, "CR-3 is merged, not handed back"),
        (("CR-4", "--epoch", 1), EXIT_PRECONDITION, "no batch holds CR-4; `status`"),
        (("CR-1",), EXIT_PRECONDITION, "judge CR-1 --epoch <n>"),
        (("CR-1", "--epoch", 7), EXIT_CONFLICT, "stale Foreman: Foreman n°7"),
    ],
)
def test_the_refusals_write_nothing_and_name_a_next_command(
    repo: Path, chantier: Chantier, args: tuple[Any, ...], code: int, text: str
) -> None:
    put(repo, [{"status": "working"}, {"status": "queued"}, {"status": "merged"}])
    before = files(repo)
    got, out, err = bare(chantier, "judge", *args, "--record", "x")
    assert (got, out) == (code, []) and text in err, err
    assert files(repo) == before

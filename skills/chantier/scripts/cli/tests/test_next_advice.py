"""`chantier next` and the `next:` lines: the steering session's due list, a working CR's next step
(the step table walked on injected facts, no git), and the few in-process cases: the refusals,
nothing written, and the `next:` line equal to what `next` prints."""

from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from batch_helpers import changes
from test_leases import Led, leased  # noqa: F401 - the fixture

from chantier.commands import driver_checks, next_lines, orders
from chantier.core.errors import EXIT_CONFLICT, EXIT_PRECONDITION
from chantier.core.records import (
    AskRecord,
    BatchRecord,
    CrEntry,
    EventRecord,
    GateWaiver,
    Lease,
    OrderRecord,
)
from chantier.core.repo import Repo
from chantier.status.advice import Facts, cr_step, driver_step
from chantier.status.due import due

PAST, LATER, FUTURE = "2020-01-01T00:00:00Z", "2020-01-02T00:00:00Z", "2999-01-01T00:00:00Z"
H, OLD = "a" * 40, "b" * 40
PR = "https://github.com/o/r/pull/1"
READY = {"status": "ready", "pr": PR}


def lease(expires: str, n: int = 1) -> Lease:
    return Lease(n=n, taken=PAST, renewed=PAST, expires=expires)


def ev(kind: str, cr: str = "CR-1", **kw: Any) -> EventRecord:
    return EventRecord(t=kw.pop("t", PAST), actor="driver", kind=kind, cr=cr, **kw)


def batch(crs: list[dict[str, Any]], **fields: Any) -> BatchRecord:
    entries = [CrEntry(id=f"CR-{n}", order=n, **c) for n, c in enumerate(crs, start=1)]
    return BatchRecord(
        **{"id": "batch-01", "status": "running", "slots": 2, "foreman_epoch": 3, **fields},
        crs=entries,
    )


TAKE = "a free slot (1 of 2 held): take CR-2 (`take CR-2 --epoch 3`)"
STACK = "take stack now: CR-1, CR-2 ready with a PR, no stack made yet (`take stack --epoch 3`)"
JUDGE = 'CR-1 handed back pr-in-draft, no ask yet (`asks "pr-in-draft CR-1 …"`)'
ORDER = "order O-1 note CR-1 look: "
LATE = "lease not confirmed since"
RESTACK = (
    "restack owed: CR-2 stood on CR-1's branch; the stack driver agent-s restacks them in one "
    "pass: send it the note `merged: CR-1` (`help stack-merge`)"
)
BACK = [ev("handback", result="ready", t=LATER)]
MERGED = [
    ev("ship", "CR-2"),
    ev("order", "CR-1", order_kind="merged"),
]
STACKED = {"mode": "stack", "stack_agent": "agent-s"}
# (id, the batch's CRs, its fields, the events, the due lines' starts, in order)
DUE: list[Any] = [
    ("free slot", [{"status": "working"}, {"status": "queued"}], {}, [], [TAKE]),
    ("all held", [{"status": "working"}, {"status": "working"}], {}, [], []),
    ("take stack", [READY, READY], {"mode": "stack"}, [], [STACK, "CR-1, CR-2 handed back "]),
    ("no ask", [READY], {}, BACK, [JUDGE]),
    (
        "ask after",
        [READY],
        {"asks": [AskRecord(id="A-1", text="pr-in-draft CR-1", sent=FUTURE)]},
        BACK,
        [],
    ),
    (
        "ask before",
        [READY],
        {"asks": [AskRecord(id="A-1", text="pr-in-draft CR-1", sent=PAST)]},
        BACK,
        [JUDGE],
    ),
    (
        "pending",
        [],
        {"orders": [OrderRecord(id="O-1", kind="note", cr="CR-1", note="look")]},
        [],
        [ORDER + "pending; do your part, then `order done O-1 --epoch 3`"],
    ),
    (
        "applied",
        [],
        {"orders": [OrderRecord(id="O-1", kind="note", cr="CR-1", note="look", applied=True)]},
        [],
        [ORDER + "the CLI applied it; `order done O-1 --epoch 3`"],
    ),
    (
        "restack",
        [{"status": "merged"}, {**READY, "stacked": True}],
        STACKED,
        MERGED,
        ["CR-2 handed back ", RESTACK],
    ),
    (
        "restack cleared",
        [{"status": "merged"}, {**READY, "stacked": True}],
        STACKED,
        [*MERGED, ev("ship", "CR-2")],
        ["CR-2 handed back "],
    ),
    (
        "lease CR",
        [{"status": "working", "lease": lease(PAST)}, {"status": "working"}],
        {},
        [],
        [f"CR-1: {LATE}"],
    ),
    (
        "lease stack",
        [{"status": "merged"}],
        {**STACKED, "stack_lease": lease(PAST)},
        [],
        [f"stack: {LATE}"],
    ),
    (
        "lease QA",
        [{"status": "merged"}],
        {"orders": [OrderRecord(id="O-1", kind="qa", lease=lease(PAST))]},
        [],
        ["order O-1 qa: pending", f"O-1: {LATE}"],
    ),
    (
        "live lease",
        [{"status": "working", "lease": lease(FUTURE)}, {"status": "working"}],
        {},
        [],
        [],
    ),
]


@pytest.mark.parametrize(
    ("crs", "fields", "events", "want"), [x[1:] for x in DUE], ids=[x[0] for x in DUE]
)
def test_due_lists_each_kind_in_its_order_with_the_batchs_epoch(
    repo: Path,
    crs: list[dict[str, Any]],
    fields: dict[str, Any],
    events: list[EventRecord],
    want: list[str],
) -> None:
    got = [x.text for x in due(Repo.find(), batch(crs, **fields), events)]
    assert len(got) == len(want), got
    for line, start in zip(got, want, strict=True):
        assert line.startswith(start), line
    assert not any("<n>" in x for x in got)  # the batch's own epoch, always
    if "lease" in " ".join(want):
        assert (
            got[-1].endswith("--epoch 3`")
            and "check with the host that its Driver ended" in got[-1]
        )


WT = "/wt/cr-1"
BASE = {
    "status": "working",
    "round": 1,
    "lease": lease(FUTURE, 2),
    "pr": PR,
    "head": H,
    "branch": "chantier/cr-1",
    "worktree": WT,
}
FACTS = Facts(H, False, H, "origin", ("tests",))
ROUND = ev("round", wt_head=OLD)
GATE = ev("gate", head=H, result="pass")
VERIFIED = ev("verdict", head=H, result="VERIFIED")
NEW = "a new round (`round CR-1 --lease 2`)"
TO_GATE = "`gate CR-1 tests --lease 2`"
# (id, the CR's fields over BASE, the facts' fields over FACTS, the events, the line)
STEPS: list[Any] = [
    ("no round", {"round": 0}, {}, [], "`round CR-1 --lease 2` before the round's Coder"),
    (
        "in round",
        {},
        {},
        [ev("round", wt_head=H)],
        f"the round's Coder, then its reviews; commit in {WT}; then the long gate ({TO_GATE})",
    ),
    (
        "in round no gate",
        {},
        {"gates": ()},
        [ev("round", wt_head=H)],
        f"the round's Coder, then its reviews; commit in {WT}; then the hand-back: chantier.yaml "
        'names no long gate: the hand-back takes --no-gate "<the project\'s rule>"',
    ),
    (
        "dirty",
        {},
        {"dirty": True},
        [ROUND],
        "commit the worktree's changes: a gate, a push and a verdict bind to a commit",
    ),
    ("gate not run", {}, {}, [ROUND], f"the long gate at aaaaaaa: {TO_GATE}, or `--no-gate"),
    (
        "gate failed",
        {},
        {},
        [ROUND, ev("gate", head=H, result="fail")],
        f"the long gate failed at aaaaaaa: fix it in {NEW}",
    ),
    (
        "gates named",
        {},
        {"gates": ("a", "b")},
        [ROUND],
        "the long gate at aaaaaaa: `gate CR-1 <name> --lease 2` (named: a, b), or",
    ),
    (
        "gate carried",
        {},
        {"pushed": ""},
        [ROUND, ev("carry", head=H, gate_from=OLD)],
        "`push CR-1 --lease 2` (origin/chantier/cr-1 is not pushed)",
    ),
    (
        "gate waived",
        {"gate_waiver": GateWaiver(order="O-1", scope="cr")},
        {"pushed": OLD},
        [ROUND],
        "`push CR-1 --lease 2` (origin/chantier/cr-1 is at bbbbbbb)",
    ),
    ("no gate named", {}, {"gates": (), "pushed": ""}, [ROUND], "`push CR-1 --lease 2`"),
    ("no PR", {"pr": None}, {}, [ROUND, GATE], "open the PR, then `ship CR-1 <pr link> --lease 2`"),
    ("old PR head", {"head": OLD}, {}, [ROUND, GATE], f"`ship CR-1 {PR} --lease 2`"),
    ("CI", {}, {}, [ROUND, GATE], f"CI on {PR} at aaaaaaa: green, start the Verifier at aaaaaaa"),
    (
        "Verifier",
        {"phase": "verifier"},
        {},
        [ROUND, GATE],
        'the Verifier\'s `verdict CR-1 VERIFIED` (or "NOT VERIFIED") at aaaaaaa',
    ),
    (
        "NOT VERIFIED",
        {},
        {},
        [ROUND, GATE, ev("verdict", head=H, result="NOT VERIFIED")],
        f"verdict NOT VERIFIED at aaaaaaa: {NEW}",
    ),
    (
        "handback",
        {},
        {},
        [ROUND, GATE, VERIFIED],
        f"`handback CR-1 ready {PR} --lease 2`, then send its line to the Foreman",
    ),
    (
        "handback direct",
        {},
        {"gates": ()},
        [ROUND, VERIFIED],
        f'`handback CR-1 ready {PR} --no-gate "<the project\'s rule>" --lease 2`, then send its '
        "line to the Chief of Staff",
    ),
]


@pytest.mark.parametrize(
    ("cr", "facts", "events", "want"), [x[1:] for x in STEPS], ids=[x[0] for x in STEPS]
)
def test_driver_step_names_the_first_step_not_done(
    cr: dict[str, Any], facts: dict[str, Any], events: list[EventRecord], want: str
) -> None:
    steering = "direct" if "Chief of Staff" in want else "foreman"
    d = batch([{**BASE, **cr}], steering=steering)
    assert driver_step(d, d.crs[0], events, FACTS._replace(**facts)).startswith(want)


@pytest.mark.parametrize(
    ("events", "no_gate"), [([ROUND, GATE, VERIFIED], None), ([ROUND, VERIFIED], "the rule")]
)
def test_the_handback_step_is_one_the_handbacks_checks_accept(
    monkeypatch: pytest.MonkeyPatch, events: list[EventRecord], no_gate: str | None
) -> None:
    d = batch([BASE])
    c, f = d.crs[0], FACTS._replace(gates=() if no_gate else FACTS.gates)
    assert driver_step(d, c, events, f).startswith("`handback CR-1 ready")
    heads = {"HEAD": f.head, f"{f.remote}/{c.branch}": f.pushed}
    monkeypatch.setattr(driver_checks, "cr_events", lambda *_: events)
    monkeypatch.setattr(driver_checks, "cr_worktree", lambda _: WT)
    monkeypatch.setattr(driver_checks, "dirty_files", lambda _: f.dirty)
    monkeypatch.setattr(driver_checks, "git", lambda *a, **_: heads[a[-1]])
    repo = SimpleNamespace(config={"remote": f.remote})
    b = SimpleNamespace(id=d.id, record=d)
    basis = driver_checks.handback_refusals(repo, b, c, no_gate, False)  # type: ignore[arg-type]
    assert basis.waiver is None and not basis.carried and not basis.verdict_carried


@pytest.mark.parametrize(
    ("status", "want"), [("queued", "A Driver starts it."), ("merged", "Nothing.")]
)
def test_a_cr_not_working_gets_its_views_next_sentence(repo: Path, status: str, want: str) -> None:
    d = batch([{"status": status, "pr": PR}])
    assert cr_step(Repo.find(), d, d.crs[0], []) == want


def snapshot(repo: Path) -> dict[str, bytes]:
    folder = changes(repo) / "4-batch"
    return {n: (folder / n).read_bytes() for n in ("batch.json", "events.jsonl")}


@pytest.mark.parametrize(
    ("args", "code", "text"),
    [
        (("--epoch", 9), EXIT_CONFLICT, "stale Foreman: Foreman n°9"),
        (("{one}", "--lease", 1, "--epoch", 1), EXIT_PRECONDITION, "--lease is a Driver's"),
        (("--lease", 1), EXIT_PRECONDITION, "needs the CR: next <cr> --lease 1"),
        (("{one}", "--lease", 7), EXIT_CONFLICT, "claim lost: "),
    ],
)
def test_the_refusals_of_next(leased: Led, args: tuple[Any, ...], code: int, text: str) -> None:  # noqa: F811
    _, chantier, (one, _) = leased
    got, out, err = chantier.bare("next", *[one if x == "{one}" else x for x in args])
    assert got == code and out == [] and text in err, err


def test_next_writes_nothing_and_the_commands_end_with_its_line(leased: Led) -> None:  # noqa: F811
    repo, chantier, (one, two) = leased
    before = snapshot(repo)
    due_lines = chantier.bare("next", "--epoch", 1)[1]
    assert due_lines == [f"due: a free slot (1 of 2 held): take {two} (`take {two} --epoch 1`)"]
    assert chantier.bare("next")[0] == chantier.bare("next", one, "--lease", 1)[0] == 0
    assert snapshot(repo) == before
    state = chantier.bare("status", "--since", 0)[1][0]
    assert state.endswith(f"| due {len(due_lines)}")  # child 11's count is the due list's length
    out = chantier("round", one)[1]
    assert out[-1] == chantier.bare("next", one, "--lease", 1)[1][0]
    assert out[-1].startswith("next: the round's Coder, then its reviews")
    out = chantier("handback", one, "blocked", "the user decides")[1]
    assert out[-1].startswith("next: send the hand-back line above to the ")
    assert sum(x.startswith("next: ") for x in out) == 1


def test_order_done_ends_with_the_first_due_item(leased: Led) -> None:  # noqa: F811
    _, chantier, (one, two) = leased
    assert chantier.bare("order", "note", one, "--note", "look")[0] == 0
    out = chantier.bare("next", "--epoch", 1)[1]
    assert len(out) == 2 and out[1].startswith("due: order O-1 note")  # noqa: PLR2004
    out = chantier.bare("order", "done", "O-1", "--epoch", 1)[1]
    assert out[-1] == f"next: a free slot (1 of 2 held): take {two} (`take {two} --epoch 1`)"


@pytest.mark.parametrize(
    ("epoch", "out", "added"),
    [
        (None, ["order O-1 merged CR-1"], False),  # a Chief of Staff's, in a Foreman's batch
        (1, ["paused", "next: the retro"], False),  # the batch's end: endpause's line alone
        (1, ["order O-1 merged CR-1"], True),
    ],
)
def test_order_merged_adds_a_line_only_for_the_steering_session(
    leased: Led,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    epoch: int | None,
    out: list[str],
    added: bool,
) -> None:
    monkeypatch.setattr(orders, "order", lambda args: list(out))
    args = argparse.Namespace(kind="merged", epoch=epoch, batch=None)
    got = next_lines.order(args)
    assert got[: len(out)] == out and (len(got) == len(out) + 1) == added
    assert sum(x.startswith("next: ") for x in got) == (1 if added or epoch else 0)

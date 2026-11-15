"""The `gate` object of a CR and its words: its state for each source, on a prepared record."""

from __future__ import annotations

from typing import Any

import pytest

from chantier.core.records import BatchRecord, CrEntry, EventRecord, GateWaiver
from chantier.status import gate as gate_module
from chantier.status.gate import event_step, gate_view

HEAD = "abc1234" + "0" * 33
OTHER = "def5678" + "0" * 33
REPO: Any = None  # only the live gate lock reads it, and it is patched here
STACK = GateWaiver(order="O-1", scope="stack", note="one gate on the top")
ONE = GateWaiver(order="O-2", scope="cr", note="batch-17", follow_up="gate-on-main")


def _batch(mode: str = "stack", waivers: dict[int, GateWaiver] | None = None) -> BatchRecord:
    crs = [
        CrEntry(
            id=f"CR-{n}",
            order=n,
            status="working",
            head=HEAD,
            pr=f"https://github.com/o/r/pull/{10 + n}",
            **({"gate_waiver": (waivers or {})[n]} if n in (waivers or {}) else {}),
        )
        for n in (1, 2, 3)
    ]
    return BatchRecord(id="batch-1", mode=mode, crs=crs)


def _event(kind: str, cr: str, **kw: Any) -> EventRecord:
    return EventRecord(t="2026-11-15T10:00:00Z", actor="driver", kind=kind, cr=cr, **kw)


def _view(d: BatchRecord, cr: int, events: list[EventRecord], live: bool = False) -> dict[str, Any]:
    return gate_view(REPO, d, d.crs[cr - 1], events, live)


@pytest.mark.parametrize(
    ("events", "state", "head", "text"),
    [
        ([], "none", None, "-"),
        (
            [_event("gate", "CR-1", head=HEAD, result="pass", run=1)],
            "passed",
            "abc1234",
            "passed abc1234",
        ),
        (
            [_event("gate", "CR-1", head=HEAD, result="fail", run=1)],
            "failed",
            "abc1234",
            "failed abc1234",
        ),
        # a pass at another head is no pass here
        ([_event("gate", "CR-1", head=OTHER, result="pass", run=1)], "none", None, "-"),
    ],
)
def test_the_state_of_a_gate_read_from_the_gate_events_at_the_head(
    events: list[EventRecord], state: str, head: str | None, text: str
) -> None:
    g = _view(_batch("parallel"), 1, events)
    assert (g["state"], g["head"], g["text"]) == (state, head, text)


def test_a_handback_exempt_by_no_gate_says_the_rule() -> None:
    d = _batch("parallel")
    d.crs[0].status = "ready"
    g = _view(d, 1, [_event("handback", "CR-1", result="ready", no_gate="docs only")])
    assert (g["state"], g["waiver"], g["text"]) == ("exempt", "docs only", "exempt: docs only")


def test_a_pass_carried_over_a_clean_rebase_names_the_head_it_came_from() -> None:
    d = _batch("parallel")
    d.crs[0].status = "ready"
    g = _view(d, 1, [_event("handback", "CR-1", result="ready", gate_from=OTHER)])
    assert (g["state"], g["head"], g["text"]) == ("carried", "def5678", "carried from def5678")


@pytest.mark.parametrize(
    ("live", "state"), [("gate running", "running"), ("gate queued", "queued")]
)
def test_a_working_cr_in_the_gate_lock_runs_or_waits(
    monkeypatch: pytest.MonkeyPatch, live: str, state: str
) -> None:
    monkeypatch.setattr(gate_module, "gate_state", lambda repo, cr: live)
    g = _view(_batch("parallel"), 1, [], live=True)
    assert (g["state"], g["text"]) == (state, state)


def test_a_stack_waiver_covers_the_lower_crs_and_the_top_validates_them() -> None:
    d = _batch(waivers={1: STACK, 2: STACK, 3: STACK})
    low, top = _view(d, 1, []), _view(d, 3, [])
    assert low["state"] == "waived" and low["waiver"] == "one gate on the top"
    assert low["validated_by"] == {"cr": "CR-3", "pr": "https://github.com/o/r/pull/13"}
    assert low["text"] == "waived → CR-3 (#13)"
    assert (top["state"], top["validated_by"], top["validates"]) == ("none", None, ["CR-1", "CR-2"])
    assert top["text"] == "validates CR-1, CR-2"


def test_a_top_with_its_pass_says_it_and_what_it_validates() -> None:
    d = _batch(waivers={1: STACK, 2: STACK, 3: STACK})
    g = _view(d, 3, [_event("gate", "CR-3", head=HEAD, result="pass", run=1)])
    assert g["text"] == "passed abc1234; validates CR-1, CR-2"


def test_a_cr_waiver_names_its_follow_up_and_validates_nothing() -> None:
    g = _view(_batch("parallel", {1: ONE}), 1, [])
    assert (g["state"], g["follow_up"], g["validated_by"], g["validates"]) == (
        "waived",
        "gate-on-main",
        None,
        [],
    )
    assert g["text"] == "waived → follow-up gate-on-main"


def test_a_withdrawn_waiver_leaves_the_cr_needing_its_gate() -> None:
    d = _batch(waivers={1: STACK, 2: STACK, 3: STACK})
    d.crs[0].unset("gate_waiver")
    assert _view(d, 1, [])["state"] == "none"


def test_the_handback_event_keeps_the_waiver_it_was_handed_back_under() -> None:
    d = _batch(waivers={1: STACK, 2: STACK, 3: STACK})
    d.crs[0].status = "merged"
    e = _event("handback", "CR-1", result="ready", gate_waiver="O-1", validated_by="CR-3")
    g = _view(d, 1, [e])
    assert (g["state"], g["validated_by"]["cr"]) == ("waived", "CR-3")
    assert event_step(d, e) == "waived (O-1): validated by CR-3 (#13)"
    follow = _event("handback", "CR-1", result="ready", gate_waiver="O-2", follow_up="gate-on-main")
    assert event_step(d, follow) == "waived (O-2): follow-up gate-on-main"
    assert (
        event_step(d, _event("handback", "CR-1", result="ready", no_gate="docs")) == "exempt: docs"
    )


def test_a_withdrawn_stack_waiver_keeps_its_note_for_a_cr_handed_back_under_it() -> None:
    d = _batch(waivers={1: STACK, 2: STACK, 3: STACK})
    d.crs[0].status = "ready"
    d.crs[0].unset("gate_waiver")
    e = _event(
        "handback",
        "CR-1",
        result="ready",
        gate_waiver="O-1",
        waiver_note="the user",
        validated_by="CR-3",
    )
    g = _view(d, 1, [e])
    assert (g["state"], g["waiver"]) == ("waived", "the user")

"""The board's per-CR times (Gantt segments, rounds), derived from events."""

from __future__ import annotations

from typing import Any

import pytest

from chantier.board.times import cr_times
from chantier.core.records import CrEntry, EventRecord


def ev(t: str, kind: str, **fields: Any) -> EventRecord:
    return EventRecord(t=f"2026-06-18T{t}Z", actor="x", kind=kind, cr="CR-1", **fields)


def at(t: str) -> str:
    return f"2026-06-18T{t}Z"


def seg(state: str, a: str, b: str | None) -> dict[str, Any]:
    return {"state": state, "from": at(a), "to": at(b) if b else None}


MERGED_FULL = [
    ev("09:00:00", "add", origin="x/1-inbox/a"),
    ev("09:01:00", "take"),
    ev("09:02:00", "round", round=1),
    ev("09:10:00", "phase", phase="inspector"),
    ev("09:20:00", "handback", result="blocked"),
    ev("09:30:00", "take"),
    ev("09:31:00", "round", round=2),
    ev("09:40:00", "handback", result="ready"),
    ev("09:41:00", "pr-draft", draft=False),
    ev("09:50:00", "phase", phase="verifier"),
    ev("09:55:00", "verdict", result="pass"),
    ev("10:00:00", "order", order_kind="merged"),
]

CASES: dict[str, tuple[list[EventRecord], CrEntry, dict[str, Any]]] = {
    "merged-at": (
        MERGED_FULL,
        CrEntry(id="CR-1", status="merged", merged_at=at("10:05:00")),
        {
            "started_at": at("09:01:00"),
            "ended_at": at("10:05:00"),
            "state_at": at("10:05:00"),
            "segments": [
                seg("working", "09:01:00", "09:20:00"),
                seg("blocked", "09:20:00", "09:30:00"),
                seg("working", "09:30:00", "09:40:00"),
                seg("draft", "09:40:00", "09:41:00"),
                seg("ready", "09:41:00", "10:05:00"),
            ],
            "rounds": [
                {"n": 1, "coder_at": at("09:02:00"), "inspector_at": at("09:10:00")},
                {"n": 2, "coder_at": at("09:31:00"), "inspector_at": None},
            ],
            "verifier_at": at("09:50:00"),
            "verdict": "pass",
            "verdict_at": at("09:55:00"),
        },
    ),
    "order-merged": (
        [ev("09:01:00", "take"), ev("09:30:00", "order", order_kind="merged")],
        CrEntry(id="CR-1", status="merged"),
        {"ended_at": at("09:30:00"), "segments": [seg("working", "09:01:00", "09:30:00")]},
    ),
    "handback-merged": (
        [ev("09:01:00", "take"), ev("09:30:00", "handback", result="merged")],
        CrEntry(id="CR-1", status="merged"),
        {"ended_at": at("09:30:00"), "segments": [seg("working", "09:01:00", "09:30:00")]},
    ),
    "cancelled": (
        [ev("09:01:00", "take"), ev("09:30:00", "cancel")],
        CrEntry(id="CR-1", status="cancelled"),
        {
            "ended_at": at("09:30:00"),
            "state_at": at("09:30:00"),
            "segments": [seg("working", "09:01:00", "09:30:00")],
        },
    ),
    "dropped": (
        [ev("09:01:00", "take"), ev("09:30:00", "order", order_kind="drop")],
        CrEntry(id="CR-1", status="cancelled"),
        {"ended_at": at("09:30:00"), "segments": [seg("working", "09:01:00", "09:30:00")]},
    ),
    "never-taken": (
        [ev("09:00:00", "add")],
        CrEntry(id="CR-1"),
        {
            "started_at": None,
            "ended_at": None,
            "state_at": None,
            "segments": [],
            "rounds": [],
            "verdict": None,
        },
    ),
    "retake": (
        [ev("09:01:00", "take"), ev("09:20:00", "take", restart=True)],
        CrEntry(id="CR-1", status="working"),
        {"started_at": at("09:01:00"), "segments": [seg("working", "09:01:00", None)]},
    ),
    "blocked-retaken": (
        [
            ev("09:01:00", "take"),
            ev("09:10:00", "handback", result="blocked"),
            ev("09:20:00", "take"),
        ],
        CrEntry(id="CR-1", status="working"),
        {
            "ended_at": None,
            "segments": [
                seg("working", "09:01:00", "09:10:00"),
                seg("blocked", "09:10:00", "09:20:00"),
                seg("working", "09:20:00", None),
            ],
        },
    ),
    "handed-back-open": (
        [
            ev("09:01:00", "take"),
            ev("09:10:00", "handback", result="ready"),
            ev("09:15:00", "phase", phase="pr"),
        ],
        CrEntry(id="CR-1", status="ready"),
        {
            "ended_at": None,
            "state_at": at("09:10:00"),
            "segments": [seg("working", "09:01:00", "09:10:00"), seg("draft", "09:10:00", None)],
        },
    ),
    "pr-draft-state-at": (
        [
            ev("09:01:00", "take"),
            ev("09:10:00", "pr-draft", draft=True),
            ev("09:15:00", "phase", phase="gate"),
        ],
        CrEntry(id="CR-1", status="working"),
        {"state_at": at("09:10:00")},
    ),
    "round-no-inspector": (
        [
            ev("09:01:00", "take"),
            ev("09:02:00", "round", round=1),
            ev("09:30:00", "round", round=2),
        ],
        CrEntry(id="CR-1", status="working"),
        {
            "rounds": [
                {"n": 1, "coder_at": at("09:02:00"), "inspector_at": None},
                {"n": 2, "coder_at": at("09:30:00"), "inspector_at": None},
            ]
        },
    ),
}


@pytest.mark.parametrize("name", CASES)
def test_cr_times(name: str) -> None:
    events, entry, expected = CASES[name]
    times = cr_times(events, entry)
    assert {k: times[k] for k in expected} == expected

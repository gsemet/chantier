"""What the pane and `status` say of a parked CR: the step, the phase, the now and next sentences,
and the order of the `parked:` lines."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from chantier.core.records import BatchRecord, CrEntry
from chantier.core.repo import Repo
from chantier.core.waits import make
from chantier.stack_apart import parked_lines
from chantier.status.now_next import now_next
from chantier.status.words import phase_text, severity, step

REPO = cast(Repo, SimpleNamespace(config={"default_branch": "main"}))


def parked(*, open_wait: bool, reason: str = "parked: question: which API?") -> CrEntry:
    wait = make("w1", "answer", "which API?", None, "x")
    wait["since"] = "2026-11-21T10:05:00Z"
    if not open_wait:
        wait["cleared_at"] = "2026-11-21T11:00:00Z"
    return CrEntry(
        id="CR-2",
        status="blocked",
        order=2,
        parked="2026-11-21T10:00:00Z",
        blocked_reason=reason,
        waits=[wait],
    )


@pytest.mark.parametrize("open_wait", [True, False])
def test_the_pane_words_of_a_parked_cr(open_wait: bool) -> None:
    c = parked(open_wait=open_wait)
    d = BatchRecord(id="batch-01", mode="stack", crs=[c])
    assert step(c) == "Parked" and severity(c) == "red"
    now, nxt = now_next(REPO, d, c, [])
    if open_wait:
        assert (phase_text(c) or "").startswith("parked: waits for w1 answer since 10:")
        assert "which API?" in (phase_text(c) or "")
        assert now == "parked: question: which API?"
        assert nxt == "Its wait cleared, the Foreman takes it back on top."
    else:
        assert phase_text(c) == "parked: wait cleared"
        assert now == "Parked: its wait is cleared."
        assert nxt == "The Foreman takes it back, before any queued CR."


def test_a_blocked_cr_that_is_not_parked_keeps_its_own_words() -> None:
    c = CrEntry(id="CR-3", status="blocked", order=3, blocked_reason="question: which API?")
    assert step(c) == "Question" and phase_text(c) == "waits for the user"


def test_status_prints_the_cleared_parked_crs_before_the_waiting_ones() -> None:
    first, second = parked(open_wait=True), parked(open_wait=False)
    second.id, second.order = "CR-5", 5
    d = BatchRecord(id="batch-01", mode="parallel", crs=[first, second])
    lines = parked_lines(d)
    assert lines[0].startswith("parked: CR-5 wait cleared: take it back before any queued CR")
    assert lines[1].startswith("parked: CR-2 since 10:00, waits for w1 answer")
    assert lines[1].endswith("out of the slots")  # no stack in a parallel batch

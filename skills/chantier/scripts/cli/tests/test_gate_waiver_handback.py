"""`handback ready` under a waiver: a covered CR needs no gate pass, the stack's top does."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from chantier.commands import driver_checks
from chantier.core.errors import ChantierError
from chantier.core.records import BatchRecord, CrEntry, GateWaiver

HEAD = "a" * 40


def _cr(n: int, **kw: Any) -> CrEntry:
    return CrEntry(
        id=f"CR-{n}", order=n, status="live", head=HEAD, branch=f"b{n}", worktree=".", **kw
    )


def _batch(waivers: dict[int, GateWaiver], mode: str = "stack") -> SimpleNamespace:
    crs = [_cr(n, **({"gate_waiver": waivers[n]} if n in waivers else {})) for n in (1, 2, 3)]
    return SimpleNamespace(id="batch-1", record=BatchRecord(id="batch-1", mode=mode, crs=crs))


@pytest.fixture(autouse=True)
def clean_pushed_verified(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(driver_checks, "git", lambda *a, **k: HEAD)
    monkeypatch.setattr(driver_checks, "dirty_files", lambda wt: [])
    monkeypatch.setattr(driver_checks, "cr_events", lambda *a: [])
    monkeypatch.setattr(driver_checks, "last_verdict", lambda events, head: "VERIFIED")
    monkeypatch.setattr(driver_checks, "_gate_missing", lambda *a: ("refused: no long gate", ""))


REPO: Any = SimpleNamespace(config={"remote": "origin", "default_branch": "main"})
STACK = GateWaiver(order="O-1", scope="stack", note="one gate on the top")
ONE = GateWaiver(order="O-2", scope="cr", note="batch-17", follow_up="gate-on-main")


def test_a_covered_lower_cr_hands_back_with_no_gate_and_says_by_whom() -> None:
    b: Any = _batch({1: STACK, 2: STACK, 3: STACK})
    basis = driver_checks.handback_refusals(REPO, b, b.record.crs[0], None, False)
    assert basis.waiver is STACK or basis.waiver == STACK
    assert basis.words() == "long gate waived (O-1): validated by CR-3's gate"


def test_a_cr_waiver_names_its_follow_up() -> None:
    b: Any = _batch({1: ONE}, mode="parallel")
    basis = driver_checks.handback_refusals(REPO, b, b.record.crs[0], None, False)
    assert basis.words() == "long gate waived (O-2): follow-up gate-on-main"


def test_the_top_of_a_waived_stack_needs_its_gate() -> None:
    b: Any = _batch({1: STACK, 2: STACK, 3: STACK})
    with pytest.raises(ChantierError, match="no long gate"):
        driver_checks.handback_refusals(REPO, b, b.record.crs[2], None, False)


def test_the_other_checks_stay_under_a_waiver(monkeypatch: pytest.MonkeyPatch) -> None:
    b: Any = _batch({1: STACK, 2: STACK, 3: STACK})
    monkeypatch.setattr(driver_checks, "last_verdict", lambda events, head: "NOT VERIFIED")
    with pytest.raises(ChantierError, match="no verdict VERIFIED"):
        driver_checks.handback_refusals(REPO, b, b.record.crs[0], None, False)
    monkeypatch.setattr(driver_checks, "dirty_files", lambda wt: ["x"])
    with pytest.raises(ChantierError, match="uncommitted"):
        driver_checks.handback_refusals(REPO, b, b.record.crs[0], None, False)


def test_no_gate_wins_over_a_waiver() -> None:
    b: Any = _batch({1: STACK, 2: STACK, 3: STACK})
    basis = driver_checks.handback_refusals(REPO, b, b.record.crs[0], "a rule", False)
    assert basis.waiver is None and basis.words() == ""

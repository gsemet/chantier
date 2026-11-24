"""The `handed back:` lines and the `batch:` line of `status`, on a prepared record."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from batch_helpers import record, write_record
from conftest import Chantier

from chantier.core.records import (
    BatchRecord,
    BatchSettings,
    CrEntry,
    EventRecord,
    OrderRecord,
    ReleaseGrant,
)
from chantier.status import ready_line
from chantier.status.ready_line import batch_line, ready_lines
from chantier.status.words import state_label

HEAD = "abc1234" + "0" * 33
FROM = "def5678" + "0" * 33
URL = "https://github.com/o/r/pull/11"
REPO: Any = SimpleNamespace(config={"default_branch": "main"}, session_root=Path("."))


def _cr(n: int = 1, **kw: Any) -> CrEntry:
    base: dict[str, Any] = {
        "id": f"CR-{n}",
        "order": n,
        "status": "ready",
        "head": HEAD,
        "pr": URL,
        "pr_draft": False,
        "path": f"4-batch/2-actives/{n}-the-slug",
    }
    return CrEntry(**{**base, **kw})


def _batch(*crs: CrEntry, **kw: Any) -> BatchRecord:
    return BatchRecord(
        id="batch-1",
        mode=kw.pop("mode", "parallel"),
        steering=kw.pop("steering", "foreman"),
        slots=kw.pop("slots", 4),
        crs=list(crs),
        **kw,
    )


def _event(kind: str = "gate", cr: str = "CR-1", **kw: Any) -> EventRecord:
    return EventRecord(t="2026-11-15T10:00:00Z", actor="driver", kind=kind, cr=cr, **kw)


def _ready(note: str = "", **kw: Any) -> EventRecord:
    return _event("handback", result="ready", note=note, **kw)


PASS = _event(head=HEAD, result="pass", run=1)


def _lines(
    d: BatchRecord, events: list[EventRecord] | None = None, stopped: set[str] | None = None
) -> list[str]:
    return ready_lines(REPO, d, events or [], stopped or set())


def _one(d: BatchRecord, events: list[EventRecord] | None = None, **kw: Any) -> str:
    (line,) = _lines(d, events, **kw)
    return str(line)


@pytest.mark.parametrize(
    ("cr", "icon", "word", "tail"),
    [
        ({}, "🟢", "ready to merge", URL),
        ({"pr_draft": True}, "🟤", "PR in draft", f"{URL} | do not merge: waits for its turn"),
        ({"pr": None, "pr_draft": None}, "🟣", "ready locally", "no PR yet"),
    ],
)
def test_the_icon_and_word_are_the_labels_own(
    cr: dict[str, Any], icon: str, word: str, tail: str
) -> None:
    d = _batch(_cr(**cr))
    line = _one(d, [PASS])
    assert line.startswith(f"handed back: {icon} {word} CR-1 the-slug {tail}")
    assert state_label(REPO, d, d.crs[0], []).startswith(f"{icon} {word}")


@pytest.mark.parametrize(
    ("note", "expect"),
    [
        ("https://x/1 gaps: a; b", " | gaps: a; b"),
        ("https://x/1 draft on dev: waits for CR-2; gaps: c d", " | gaps: c d"),
        ("https://x/1", None),
    ],
)
def test_the_gaps_are_the_last_hand_backs_unchanged(note: str, expect: str | None) -> None:
    line = _one(_batch(_cr()), [PASS, _ready("old gaps: no"), _ready(note)])
    assert (expect in line) if expect else "gaps" not in line


@pytest.mark.parametrize(
    ("events", "text"),
    [
        ([PASS], "passed"),
        ([_ready(gate_from=FROM)], "passed (carried from def5678)"),
        ([_event(head=HEAD, result="fail", run=1)], "failed"),
        ([], "not run"),
        ([_ready(no_gate="docs only")], "exempt: docs only"),
        ([_ready(gate_waiver="O-2", follow_up="gate-main")], "waived → follow-up gate-main"),
    ],
)
def test_the_long_gate_clause_says_what_the_record_holds(
    events: list[EventRecord], text: str
) -> None:
    line = _one(_batch(_cr()), events)
    assert line.endswith(f" | long gate CR-1 at abc1234: {text}")
    assert "local gate" not in line


def test_the_long_gate_clause_is_absent_with_no_head() -> None:
    assert "long gate" not in _one(_batch(_cr(head=None)), [PASS])


@pytest.mark.parametrize(
    ("steering", "kw", "who"),
    [
        ("foreman", {}, "the Foreman"),
        ("direct", {}, "the Chief of Staff"),
        ("foreman", {"agent": "drv", "live": True}, "its Driver"),
        ("foreman", {"agent": "drv", "live": False}, "the Foreman"),
        ("foreman", {"agent": "drv", "live": True, "host": "copilot"}, "the Foreman"),
        ("direct", {"agent": "drv", "live": True, "host": "copilot"}, "the Chief of Staff"),
    ],
)
def test_an_open_long_gate_is_owed_by_the_one_the_host_shows(
    monkeypatch: pytest.MonkeyPatch, steering: str, kw: dict[str, Any], who: str
) -> None:
    monkeypatch.setattr(ready_line, "ended_unrecorded", lambda *a: not kw.get("live", True))
    extra = {"host": kw["host"]} if "host" in kw else {}
    d = _batch(_cr(agent=kw.get("agent")), steering=steering, **extra)
    line = _one(d)
    assert f" | owed before the merge: its long gate passes at abc1234 ({who}) | " in line
    assert "do not merge before" not in line
    assert f"long gate owed: CR-1 ({who})" in batch_line(REPO, d, [], set())


def test_a_driver_the_host_reports_stopped_is_not_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ready_line, "ended_unrecorded", lambda *a: False)
    line = _one(_batch(_cr(agent="drv")), stopped={"drv"})
    assert "(the Foreman)" in line


def test_orders_not_applied_are_owed_and_applied_ones_are_not() -> None:
    orders = [
        OrderRecord(id="O-21", kind="note", cr="CR-1"),
        OrderRecord(id="O-22", kind="hold", cr="CR-1", applied=True),
        OrderRecord(id="O-23", kind="note", cr="CR-1", done="x"),
        OrderRecord(id="O-24", kind="note", cr="CR-2"),
    ]
    d = _batch(_cr(), _cr(2, pr=None, pr_draft=None), orders=orders)
    line = _lines(d, [PASS])[0]
    assert " | owed before the merge: O-21 note is applied (the Foreman) | " in line
    assert "O-22" not in line
    assert "O-23" not in line
    assert "O-24" not in line
    both = _one(_batch(_cr(), orders=orders[:1]), [])
    assert "(the Foreman); O-21 note is applied (the Foreman) | " in both


def test_no_open_step_gives_no_owed_segment() -> None:
    assert "owed before" not in _one(_batch(_cr()), [PASS])


@pytest.mark.parametrize("status", ["queued", "working", "blocked", "merged", "cancelled"])
def test_a_cr_not_handed_back_has_no_line(status: str) -> None:
    assert _lines(_batch(_cr(status=status))) == []


def test_the_lines_come_in_the_rows_order() -> None:
    d = _batch(_cr(2), _cr(1))
    assert [x.split()[6] for x in _lines(d)] == ["CR-1", "CR-2"]


def _line(d: BatchRecord, events: list[EventRecord] | None = None) -> str:
    return batch_line(REPO, d, events or [], set())


@pytest.mark.parametrize("mode", ["stack", "series", "parallel"])
@pytest.mark.parametrize("steering", ["foreman", "direct"])
def test_the_batch_line_names_the_shape_and_who_steers(mode: str, steering: str) -> None:
    line = _line(_batch(_cr(), mode=mode, steering=steering), [PASS])
    word = "Foreman" if steering == "foreman" else "direct (the Chief of Staff)"
    assert line.startswith(f"batch: shape {mode}; slots 0/4; steering {word}; rounds 3; ")
    assert "long gate owed: none; merges: the user" in line


def test_the_batch_line_gives_each_limit_and_the_budget() -> None:
    d = _batch(_cr(rounds=5), settings=BatchSettings(max_rounds=2), budget_usd=50, spent_usd=1.2)
    assert "rounds 2 (CR-1 5); budget $1.20 of $50; " in _line(d)
    none = _batch(_cr(), spent_usd=1.2)
    assert "rounds 3; budget none (spent $1.20); " in _line(none)


@pytest.mark.parametrize(
    ("grant", "under"),
    [
        (None, False),
        (ReleaseGrant(), False),
        (ReleaseGrant(autonomous=1), True),
        (ReleaseGrant(fixes=True), True),
    ],
)
def test_the_merge_is_the_users_and_a_grant_is_said(
    grant: ReleaseGrant | None, under: bool
) -> None:
    line = _line(_batch(_cr(), release=grant))
    assert ("; under the grant: the release/fix PR (steering session)" in line) is under
    assert "merges: the user" in line


def test_the_batch_line_is_the_second_line_of_status(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    from batch_helpers import open_batch  # noqa: PLC0415

    open_batch(repo, chantier, monkeypatch, "Ready one", "Queued two")
    data = record(repo)
    data["crs"][0].update(status="ready", pr=URL, pr_draft=False, head=HEAD)
    write_record(repo, data)
    _, out, _ = chantier("status")
    assert out[0].split(" live ")[1].startswith("0/")
    assert out[1].startswith("batch: shape ")
    ready = [x for x in out if x.startswith("handed back: ")]
    assert len(ready) == 1
    assert out.index(ready[0]) > max(i for i, x in enumerate(out) if x.startswith("CR-"))
    assert f"{URL} | " in ready[0]

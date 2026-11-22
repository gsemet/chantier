"""The screen's data of `chantier live` and its drawing, fed with prepared events: no network, no
server."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Any

import pytest

from chantier.clients.tui import screen
from chantier.clients.tui.link import Event, Linked
from chantier.clients.tui.model import Model, lease_left

NOW = "2030-01-01T00:00:00Z"
WIDE, NARROW, HIGH = 140, 90, 20


def _lease(**over: Any) -> dict[str, Any]:
    facts = {"n": 1, "renewed": NOW, "expires": "2030-01-01T00:04:30Z", "ended": None}
    return {**facts, "gate": None, **over}


def _crs() -> list[dict[str, Any]]:
    row = {"phase": None, "round": 0, "round_limit": 3, "lease": None, "blocked": None}
    return [
        {**row, "cr": "CR-1", "title": "Working one", "state": "working", "phase": "coding",
         "round": 1, "lease": _lease()},
        {**row, "cr": "CR-2", "title": "Ready one", "state": "handed_back", "to_review": True,
         "handed_back_at": "2029-12-31T23:48:00Z"},
        {**row, "cr": "CR-3", "title": "Held one", "state": "blocked",
         "blocked": "waits for the user's answer"},
        {**row, "cr": "CR-4", "title": "Done one", "state": "merged"},
    ]  # fmt: skip


def _record(kind: str, t: str, **more: Any) -> dict[str, Any]:
    return {"t": t, "actor": "Foreman", "kind": kind, **more}


def _project(events: list[dict[str, Any]]) -> dict[str, Any]:
    batch = {"id": "batch-01", "state": "running", "mode": "batch", "crs": _crs()}
    return {**{"batch": {**batch, "stack_lease": None}}, "events": events}


def _fed(clock: list[float]) -> Model:
    m = Model(clock=lambda: clock[0])
    m.feed(Linked("ws", NOW))
    board = {"version": "0.15.0", "served": "/work/p", "projects": [{"id": "p", "inbox": 2}]}
    m.feed(Event("board", "board", board, NOW))
    first = [_record("took", "2029-12-31T23:50:00Z", cr="CR-1")]
    m.feed(Event("project:p", "project", _project(first), NOW))
    m.feed(Event("events:p", "events", {"lines": []}, NOW))
    return m


def test_the_model_counts_and_keeps_each_new_line_once() -> None:
    clock = [100.0]
    m = _fed(clock)
    assert m.counts() == {"working": 1, "ready": 1, "held": 1, "done": 1}
    assert m.missing() == [] and m.agents() == [("p", "Driver CR-1 coding")]
    earlier = [_record("took", "2029-12-31T23:50:00Z", cr="CR-1")]
    later = [*earlier, _record("handed_back", "2029-12-31T23:59:00Z", cr="CR-2", result="ok")]
    m.feed(Event("project:p", "project", _project(later), NOW))
    m.feed(Event("project:p", "project", _project(later), NOW))  # the same again: nothing new
    lines = [
        {"seq": 1, "t": "2029-12-31T23:59:30Z", "type": "board@1", "source": "board",
         "text": "board wrote (new): an idea"},
        {"seq": 2, "t": "2029-12-31T23:59:40Z", "type": "later@1", "source": "hub"},
    ]  # fmt: skip
    m.feed(Event("events:p", "events", {"lines": lines}, NOW))
    assert [x.text for x in m.flow] == [
        "took CR-1",
        "handed_back CR-2 ok",
        "board wrote (new): an idea",
        "later@1",  # no `text`: its type
    ]
    clock[0] += 30  # "now" is the server's plus the time elapsed here
    assert m.now() == datetime(2030, 1, 1, 0, 0, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    ("over", "left"),
    [
        ({}, "04:30"),
        ({"expires": "2029-12-31T23:57:00Z", "gate": "gate"}, "gate"),
        ({"expires": "2029-12-31T23:57:00Z"}, "not confirmed 3 min"),
        ({"ended": "2029-12-31T23:59:00Z"}, None),
    ],
)
def test_the_time_left_of_a_lease_comes_from_its_facts_and_the_servers_now(
    over: dict[str, Any], left: str | None
) -> None:
    m = Model(clock=lambda: 0.0)
    m.feed(Linked("http", NOW))  # this machine's clock is not asked
    assert lease_left(_lease(**over), m.now()) == left
    assert lease_left(None, m.now()) is None


def _drawn(m: Model, width: int) -> str:
    out = io.StringIO()
    screen.plain(m, width, HIGH, out)
    return out.getvalue()


def test_the_screen_shows_the_counts_the_tasks_and_the_flow_and_drops_the_left_column() -> None:
    m = _fed([0.0])
    wide = _drawn(m, WIDE)
    assert "working 1  ready 1  held 1  done 1" in wide and "v0.15.0" in wide
    assert "lease 04:30" in wide and "round 1/3" in wide  # the working CR
    assert "12m  Ready one" in wide  # to review, with its age
    assert "waits for the user's answer" in wide  # blocked, with its reason
    assert "23:50:00" in wide and "took CR-1" in wide  # a flow line
    assert "Projects" in wide and "Driver CR-1 coding" in wide
    assert all(len(x) <= WIDE for x in wide.splitlines()) and "\x1b" not in wide
    narrow = _drawn(m, NARROW)
    assert "Projects" not in narrow and "lease 04:30" in narrow

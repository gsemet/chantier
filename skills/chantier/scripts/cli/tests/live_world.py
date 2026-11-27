"""The prepared state the live view's tests draw from."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from chantier.clients.tui import screen
from chantier.clients.tui.link import Event, Linked
from chantier.clients.tui.model import Model
from chantier.clients.tui.view import View

CAP = 2000

NOW = "2030-01-01T00:00:00Z"
WIDE, NARROW, HIGH = 140, 90, 21
PARIS = ZoneInfo("Europe/Paris")
TOKENS = Path(__file__).parents[1] / "src/chantier/clients/web/css/tokens.css"


def lease(**over: Any) -> dict[str, Any]:
    facts = {"n": 1, "renewed": NOW, "expires": "2030-01-01T00:04:30Z", "ended": None}
    return {**facts, "gate": None, **over}


def crs() -> list[dict[str, Any]]:
    row = {"phase": None, "round": 0, "round_limit": 3, "lease": None, "blocked": None}
    return [
        {**row, "cr": "CR-1", "title": "Working one", "state": "working", "phase": "coding",
         "round": 1, "lease": lease()},
        {**row, "cr": "CR-2", "title": "Ready one", "state": "handed_back", "to_review": True,
         "handed_back_at": "2029-12-31T23:48:00Z"},
        {**row, "cr": "CR-3", "title": "Held one", "state": "blocked",
         "blocked": "waits for the user's answer"},
        {**row, "cr": "CR-4", "title": "Done one", "state": "merged"},
    ]  # fmt: skip


def record(kind: str, t: str, **more: Any) -> dict[str, Any]:
    return {"t": t, "actor": "Foreman", "kind": kind, **more}


def project(events: list[dict[str, Any]]) -> dict[str, Any]:
    batch = {"id": "batch-01", "state": "running", "mode": "batch", "crs": crs()}
    return {**{"batch": {**batch, "stack_lease": None}}, "events": events}


def fed(clock: list[float]) -> Model:
    m = Model(clock=lambda: clock[0], zone=PARIS)
    m.feed(Linked("ws", NOW))
    board = {"version": "0.15.0", "served": "/work/p", "projects": [{"id": "p", "inbox": 2}]}
    m.feed(Event("board", "board", board, NOW))
    first = [record("took", "2029-12-31T23:50:00Z", cr="CR-1")]
    m.feed(Event("project:p", "project", project(first), NOW))
    m.feed(Event("events:p", "events", {"lines": []}, NOW))
    return m


def watching(case: str) -> list[Model]:
    """The boards of a case: `one` project, two `projects` of one board, or two `boards`."""
    if case == "boards":
        a, b = fed([0.0]), fed([0.0])
        a.label, b.label = "a", "b"
        return [a, b]
    m = fed([0.0])
    if case == "projects":
        board = {"version": "0.15.0", "served": "/work/p", "projects": [{"id": "p"}, {"id": "q"}]}
        m.feed(Event("board", "board", board, NOW))
    return [m]


def drawn(m: Model, width: int) -> str:
    out = io.StringIO()
    screen.plain(m, width, HIGH, out)
    return out.getvalue()


def journal(m: Model, lines: list[dict[str, Any]]) -> None:
    m.feed(Event("events:p", "events", {"lines": lines}, NOW))


def numbered(start: int, stop: int, minute: int = 30, prefix: str = "line") -> list[dict[str, Any]]:
    return [
        {"seq": i, "t": f"2029-12-31T23:{minute}:{i % 60:02d}Z", "source": "hub",
         "text": f"{prefix} {i:02d}"}
        for i in range(start, stop)
    ]  # fmt: skip


def keyed(m: Model, view: View) -> str:
    out = io.StringIO()
    view.keys = True
    screen.plain(m, WIDE, HIGH, out, view)  # 15 rows of Flow
    return out.getvalue()

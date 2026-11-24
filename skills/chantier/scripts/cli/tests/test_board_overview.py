"""What "All projects" shows beyond the project lines: the open PRs of each project, the recent
activity of every project and the History's `*` address. On a prepared surface of four projects
(alpha and beta run a batch of two ready CRs), the journal written through the one append function,
with no forge."""

from __future__ import annotations

import json
from typing import Any

import pytest
from api_client import settled
from conftest import Surface
from forge_world import LINK, World
from test_board_history import OK, entry

from chantier.board import history_page, overview
from chantier.board.api import ops
from chantier.board.context import Context
from chantier.board.key import KeyFile, key_path, load_or_create
from chantier.board.projects import open_projects
from chantier.board.seats import Seats
from chantier.core import clock
from chantier.hub import journal

BACK = "2026-11-20T10:00:00Z"
FEED_KEYS = {"project", "kind", "at", "cr", "title", "batch", "pr"}
TWO, ROWS = 2, 20


class Served:
    """The four projects of a surface served by one context."""

    def __init__(self, surface: Surface, monkeypatch: pytest.MonkeyPatch) -> None:
        self.forge = World(surface, monkeypatch)
        monkeypatch.setattr(clock, "_fixed", [])
        projects = open_projects()
        found = projects.home
        load_or_create(found)
        self.ctx = Context(
            projects, KeyFile(key_path(found)), Seats(projects), "t", lambda: None, None
        )

    def hand_back(self, name: str, *crs: str) -> None:
        folder = self.forge.project(name) / "changes" / "4-batch"
        lines = [
            {"t": BACK, "actor": "t", "kind": "handback", "cr": cr, "result": "ready"} for cr in crs
        ]
        (folder / "events.jsonl").write_text(
            "".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8"
        )
        settled(self.ctx)

    def red(self, name: str, cr: str, at: str) -> None:
        """A `checks-red@1` line the hub would write, at `at`, through the one append function."""
        clock.fix(at)
        pr = LINK.format(name, 10 if cr == "CR-1" else 11)
        event = journal.red_event("batch-01", cr, pr, at[11:13].ljust(40, "c"))
        assert journal.append(self.forge.repo(name), [event], "hub")
        settled(self.ctx)

    def states(self, name: str) -> dict[str, str]:
        line = next(p for p in overview.board_data(self.ctx)["projects"] if p["id"] == name)
        return {r["cr"]: r["state"] for r in line["open_prs"]}

    def closed(self, name: str, batch: str, crs: list[dict[str, Any]]) -> None:
        folder = self.forge.project(name) / "changes" / "5-archives" / "batches"
        folder.mkdir(parents=True, exist_ok=True)
        data = {"schema": 1, "batch": batch, "state": "closed", "crs": crs}
        (folder / f"{batch}.json").write_text(json.dumps(data), encoding="utf-8")
        settled(self.ctx)

    def history(self, project: str) -> dict[str, Any]:
        args = {"project": project, "period": "week", "date": "2026-11-20", "tz": "UTC"}
        got = ops.call(self.ctx, "history.get", args)
        assert got.status == OK and got.data is not None, got.error
        return got.data


@pytest.fixture
def served(surface: Surface, monkeypatch: pytest.MonkeyPatch) -> Served:
    return Served(surface, monkeypatch)


def test_a_red_ci_after_the_hand_back_reads_red_the_same_cr_without_it_reads_ready(
    served: Served,
) -> None:
    served.hand_back("alpha", "CR-1", "CR-2")
    assert served.states("alpha") == {"CR-1": "ready", "CR-2": "ready"}
    served.red("alpha", "CR-1", "2026-11-20T09:00:00Z")  # before the hand-back: not shown
    assert served.states("alpha") == {"CR-1": "ready", "CR-2": "ready"}
    served.red("alpha", "CR-1", "2026-11-20T11:00:00Z")
    assert served.states("alpha") == {"CR-1": "red", "CR-2": "ready"}
    assert served.states("beta") == {"CR-1": "ready", "CR-2": "ready"}  # another project's own


def test_building_the_open_pr_rows_and_the_feed_calls_no_forge(served: Served) -> None:
    served.hand_back("alpha", "CR-1", "CR-2")
    data = overview.board_data(served.ctx)
    line = next(p for p in data["projects"] if p["id"] == "alpha")
    assert line["open_prs"] and data["activity"] is not None
    history_page.feed(served.ctx, served.ctx.projects.all(), overview.FEED_ROWS)
    assert served.forge.calls == []


def test_no_batch_no_open_prs(served: Served) -> None:
    line = next(p for p in overview.board_data(served.ctx)["projects"] if p["id"] == "delta")
    assert line["open_prs"] == []  # its CRs are merged
    assert served.states("gamma") == {}  # cancelled


def test_all_projects_history_holds_the_events_of_both_projects(served: Served) -> None:
    day = "2026-11-20T10:00:00Z"
    served.closed("alpha", "batch-00", [entry("CR-1", ended=day, cost_usd=1.5)])
    served.closed(
        "beta",
        "batch-00",
        [entry("CR-2", ended=day, cost_usd=2.0), entry("CR-3", "dropped", ended=day, pr=None)],
    )
    alpha, beta = served.history("alpha"), served.history("beta")
    both = served.history(history_page.ALL)
    items = [e for d in both["days"] for e in d["items"]]
    assert {e["project"] for e in items} == {"alpha", "beta"}
    assert {(e["project"], e["cr"]) for e in items} >= {("alpha", "CR-1"), ("beta", "CR-2")}
    assert all("project" not in e for d in alpha["days"] for e in d["items"])  # unchanged
    for key in ("merged", "dropped"):
        assert both["totals"][key] == alpha["totals"][key] + beta["totals"][key]
    assert both["totals"]["merged"] == TWO and both["totals"]["dropped"] == 1


def test_the_recent_activity_of_two_projects_is_the_newest_twenty_first_and_carries_no_cost(
    served: Served,
) -> None:
    def crs(first: int) -> list[dict[str, Any]]:
        return [
            entry(f"CR-{n}", ended=f"2026-11-{n:02d}T10:00:00Z", cost_usd=2.0)
            for n in range(first, first + 15)
        ]

    served.closed("alpha", "batch-00", crs(1))  # 1 to 15
    served.closed("beta", "batch-00", crs(8))  # 8 to 22
    got = history_page.feed(served.ctx, served.ctx.projects.all(), overview.FEED_ROWS)
    assert len(got) == ROWS == overview.FEED_ROWS
    assert [e["at"] for e in got] == sorted((e["at"] for e in got), reverse=True)
    assert {e["project"] for e in got} == {"alpha", "beta"}
    assert got[0]["cr"] == "CR-22" and all(set(e) == FEED_KEYS for e in got)
    assert "cost" not in json.dumps(got) and "rounds" not in json.dumps(got)
    data = overview.board_data(served.ctx)
    assert data["activity"] == got  # the board topic carries it

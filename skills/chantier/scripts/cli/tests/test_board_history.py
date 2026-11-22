"""The History page's answer (`history.get` and the `history` topic), on prepared planning folders,
with the CLI's clock pinned: the local day, the period's limits, the totals, the older records, the
running batch, the kept index, the protocol's refusals and the close's new keys."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from api_client import settled
from batch_helpers import changes
from test_board_prs import Board

from chantier.board import history_page
from chantier.board.api import ops, protocol, topics
from chantier.core import clock
from chantier.core.records import CrEntry, EventRecord
from chantier.history import cr_entry
from chantier.store.folder import FolderStore

PARIS, NEW_YORK = "Europe/Paris", "America/New_York"
OK, BAD, TWO = 200, 400, 2
TODAY = "2026-12-15T12:00:00Z"
DATE_TEXT = "a date YYYY-MM-DD between 2000-01-01 and 2100-12-31"
ZONE_TEXT = "an IANA time zone name, such as Europe/Paris"


class World:
    """A served project whose planning folder these helpers write."""

    def __init__(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(clock, "_fixed", [])
        clock.fix(TODAY)
        self.root = changes(repo)
        (self.root / "5-archives" / "batches").mkdir(parents=True, exist_ok=True)
        self.board = Board(repo, [], monkeypatch)

    def closed(self, name: str, crs: list[dict[str, Any]], state: str = "closed") -> None:
        data = {"schema": 1, "batch": name, "state": state, "crs": crs}
        path = self.root / "5-archives" / "batches" / f"{name}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        self.settle()

    def status(self, archive: str, text: str) -> None:
        folder = self.root / archive
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "STATUS.json").write_text(text, encoding="utf-8")
        self.settle()

    def running(self, crs: list[dict[str, Any]], events: list[dict[str, Any]]) -> None:
        folder = self.root / "4-batch"
        folder.mkdir(parents=True, exist_ok=True)
        data = {"schema": 1, "id": "batch-30", "host": "claude", "crs": crs}
        (folder / "batch.json").write_text(json.dumps(data), encoding="utf-8")
        self.events(events)

    def events(self, events: list[dict[str, Any]]) -> None:
        lines = [json.dumps({"actor": "t", **e}) for e in events]
        (self.root / "4-batch" / "events.jsonl").write_text("\n".join(lines) + "\n", "utf-8")
        self.settle()

    def settle(self) -> None:
        settled(self.board.ctx)  # what the file watch does once a change is quiet

    def get(self, period: str, on: str | None = None, tz: str = PARIS) -> dict[str, Any]:
        args = {
            "project": self.board.id,
            "period": period,
            "tz": tz,
            **({"date": on} if on else {}),
        }
        result = ops.call(self.board.ctx, "history.get", args)
        assert result.status == OK, result.error
        assert result.data is not None
        return result.data

    def refused(self, args: dict[str, Any]) -> str:
        result = ops.call(self.board.ctx, "history.get", {"project": self.board.id, **args})
        assert result.status == BAD
        return result.error or ""

    def topic(self, last: str | None = None, **args: Any) -> tuple[str, dict[str, Any] | None]:
        a = ops.checked(
            protocol.TOPIC_ARGS["history"], {"project": self.board.id, "tz": PARIS, **args}
        )
        assert not isinstance(a, str), a
        found = topics.read(self.board.ctx, "history", a, last)
        assert found is not None
        return found


@pytest.fixture
def world(repo: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    return World(repo, monkeypatch)


def entry(cr: str, result: str = "merged", **more: Any) -> dict[str, Any]:
    """A CR of a record written with the new keys."""
    return {
        "cr": cr,
        "title": f"Title of {cr}",
        "result": result,
        "archive": f"5-archives/{cr}",
        "pr": f"https://github.com/o/r/pull/{cr[3:]}",
        "rounds": 1,
        "cost_usd": 1.0,
        "cost_unpriced": {},
        "kind": "change",
        "ended": None,
        "shipped": None,
        "version": None,
        **more,
    }


@pytest.mark.parametrize(
    ("zone", "day", "start", "stop"),
    [
        (PARIS, "2026-10-25", "2026-10-24T22:00:00Z", "2026-10-25T23:00:00Z"),  # 25 hours
        (PARIS, "2026-11-21", "2026-11-20T23:00:00Z", "2026-11-21T23:00:00Z"),
        (NEW_YORK, "2026-11-21", "2026-11-21T05:00:00Z", "2026-11-22T05:00:00Z"),
    ],
)
def test_a_local_day_has_its_own_utc_limits(zone: str, day: str, start: str, stop: str) -> None:
    got = history_page.day_bounds(ZoneInfo(zone), date.fromisoformat(day))
    assert tuple(t.strftime(clock.FORMAT) for t in got) == (start, stop)
    assert got[0] == datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(UTC)


@pytest.mark.parametrize(
    ("zone", "at", "day"),
    [
        (PARIS, "2026-11-20T23:30:00Z", "2026-11-21"),
        (PARIS, "2026-10-25T22:30:00Z", "2026-10-25"),
        (PARIS, "2026-10-25T23:30:00Z", "2026-10-26"),
        (NEW_YORK, "2026-11-21T03:30:00Z", "2026-11-20"),
    ],
)
def test_an_event_is_in_its_local_day(world: World, zone: str, at: str, day: str) -> None:
    world.closed("batch-01", [entry("CR-1", ended=at)])
    got = world.get("day", day, zone)
    assert [d["day"] for d in got["days"]] == [day]
    assert got["totals"]["merged"] == 1
    other = world.get("week", day, zone)  # the same week holds it once, under that day
    assert [d["day"] for d in other["days"]] == [day]


@pytest.mark.parametrize(
    ("pinned", "period", "on", "expect"),
    [
        (
            TODAY,
            "week",
            "2026-11-21",
            ("2026-11-16", "2026-11-22", "2026-11-09", "2026-11-23"),
        ),
        (TODAY, "week", "2026-12-15", ("2026-12-14", "2026-12-20", "2026-12-07", None)),
        (
            TODAY,
            "month",
            "2026-11-21",
            ("2026-11-01", "2026-11-30", "2026-10-01", "2026-12-01"),
        ),
        (TODAY, "month", "2026-12-02", ("2026-12-01", "2026-12-31", "2026-11-01", None)),
        (TODAY, "day", None, ("2026-12-15", "2026-12-15", "2026-12-14", None)),
        (
            TODAY,
            "day",
            "2026-12-14",
            ("2026-12-14", "2026-12-14", "2026-12-13", "2026-12-15"),
        ),
        (
            "2026-12-15T23:30:00Z",
            "day",
            None,
            ("2026-12-16", "2026-12-16", "2026-12-15", None),
        ),
    ],
)
def test_the_periods_limits_and_neighbours(
    world: World, pinned: str, period: str, on: str | None, expect: tuple[str | None, ...]
) -> None:
    clock.fix(pinned)
    got = world.get(period, on)
    assert (got["date"], got["end"], got["prev"], got["next"]) == expect
    assert got["holds_today"] == (got["next"] is None)
    assert got["today"] == clock.parse(pinned).astimezone(ZoneInfo(PARIS)).date().isoformat()


def test_the_totals_and_the_cost(world: World) -> None:
    day = "2026-11-20T10:00:00Z"
    world.closed(
        "batch-01",
        [
            entry("CR-1", ended=day, shipped="2026-11-20T08:00:00Z", cost_usd=1.5),
            entry("CR-2", "dropped", ended=day, to="2-backlog/P2", pr=None, cost_usd=0.25),
            entry("CR-3", ended=day, kind="release", version="1.2.3", cost_usd=2.0),
            entry("CR-4", ended=day, cost_usd=None),
        ],
    )
    got = world.get("day", "2026-11-20")
    assert got["totals"] == {
        "merged": 2, "dropped": 1, "opened": 1, "releases": 1,
        "cost_usd": 3.75, "cost_partial": True,
    }  # fmt: skip
    (only,) = got["days"]
    assert only["counts"] == {"merged": 2, "dropped": 1, "opened": 1, "releases": 1}
    kinds = {e["cr"]: e for e in only["items"] if e["kind"] != "opened"}
    assert kinds["CR-3"]["kind"] == "release" and kinds["CR-3"]["version"] == "1.2.3"
    assert kinds["CR-2"]["to"] == "2-backlog/P2" and kinds["CR-2"]["folder"] == "5-archives/CR-2"
    assert [e["at"] for e in only["items"]] == sorted(
        (e["at"] for e in only["items"]), reverse=True
    )
    assert (got["undated"], got["unreadable"]) == (0, 0)


def test_an_older_record_is_read_from_its_archived_steps(world: World) -> None:
    old = {
        k: v for k, v in entry("CR-1").items() if k not in {"kind", "ended", "shipped", "version"}
    }
    two = {**old, "cr": "CR-2", "title": "Release", "archive": "5-archives/CR-2"}
    gone = {**old, "cr": "CR-3", "archive": "5-archives/CR-3"}
    dropped = {**old, "cr": "CR-4", "result": "dropped", "archive": "6-trash/CR-4"}
    bad = {**old, "cr": "CR-5", "archive": "5-archives/CR-5"}
    world.closed("batch-01", [old, two, gone, dropped, bad])
    world.status("5-archives/CR-1", json.dumps({"steps": [
        {"name": "Shipped", "at": "2026-11-18T09:00:00Z"},
        {"name": "Merged", "at": "2026-11-18T10:00:00Z"},
    ]}))  # fmt: skip
    world.status("5-archives/CR-2", json.dumps({"steps": [
        {"name": "Shipped", "at": ""}, {"name": "Merged", "at": "2026-11-18T11:00:00Z"},
    ]}))  # fmt: skip
    world.status("5-archives/CR-5", "{not json")
    (world.root / "5-archives" / "batches" / "batch-02.json").write_text("{", encoding="utf-8")
    got = world.get("day", "2026-11-18")
    seen = {(e["cr"], e["kind"], e["at"]) for e in got["days"][0]["items"]}
    assert seen == {
        ("CR-1", "opened", "2026-11-18T09:00:00Z"),
        ("CR-1", "merged", "2026-11-18T10:00:00Z"),
        ("CR-2", "merged", "2026-11-18T11:00:00Z"),
    }
    assert got["totals"]["releases"] == 0  # an unmarked record shows a plain merged CR
    assert (got["undated"], got["unreadable"]) == (3, 2)  # CR-3, CR-4, CR-5; one STATUS, one record


def test_the_running_batch_is_today_and_the_topic_moves_only_with_the_record(
    world: World,
) -> None:
    crs = [
        {"id": "CR-1", "title": "Merged now", "status": "merged", "kind": "change", "order": 1},
        {"id": "CR-2", "title": "Working", "status": "working", "order": 2},
    ]
    world.running(
        crs,
        [
            {"t": "2026-12-15T09:00:00Z", "kind": "ship", "cr": "CR-1", "pr": "https://x/pull/1"},
            {"t": "2026-12-15T10:00:00Z", "kind": "order", "cr": "CR-1", "order_kind": "merged"},
        ],
    )
    got = world.get("day")
    assert [(e["kind"], e["batch"]) for e in got["days"][0]["items"]] == [
        ("merged", "batch-30"), ("opened", "batch-30")
    ]  # fmt: skip
    rev, value = world.topic(period="day")
    assert value is not None
    clock.fix("2026-12-15T12:01:00Z")  # a minute later: `now` is not in the rev
    assert world.topic(rev, period="day") == (rev, None)
    past, _ = world.topic(period="day", date="2026-12-14")
    world.events([
        {"t": "2026-12-15T09:00:00Z", "kind": "ship", "cr": "CR-1", "pr": "https://x/pull/1"},
        {"t": "2026-12-15T10:00:00Z", "kind": "order", "cr": "CR-1", "order_kind": "merged"},
        {"t": "2026-12-15T11:00:00Z", "kind": "ship", "cr": "CR-2", "pr": "https://x/pull/2"},
    ])  # fmt: skip
    assert world.topic(rev, period="day")[0] != rev
    assert world.topic(past, period="day", date="2026-12-14") == (past, None)


def test_the_index_is_kept_while_the_planning_folder_holds(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = {
        k: v for k, v in entry("CR-1").items() if k not in {"kind", "ended", "shipped", "version"}
    }
    world.closed("batch-01", [old])
    world.status("5-archives/CR-1", json.dumps({"steps": [{"name": "Merged", "at": TODAY}]}))
    reads: list[str] = []
    real = FolderStore.read_text

    def count(self: FolderStore, rel: str, errors: str = "strict") -> str:
        reads.append(rel)
        return real(self, rel, errors)

    monkeypatch.setattr(FolderStore, "read_text", count)
    first = world.get("day")
    cold = [r for r in reads if r.endswith("STATUS.json")]
    reads.clear()
    assert first["totals"]["merged"] == 1 and cold  # read when the print is new
    world.get("week")
    assert not [r for r in reads if r.endswith("STATUS.json")]  # then not again
    world.closed("batch-02", [entry("CR-2", ended=TODAY)])  # a new record moves the print
    assert world.get("day")["totals"]["merged"] == TWO  # the change rebuilt the index


@pytest.mark.parametrize(
    ("args", "named", "text"),
    [
        ({"period": "year", "tz": PARIS}, "'period'", "day"),
        *[
            ({"period": "day", "tz": PARIS, "date": bad}, "'date'", DATE_TEXT)
            for bad in ("2026-13-01", "2026-2-1", "1999-12-31", "2101-01-01", "2026-11-21T00")
        ],
        *[
            ({"period": "day", "tz": bad}, "'tz'", ZONE_TEXT)
            for bad in ("Mars/Olympus", "../etc", "x" * 65)
        ],
    ],
)
def test_history_refuses_a_bad_period_date_or_zone_naming_the_field(
    world: World, args: dict[str, Any], named: str, text: str
) -> None:
    assert named in (said := world.refused(args)) and text in said
    on_topic = ops.checked(protocol.TOPIC_ARGS["history"], {"project": world.board.id, **args})
    assert isinstance(on_topic, str) and named in on_topic and text in on_topic


def test_a_valid_history_call_leaves_the_project_state_alone(world: World) -> None:
    before = ops.call(world.board.ctx, "project.state", {"project": world.board.id}).data
    world.get("month")
    after = ops.call(world.board.ctx, "project.state", {"project": world.board.id}).data
    assert before is not None and after is not None
    assert "history_page" not in after and set(before) == set(after)


def test_the_close_keeps_kind_ended_shipped_and_version(tmp_path: Path) -> None:
    c = CrEntry(id="CR-1", title="T", status="merged", kind="release", released="1.0.0")
    own = [
        EventRecord(t="2026-11-20T09:00:00Z", actor="a", kind="ship", cr="CR-1"),
        EventRecord(t="2026-11-20T10:00:00Z", actor="a", kind="ship", cr="CR-1"),
        EventRecord(
            t="2026-11-20T11:00:00Z", actor="a", kind="handback", cr="CR-1", result="merged"
        ),
        EventRecord(t="2026-11-20T08:00:00Z", actor="a", kind="ship", cr="CR-2"),
    ]
    got = cr_entry(c, {}, own)
    assert (got["kind"], got["ended"], got["shipped"], got["version"]) == (
        "release", "2026-11-20T11:00:00Z", "2026-11-20T09:00:00Z", "1.0.0"
    )  # fmt: skip
    bare = cr_entry(CrEntry(id="CR-9", status="cancelled"), {})
    assert (bare["kind"], bare["ended"], bare["shipped"], bare["version"]) == (
        "change",
        None,
        None,
        None,
    )
    dropped = cr_entry(
        CrEntry(id="CR-3", status="cancelled", left_to="3-ready"),
        {},
        [EventRecord(t="2026-11-20T12:00:00Z", actor="a", kind="cancel", cr="CR-3")],
    )
    assert dropped["ended"] == "2026-11-20T12:00:00Z" and dropped["to"] == "3-ready"

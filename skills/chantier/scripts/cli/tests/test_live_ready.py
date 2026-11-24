"""The live view's Agents and Ready boxes, its local times and the forge read."""

from __future__ import annotations

import io
import re
import threading
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from live_world import (
    HIGH,
    NOW,
    PARIS,
    TOKENS,
    WIDE,
    crs,
    drawn,
    fed,
    lease,
)

from chantier.clients.tui import screen
from chantier.clients.tui.link import Event, Idle, Linked, Refused
from chantier.clients.tui.model import Model
from chantier.clients.tui.parts import STATE_COLOURS
from chantier.clients.tui.times import since
from chantier.clients.tui.view import View
from chantier.commands import live as live_command
from chantier.core.errors import EXIT_EXTERNAL, ChantierError


@pytest.mark.parametrize(
    ("seconds", "text"),
    [(0, "0 s"), (46, "46 s"), (150, "2 min"), (3700, "1 h"), (86400, "1 day"),
     (3 * 86400 + 7200, "3 days"), (-5, "0 s")],
)  # fmt: skip
def test_since_rounds_down_and_never_runs_backwards(seconds: int, text: str) -> None:
    now = datetime(2030, 1, 1, tzinfo=UTC)
    then = (now - timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert since(then, now) == text


@pytest.mark.parametrize(
    ("now", "header", "t", "stamp"),
    [
        (NOW, "2030-01-01 01:00:00 UTC+01:00", "2029-12-31T23:50:00Z", "01-01 00:50:00"),
        ("2030-07-01T00:00:00Z", "2030-07-01 02:00:00 UTC+02:00", "2030-06-30T23:50:00Z",
         "07-01 01:50:00"),
        (NOW, "2030-01-01 01:00:00 UTC+01:00", "not a time", "----- --:--:--"),
    ],
)  # fmt: skip
def test_every_time_is_drawn_in_the_local_zone_with_its_utc_offset(
    now: str, header: str, t: str, stamp: str
) -> None:
    m = Model(zone=PARIS, clock=lambda: 0.0)
    m.feed(Linked("ws", now))
    assert m.clock_text() == header and m.stamp(t) == stamp


def _state(m: Model, seat: Any = None, **over: Any) -> None:
    """The project's state with the batch's fields changed."""
    batch = {"id": "batch-01", "state": "running", "mode": "batch", "crs": [],
             "stack_lease": None, "steering": "direct", **over}  # fmt: skip
    m.feed(Event("project:p", "project", {"batch": batch, "events": [], "seat": seat}, NOW))


def _lone() -> Model:
    m = Model(zone=PARIS, clock=lambda: 0.0)
    m.feed(Linked("ws", NOW))
    m.feed(Event("board", "board", {"projects": [{"id": "p"}]}, NOW))
    return m


@pytest.mark.parametrize(
    ("seat", "over", "lines"),
    [
        ({"title": "Chief 1"}, {}, ["Chief of Staff (seat)  Chief 1"]),
        ({"title": ""}, {}, ["Chief of Staff (seat)"]),
        (None, {"steering": "foreman", "heartbeat": "2029-12-31T23:57:00Z",
                "steering_wake_min": 10}, ["Foreman  beat 3 min ago"]),
        (None, {"steering": "foreman", "heartbeat": "2029-12-31T23:40:00Z",
                "steering_wake_min": 10}, ["Foreman  beat 20 min ago  late"]),
        (None, {"steering": "foreman", "heartbeat_stopped": NOW}, ["Foreman  heartbeat stopped"]),
        (None, {"steering": "foreman"}, ["Foreman"]),
        (None, {"crs": crs()}, ["Driver CR-1 coding"]),
        (None, {"stack_lease": lease()}, ["Stack driver"]),
        (None, {}, []),
        ({"title": "Chief"}, {"state": "paused", "steering": "foreman", "crs": crs()},
         ["Chief of Staff (seat)  Chief"]),
    ],
)  # fmt: skip
def test_agents_lists_the_seat_the_foreman_the_drivers_and_the_stack_driver(
    seat: Any, over: dict[str, Any], lines: list[str]
) -> None:
    m = _lone()
    _state(m, seat, **over)
    assert [x for _, x in m.agents()] == lines
    shown = "".join("".join(x) for x in m.agents())
    assert not {"steering", "live", "active"} & set(shown.split())
    out = io.StringIO()
    screen.plain(m, WIDE, HIGH, out)
    assert all(x[:20] in out.getvalue() for x in lines or ["none"])  # the box cuts the rest


def _pr(**over: Any) -> dict[str, Any]:
    facts = {"cr": "CR-2", "pr": "https://github.com/o/r/pull/7", "number": 7, "state": "open",
             "conflicting": False, "checking": False, "checks": "green", "ready_now": False,
             "why": None}  # fmt: skip
    return {**facts, **over}


def _with_prs(m: Model, *rows: dict[str, Any], **answer: Any) -> None:
    data = {"batch": "batch-01", "rows": list(rows), "error": None, **answer}
    m.feed(Event("prs:p:batch-01", "prs", data, NOW))


def test_wanted_names_the_batch_and_missing_leaves_the_prs_to_pending() -> None:
    m = _lone()
    assert not any(k.startswith("prs") for k, _, _ in m.wanted()) and m.pending_prs() == []
    _state(m, crs=crs())
    assert ("prs:p:batch-01", "prs", {"project": "p", "batch": "batch-01"}) in m.wanted()
    assert m.missing() == ["events p"] and m.pending_prs() == ["prs p"]
    m.feed(Event("events:p", "events", {"lines": []}, NOW))
    _state(m, state="paused")  # a paused batch is watched too
    assert m.missing() == [] and m.pending_prs() == ["prs p"]
    _with_prs(m)
    assert m.pending_prs() == [] and "p" in m.prs
    _state(m, id="batch-02")  # a new batch is a new key
    assert ("prs:p:batch-02", "prs", {"project": "p", "batch": "batch-02"}) in m.wanted()
    assert m.pending_prs() == ["prs p"]
    m.feed(Event("prs:p:batch-02", "prs", {"batch": "batch-02", "rows": []}, NOW))
    m.feed(Refused("prs:p:batch-02", 404, "no"))
    assert m.prs == {} and "p" not in m.dropped


@pytest.mark.parametrize(
    ("row", "word"),
    [
        (None, "not read"),
        (_pr(why="merged", state="merged"), "merged, not recorded"),
        (_pr(ready_now=True), "ready to merge"),
        (_pr(why="draft", state="draft"), "draft"),
        (_pr(why="closed", state="closed"), "closed"),
        (_pr(why="conflicting", conflicting=True), "conflicting"),
        (_pr(why="failing", checks="failing"), "checks failing"),
        (_pr(checking=True), "checks running"),
        (_pr(checks="none"), "to review"),
    ],
)
def test_ready_draws_each_state_word_with_the_pr_age_and_title(
    row: dict[str, Any] | None, word: str
) -> None:
    m = fed([0.0])
    if row:
        _with_prs(m, row)
    out = io.StringIO()
    screen.plain(m, WIDE, HIGH, out)
    line = next(x for x in out.getvalue().splitlines() if "12m" in x)
    assert word in line and "12m" in line and ("#7" in line) is bool(row)


def test_ready_follows_the_merge_order_filters_by_number_and_says_why_it_is_empty() -> None:
    m = _lone()
    rows = [{**crs()[1], "cr": f"CR-{i}", "title": f"Title {i}"} for i in (5, 6)]
    _state(m, crs=rows, merge_order=["CR-6", "CR-5"])
    _with_prs(m, _pr(cr="CR-5", number=5), _pr(cr="CR-6", number=6))
    out = io.StringIO()
    screen.plain(m, WIDE, HIGH, out)
    text = out.getvalue()
    assert text.index("Title 6") < text.index("Title 5")
    view = View()
    view.press("/"), [view.press(k) for k in ("#", "5", "enter")]
    out = io.StringIO()
    screen.plain(m, WIDE, HIGH, out, view)
    assert "Title 5" in out.getvalue() and "Title 6" not in out.getvalue()
    for text_, empty, kept in (("#9", "no PR matches #9", rows), ("", "no PR ready", [])):
        view = View()
        view.text = text_
        out = io.StringIO()
        _state(m, crs=kept, merge_order=["CR-6", "CR-5"])
        screen.plain(m, WIDE, HIGH, out, view)
        assert empty in out.getvalue()
    assert "no batch" in drawn(Model(zone=PARIS), WIDE)


def test_ready_titles_a_forge_error_and_marks_rows_not_read() -> None:
    m = fed([0.0])
    _with_prs(m, error="gh: no network")
    out = io.StringIO()
    screen.plain(m, WIDE, HIGH, out)
    assert "Ready  forge: gh: no network" in out.getvalue() and "not read" in out.getvalue()


def _interactive(m: Model) -> str:
    from rich.console import Console

    out = io.StringIO()
    console = Console(
        file=out, force_terminal=True, color_system="truecolor", width=WIDE, legacy_windows=False
    )
    console.print(screen.render(m, WIDE, HIGH))
    return out.getvalue()


@pytest.mark.parametrize(
    ("url", "linked"),
    [("https://github.com/o/r/pull/7", True), ("file:///etc/pull/7", False)],
)
def test_the_interactive_screen_links_the_pr_and_colours_the_state_words(
    url: str, linked: bool
) -> None:
    m = _lone()
    rows = [{**crs()[1], "cr": f"CR-{i}", "title": f"Title {i}"} for i in (5, 6)]
    _state(m, crs=rows, merge_order=["CR-5", "CR-6"])
    _with_prs(m, _pr(cr="CR-5", number=5, pr=url, ready_now=True), _pr(cr="CR-6", pr=url))
    text = _interactive(m)
    assert ("\x1b]8;" in text) is linked and (url in text) is linked
    assert "38;2;47;158;107" in text and "38;2;163;167;175" in text  # ready, queued
    assert "ready to merge" in text and "to review" in text


def test_the_state_colours_are_the_boards() -> None:
    found = re.findall(
        r"^\s*--state-([a-z]+):\s*(#[0-9a-f]{6});", TOKENS.read_text(encoding="utf-8"), re.M
    )
    assert dict(found) == STATE_COLOURS and len(found) == len(STATE_COLOURS)


class Feed:
    """A stand-in link: the given items once, then idle."""

    def __init__(self, items: list[Any]) -> None:
        self.base, self.sent = "http://127.0.0.1:9/", items

    def want(self, _wants: Any) -> None:
        pass

    def items(self) -> Iterator[Any]:
        yield from self.sent
        while True:
            threading.Event().wait(0.05)
            yield Idle()


def _first_answers(skip: str) -> list[Any]:
    m = fed([0.0])
    project = {"batch": {"id": "batch-01", "state": "running", "crs": crs()}, "events": []}
    items = [
        Event("board", "board", {"projects": [{"id": "p"}]}, NOW),
        Event("project:p", "project", project, NOW),
        Event("events:p", "events", {"lines": []}, NOW),
    ]
    assert m
    return [x for x in items if x.topic != skip]


def test_once_prints_with_the_prs_not_read_but_exits_4_for_any_other_missing_answer(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(live_command, "ONCE_S", 0.5)
    feeds: list[Any] = [Feed(_first_answers("none"))]  # no `prs` ever
    live_command.once(feeds, [Model(zone=PARIS)])
    out = capsys.readouterr().out
    assert "not read" in out and "Ready" in out and "\x1b" not in out
    with pytest.raises(ChantierError, match="events p") as e:
        feeds = [Feed(_first_answers("events"))]
        live_command.once(feeds, [Model(zone=PARIS)])
    assert e.value.code == EXIT_EXTERNAL


def _many(panel: str) -> Model:
    """A board with more Ready rows (12) or more Tasks lines (16) than their box holds."""
    m = _lone()
    if panel == "ready":
        rows = [{**crs()[1], "cr": f"CR-{i}", "title": f"Title {i:02d}"} for i in range(1, 13)]
    else:
        rows = [{**crs()[2], "cr": f"CR-{i}", "title": f"Title {i:02d}"} for i in range(1, 9)]
    _state(m, crs=rows, merge_order=[r["cr"] for r in rows])
    _with_prs(m)
    m.feed(Event("events:p", "events", {"lines": [{"seq": i, "t": "2029-12-31T23:30:00Z",
              "source": "hub", "text": f"flow {i:02d}"} for i in range(1, 6)]}, NOW))  # fmt: skip
    return m


def _text(m: Model, view: View, width: int = WIDE) -> str:
    out = io.StringIO()
    screen.plain(m, width, HIGH, out, view)
    return out.getvalue()


@pytest.mark.parametrize(
    ("panel", "tabs", "first", "last"),
    [("ready", 1, "Title 01", "Title 12"), ("tasks", 2, "Title 01", "Title 08")],
)
def test_a_panel_with_more_rows_than_its_box_scrolls_alone_and_keeps_its_offset(
    panel: str, tabs: int, first: str, last: str
) -> None:
    m, view = _many(panel), View()
    start = _text(m, view)
    assert first in start and last not in start
    for _ in range(tabs):
        view.press("tab")
    assert view.active == panel
    view.press("down")
    one = _text(m, view)
    assert first not in one and "Title 02" in one and "flow 05" in start and "flow 05" in one
    view.press("pgdn")
    assert last in _text(m, view)
    view.press("pgdn"), view.press("pgdn")  # clamped to the last full page
    assert last in _text(m, view)
    view.press("home")
    assert first in _text(m, view)
    view.press("end"), view.press("btab")  # the offset stays with the panel
    for _ in range(tabs):
        view.press("tab")
    assert last in _text(m, view) and first not in _text(m, view)
    view.press("/"), view.press("x"), view.press("enter")  # a new filter starts every box again
    assert view.offsets == {}


def test_a_panel_whose_content_fits_does_not_move() -> None:
    m, view = fed([0.0]), View()
    view.press("tab")
    before = _text(m, view)
    for key in ("down", "pgdn", "end", "up"):
        view.press(key)
        assert _text(m, view) == before


def _title_seen(text: str) -> int:
    return max(len(x) for x in re.findall(r"A long title[a-zA-Z ]*", text))


def test_a_maximized_ready_row_shows_a_title_cut_later_than_at_the_boxs_width() -> None:
    m, view = _lone(), View()
    title = "A long title of a CR that the narrow box cuts " * 2
    _state(m, crs=[{**crs()[1], "title": title}])
    _with_prs(m, error="gh: " + "no network " * 5)
    view.press("tab")
    normal = _text(m, view)
    view.press("m")
    full = _text(m, view)
    assert _title_seen(full) > _title_seen(normal) and "gh: no network no network" in full
    assert "forge: gh: no network no network no network no network" in full
    assert "Ready  forge" in normal and "no network no network no network no network" not in normal

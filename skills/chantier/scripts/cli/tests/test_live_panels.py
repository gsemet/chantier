"""The live view's active panel, Tab, the maximized screen, the column widths and the Flow's `Ago`
column."""

from __future__ import annotations

import io
import re

import pytest
from live_world import HIGH, NARROW, WIDE, fed, journal, keyed, numbered, watching

from chantier.clients.tui import screen
from chantier.clients.tui.model import Model
from chantier.clients.tui.view import MAXIMIZE, View

FLOW_BOX = "╭─ ▸ Flow "  # the active Flow's box, as drawn


def _marked(text: str) -> list[str]:
    """The titles that carry the active marker in the plain text of a screen."""
    return re.findall(r"▸ (\w+)", text)


def _plain(m: Model | list[Model], view: View, width: int = WIDE) -> str:
    out = io.StringIO()
    screen.plain(m, width, HIGH, out, view)
    return out.getvalue()


def test_the_flow_is_active_at_the_start_and_is_not_maximized() -> None:
    m, view = fed([0.0]), View()
    assert view.active == "flow" and not view.maximized
    assert _marked(_plain(m, view)) == ["Flow"]  # `--once` prints it too


@pytest.mark.parametrize(
    ("width", "cycle"),
    [
        (WIDE, ["ready", "tasks", "projects", "agents", "flow"]),
        (NARROW, ["ready", "tasks", "flow", "ready"]),
    ],
)
def test_tab_cycles_the_drawn_panels_and_shift_tab_goes_back(width: int, cycle: list[str]) -> None:
    m, view = fed([0.0]), View()
    _plain(m, view, width)  # the drawing tells the view which panels it draws
    for want in cycle:
        view.press("tab")
        assert view.active == want
        assert _marked(_plain(m, view, width)) == [want.capitalize()]
    view.press("btab")
    assert view.active == cycle[-2]
    for name in ("/", "tab", "btab"):  # typing a filter: Tab adds nothing and moves nothing
        view.press(name)
    assert view.typing == "" and view.active == cycle[-2]
    view.press("esc")
    view.press("?")
    assert not view.press("tab") and not view.help and view.active == cycle[-2]


def test_a_resize_that_hides_the_active_panel_makes_the_flow_active() -> None:
    m, view = fed([0.0]), View()
    _plain(m, view)
    view.active = "agents"
    assert _marked(_plain(m, view, NARROW)) == ["Flow"] and view.active == "flow"


def test_the_flow_draws_the_newest_line_first() -> None:
    m, view = fed([0.0]), View()
    journal(m, numbered(1, 30))
    text = keyed(m, view)
    assert text.index("took CR-1") < text.index("line 29") < text.index("line 17")


def test_maximize_shows_the_active_panel_alone_and_the_same_key_restores() -> None:
    m, view = fed([0.0]), View()
    journal(m, numbered(1, 30))
    normal = keyed(m, view)
    view.press(MAXIMIZE)
    full = keyed(m, view)
    assert view.maximized and _marked(full) == ["Flow"] and " Ready " in normal
    assert not any(f" {x} " in full for x in ("Projects", "Agents", "Ready", "Tasks"))
    view.press("tab")  # the screen stays maximized on the next panel
    ready = keyed(m, view)
    assert view.maximized and _marked(ready) == ["Ready"] and "line 29" not in ready
    assert " Flow " not in ready and "Ready one" in ready
    view.press("?"), view.press("x")  # the help returns to the maximized panel
    assert view.maximized and _marked(keyed(m, view)) == ["Ready"]
    view.press("esc")  # Esc does not restore
    assert view.maximized
    view.press(MAXIMIZE)
    assert not view.maximized and keyed(m, view).count("▸") == 1 and " Tasks " in keyed(m, view)


def test_the_ago_column_is_narrow_and_right_aligned() -> None:
    m, view = fed([0.0]), View()
    journal(m, [
        {"seq": 1, "t": "2029-12-31T23:58:00Z", "source": "hub", "text": "event two"},
        {"seq": 2, "t": "2029-12-31T23:14:00Z", "source": "hub", "text": "event forty"},
    ])  # fmt: skip
    clock = keyed(m, view).splitlines()
    view.ago = True
    ago = keyed(m, view).splitlines()
    two, forty = (next(r for r in ago if f"event {x}" in r) for x in ("two", "forty"))
    assert two.index(" 2 min") + 6 == forty.index("46 min") + 6  # right-aligned, 6 wide
    clocked = next(r for r in clock if "event two" in r)
    assert clocked.index("event") - two.index("event") == 14 - 6  # the freed columns: the Event's


def _columns(text: str) -> tuple[int, int | None, int, int]:
    """The widths as drawn: the left column's (what stands before the Flow's box), then those of
    the Flow's Project (None when not drawn), Who and Event, read from its header row."""
    lines = text.splitlines()
    at, top = next((i, x) for i, x in enumerate(lines) if FLOW_BOX in x)
    left = top.index(FLOW_BOX)
    right = top.index("╮", left)
    head = lines[at + 1][left : right + 1]
    who, event = head.index("Who"), head.index("Event")
    project = who - head.index("Project") - 1 if "Project" in head else None
    return left, project, event - who - 1, right - left - 1 - event


@pytest.mark.parametrize(
    ("case", "width", "maximized", "left", "project", "who", "event"),
    [
        # everything fits: the defaults, and Event takes the rest
        ("one", 164, False, 42, None, 15, 43),
        ("one", 141, False, 42, None, 15, 20),
        ("projects", 162, False, 42, 20, 15, 20),
        ("boards", 164, False, 42, 22, 15, 20),
        # the left column gives way first, then Who, then Project; Event keeps 20
        ("one", 140, False, 41, None, 15, 20),
        ("one", 127, False, 28, None, 15, 20),
        ("one", 126, False, 28, None, 14, 20),
        ("one", 122, False, 28, None, 10, 20),
        ("projects", 161, False, 41, 20, 15, 20),
        ("projects", 148, False, 28, 20, 15, 20),
        ("projects", 143, False, 28, 20, 10, 20),
        ("projects", 142, False, 28, 19, 10, 20),
        ("projects", 133, False, 28, 10, 10, 20),
        ("boards", 135, False, 28, 12, 10, 20),
        # one column under the threshold: no left column, Project then Who take back what fits
        ("one", 121, False, 0, None, 15, 42),
        ("projects", 132, False, 0, 20, 15, 32),
        ("boards", 134, False, 0, 22, 15, 32),
        ("projects", 117, False, 0, 20, 12, 20),
        ("projects", 110, False, 0, 15, 10, 20),
        ("boards", 100, False, 0, 12, 10, 13),  # Event under 20 only when nothing else can give
        # a maximized Flow spans the body
        ("projects", 90, True, 0, 20, 15, 34),
        ("projects", 70, True, 0, 19, 10, 20),
    ],
)
def test_a_narrower_screen_closes_the_columns_up_before_the_left_one_goes(  # noqa: PLR0913, PLR0917
    case: str,
    width: int,
    maximized: bool,
    left: int,
    project: int | None,
    who: int,
    event: int,
) -> None:
    view = View()
    view.maximized = maximized
    text = _plain(watching(case), view, width)
    assert _columns(text) == (left, project, who, event)
    assert (" Projects " in text) is bool(left)


@pytest.mark.parametrize(("width", "left"), [(122, 28), (121, 0)])
def test_the_ago_column_never_shows_or_hides_the_left_column(width: int, left: int) -> None:
    view = View()
    view.ago = True
    text = _plain(fed([0.0]), view, width)
    assert " Ago " in text and " Time " not in text
    assert text.splitlines()[2].index(FLOW_BOX) == left

"""The live view's active panel, Tab, the maximized screen and the Flow's `Ago` column."""

from __future__ import annotations

import io
import re

import pytest
from live_world import HIGH, NARROW, WIDE, fed, journal, keyed, numbered

from chantier.clients.tui import screen
from chantier.clients.tui.model import Model
from chantier.clients.tui.view import MAXIMIZE, View


def _marked(text: str) -> list[str]:
    """The titles that carry the active marker in the plain text of a screen."""
    return re.findall(r"▸ (\w+)", text)


def _plain(m: Model, view: View, width: int = WIDE) -> str:
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

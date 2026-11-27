"""The mouse of `chantier live`, with no Rich and no `blessed` in it: `term` is a `blessed.Terminal`
or a stand-in, and an event is one of its keystrokes (`name`, and `mouse_xy`, the column and the
row from 0).

`tracked` holds mouse tracking on when the terminal handles it. `handle` takes the events: a
left press on one of the two panel borders where a side column meets the Flow starts a drag, which
moves the border with the pointer, and whose release keeps the dragged column's width and writes
both widths to `live.json`; a key press drops the drag, nothing written. The wheel moves as the
`up` and `down` keys do."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import Any

from chantier.clients.tui.model import Model
from chantier.clients.tui.view import Drag, View
from chantier.clients.tui.widths import column_widths, drag_width, save

MOUSE_TIMEOUT_S = 1.0  # each question to the terminal about the mouse waits at most this long
WHEEL = {"MOUSE_SCROLL_UP": "up", "MOUSE_SCROLL_DOWN": "down"}  # with no modifier held


@contextlib.contextmanager
def tracked(term: Any, view: View) -> Iterator[None]:
    """Mouse tracking while the block runs, when the terminal (None: no keyboard) handles it; it
    is off again when the block is left, however it is. The terminal is asked on entering, so enter
    once the first screen is drawn; the keys typed meanwhile stay in the terminal's input."""
    asked: dict[str, Any] = {"clicks": True, "report_drag": True, "timeout": MOUSE_TIMEOUT_S}
    if term is None or not term.does_mouse(**asked):
        yield
        return
    with term.mouse_enabled(**asked):
        view.tracking = True
        yield


def _border(models: list[Model], view: View, x: int, width: int) -> str | None:
    """The side column whose border with the Flow stands at the column `x`: either of the two
    panel borders there."""
    drawn = column_widths(models, width, view)
    if drawn.left and x in (drawn.left - 1, drawn.left):
        return "left"
    # the right column's first column; the Flow takes at least one
    first = drawn.left + max(width - drawn.left - drawn.right, 1)
    return "right" if x in (first - 1, first) else None


def _press(models: list[Model], view: View, at: tuple[int, int], width: int, body: range) -> None:
    x, y = at
    shown = not (view.help or view.maximized) and y in body
    side = _border(models, view, x, width) if shown else None
    drawn = column_widths(models, width, view)
    both = (drawn.left, drawn.right)
    view.drag = Drag(side, x, both, both) if side else None  # a press ends an unfinished drag


def _moved(models: list[Model], drag: Drag, x: int, width: int) -> Drag:
    """The drag with the pointer at the column `x`."""
    by = x - drag.x
    left, right = drag.start
    if drag.side == "left":
        left = drag_width(models, width, drag.side, drag.start, left + by)
    else:
        right = drag_width(models, width, drag.side, drag.start, right - by)
    return drag._replace(now=(left, right))


def _release(view: View, drag: Drag) -> None:
    """End the drag: when the dragged column is not as wide as at the start, keep that width and
    write both kept widths."""
    view.drag = None
    at = 0 if drag.side == "left" else 1
    if drag.now[at] == drag.start[at]:
        return
    if drag.side == "left":
        view.left = drag.now[at]
    else:
        view.right = drag.now[at]
    if view.file is not None:
        save(view.file, view.left, view.right)


def handle(models: list[Model], view: View, key: Any, width: int, body: range) -> bool:
    """One keystroke the view has no name for (a mouse event, a key with no use here, or the empty
    one of a wait that ran out), on a screen `width` columns wide whose body is on the rows `body`;
    true when what is drawn changes. A key drops a drag under way, as every key does; a mouse event
    that is no left button or wheel event does nothing."""
    name = key.name or ""
    if not name.startswith("MOUSE_"):
        dropped = bool(key) and view.drag is not None
        if dropped:
            view.drag = None
        return dropped
    if name in WHEEL:
        return view.wheel(WHEEL[name])
    before = column_widths(models, width, view)
    if name == "MOUSE_LEFT":
        _press(models, view, key.mouse_xy, width, body)
    elif view.drag is not None and name.endswith(("LEFT_MOTION", "LEFT_RELEASED")):
        # a modifier pressed during the drag changes the name's start only
        view.drag = _moved(models, view.drag, key.mouse_xy[0], width)
        if name.endswith("RELEASED"):
            _release(view, view.drag)
    return column_widths(models, width, view) != before

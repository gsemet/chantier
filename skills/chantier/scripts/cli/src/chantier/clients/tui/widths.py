"""The widths of `chantier live`'s columns, with no Rich in it: those a terminal draws, those a drag
may give a side column, and `live.json`, which keeps the two side columns' widths.

The left and the right column are kept at the widths last dragged (`LEFT_W` and `RIGHT_W`,
`parts.py`, until then), the Flow's `Who` is `WHO_W` and its `Project` `PROJECT_W` wide. A screen
too narrow for them gives way in this order, so that the Flow's `Event` keeps `EVENT_MIN`: the
right column down to `RIGHT_FLOOR`, the left one down to `LEFT_FLOOR`, then `Who` down to
`WHO_MIN`, then `Project` down to `PROJECT_MIN`; when even that does not fit, the left column is
not drawn. A side column kept under its floor is drawn as kept. With no left column, `Project`
then `Who` take back what fits, then the right column does, up to its kept width. A drag stops at
`LEFT_MIN` or `RIGHT_MIN`, and where the central column reaches its own minimum."""

from __future__ import annotations

import contextlib
import json
import os
import secrets
from pathlib import Path
from typing import NamedTuple

from chantier.clients.tui.model import Model
from chantier.clients.tui.parts import LEFT_W, RIGHT_W, watched
from chantier.clients.tui.view import View
from chantier.core.errors import EXIT_PRECONDITION, ChantierError

PROJECT_W, WHO_W = 20, 15  # the Flow's `Project` and `Who` where they fit
TIME_W = 14  # the Flow's `Time`; counted too when `Ago` takes its place
PROJECT_MIN, WHO_MIN, EVENT_MIN = 10, 10, 20  # how far a narrow screen closes the Flow up
LEFT_FLOOR, RIGHT_FLOOR = 28, 44  # how far it closes the side columns up
LEFT_MIN, RIGHT_MIN = 20, 30  # how narrow a drag, or `live.json`, makes the side columns
LABEL_W = 2  # a board's label in `Project` (`a/`), with several boards
FLOW_FRAME, GAP = 4, 1  # the Flow box's borders and padding; between two columns of its table

FILE = "live.json"  # in the user's chantier configuration folder, which the caller gives
KEPT = {"left": (LEFT_W, LEFT_MIN), "right": (RIGHT_W, RIGHT_MIN)}  # each key: default, minimum


class Widths(NamedTuple):
    """The widths a screen draws: the left column's (0: not drawn), the right column's and the
    Flow's `Project` (the board's label included) and `Who`."""

    left: int
    right: int
    project: int
    who: int


def central_min(models: list[Model]) -> int:
    """The central column at its narrowest: the Flow with `Who` and `Project` closed up and
    `EVENT_MIN` for `Event`."""
    least = FLOW_FRAME + TIME_W + GAP + WHO_MIN + GAP + EVENT_MIN
    if len(watched(models)) > 1:
        least += PROJECT_MIN + (LABEL_W if len(models) > 1 else 0) + GAP
    return least


def _within(wanted: int, low: int, high: int) -> int:
    return max(low, min(wanted, high))


def column_widths(
    models: list[Model], width: int, view: View | None = None, maximized: bool = False
) -> Widths:
    """The widths for a terminal `width` wide, with the side widths the view keeps; during a drag
    the side columns are as the drag has them. The side widths are the normal layout's, which says
    what panels there are; with `maximized`, the Flow's are those of a Flow over the whole body."""
    view = view or View()
    several = len(watched(models)) > 1
    grows = WHO_W - WHO_MIN + (PROJECT_W - PROJECT_MIN if several else 0)
    spare = width - central_min(models)  # for the side columns, then for `Project` and `Who`
    floor = min(view.left, LEFT_FLOOR), min(view.right, RIGHT_FLOOR)
    if view.drag:
        left, right = view.drag.now
    elif spare >= sum(floor):
        right = _within(spare - grows - view.left, floor[1], view.right)
        left = _within(spare - grows - right, floor[0], view.left)
    else:
        left, right = 0, _within(spare - grows, floor[1], view.right)
    extra = spare if maximized else spare - left - right
    more = _within(extra, 0, PROJECT_W - PROJECT_MIN) if several else 0
    who = WHO_MIN + _within(extra - more, 0, WHO_W - WHO_MIN)
    label = LABEL_W if len(models) > 1 else 0
    return Widths(left, right, PROJECT_MIN + more + label, who)


def drag_width(
    models: list[Model], width: int, side: str, start: tuple[int, int], wanted: int
) -> int:
    """The width a drag gives the `side` column for the `wanted` one, `start` being the side widths
    drawn when it began: no less than the column's minimum, and no more than leaves the central
    column its own beside the other column. Where the central column was under its minimum at the
    start, the dragged column may narrow, never widen."""
    at = 0 if side == "left" else 1
    most = max(start[at], width - central_min(models) - start[1 - at])
    return _within(wanted, KEPT[side][1], most)


def _bad(where: Path, fault: str) -> ChantierError:
    return ChantierError(f"live: {where}: {fault}: fix or delete it", EXIT_PRECONDITION)


def load(where: Path) -> tuple[int, int]:
    """The left and right widths `live.json` keeps; the default for an absent key, and for both
    when the file is not there. Anything else is refused: no default stands in for it."""
    try:
        data = json.loads(where.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        data = {}
    except (OSError, ValueError) as e:
        why = e.strerror if isinstance(e, OSError) else str(e).splitlines()[0]
        raise _bad(where, why or "unreadable") from e
    if not isinstance(data, dict):
        raise _bad(where, "not an object")
    for key, value in data.items():
        if key not in KEPT:
            raise _bad(where, f"unknown key {key!r}")
        if isinstance(value, bool) or not isinstance(value, int):
            raise _bad(where, f"`{key}` is not an integer")
        if value < KEPT[key][1]:
            raise _bad(where, f"`{key}` is under {KEPT[key][1]}")
    return data.get("left", LEFT_W), data.get("right", RIGHT_W)


def save(where: Path, left: int, right: int) -> None:
    """Write both widths atomically (a temporary file in the folder, with the mode the user's
    umask gives, then a replace); the folder is made when it is not there."""
    temporary = where.with_name(f".live-{os.getpid()}-{secrets.token_hex(4)}.tmp")
    try:
        where.parent.mkdir(parents=True, exist_ok=True)
        with temporary.open("x", encoding="utf-8", newline="\n") as out:
            out.write(json.dumps({"left": left, "right": right}) + "\n")
        os.replace(temporary, where)
    except OSError as e:
        raise ChantierError(f"live: {where}: not written: {e.strerror}", EXIT_PRECONDITION) from e
    finally:
        with contextlib.suppress(OSError):  # gone once it replaced the file
            temporary.unlink()

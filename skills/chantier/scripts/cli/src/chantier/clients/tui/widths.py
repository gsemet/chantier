"""The widths of `chantier live`'s columns on a terminal, with no Rich in it.

The left column is `LEFT_W` wide (`parts.py`), the Flow's `Who` `WHO_W` and its `Project`
`PROJECT_W`. A screen too narrow for them closes them up in that order, each down to its minimum,
so that the Flow's `Event` keeps `EVENT_MIN`; when even the minima do not fit, the left column is
not drawn."""

from __future__ import annotations

from typing import NamedTuple

from chantier.clients.tui.model import Model
from chantier.clients.tui.parts import LEFT_W, RIGHT_W, watched

PROJECT_W, WHO_W = 20, 15  # the Flow's `Project` and `Who` where they fit
TIME_W = 14  # the Flow's `Time`; counted too when `Ago` takes its place
LEFT_MIN, PROJECT_MIN, WHO_MIN, EVENT_MIN = 28, 10, 10, 20  # how far a narrow screen closes up
LABEL_W = 2  # a board's label in `Project` (`a/`), with several boards
FLOW_FRAME, GAP = 4, 1  # the Flow box's borders and padding; between two columns of its table


class Widths(NamedTuple):
    """The widths a screen draws: the left column's (0: not drawn) and the Flow's `Project`
    (the board's label included) and `Who`."""

    left: int
    project: int
    who: int


def column_widths(models: list[Model], width: int, maximized: bool = False) -> Widths:
    """The widths for a terminal `width` wide. The left column's is the normal layout's, which
    says what panels there are; with `maximized`, the Flow's are those of a Flow over the whole
    body."""
    several = len(watched(models)) > 1
    label = LABEL_W if len(models) > 1 else 0
    # the Flow at its narrowest, and what `Who` and `Project` may grow above it
    least = FLOW_FRAME + TIME_W + GAP + WHO_MIN + GAP + EVENT_MIN
    grows = WHO_W - WHO_MIN
    if several:
        least += PROJECT_MIN + label + GAP
        grows += PROJECT_W - PROJECT_MIN
    spare = width - RIGHT_W - least  # for the left column, then for `Project` and `Who`
    left = max(LEFT_MIN, min(LEFT_W, spare - grows)) if spare >= LEFT_MIN else 0
    extra = width - least if maximized else spare - left
    more = max(0, min(extra, PROJECT_W - PROJECT_MIN)) if several else 0
    who = WHO_MIN + max(0, min(extra - more, WHO_W - WHO_MIN))
    return Widths(left, PROJECT_MIN + more + label, who)

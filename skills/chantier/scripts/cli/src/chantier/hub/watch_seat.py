"""The watcher's seat rule: with no server running, the seat's session it starts a board for."""

from __future__ import annotations

import re

from chantier.core.errors import ChantierError
from chantier.core.repo import Repo
from chantier.core.seat import read_seat
from chantier.hub import autostart
from chantier.hub.watch_lines import (
    NO_KEY,
    NO_SEAT,
    NO_TRANSCRIPT,
    SEAT_LINE,
    UNREADABLE_SEAT,
    Ended,
)


def seat_rule(repo: Repo, session: str, texts: dict[str, str]) -> str:
    """The seat's session this watcher starts the board for, else the end that says why, in this
    order: no session key, no seat, a seat with no transcript, another's."""
    if session == autostart.NONE:
        raise Ended(NO_KEY.format(**texts))
    try:
        seat = read_seat(repo)
    except ChantierError as e:
        raise Ended(UNREADABLE_SEAT.format(**texts, error=e)) from e
    if seat is None:
        raise Ended(NO_SEAT.format(**texts))
    if not re.sub(r"[^A-Za-z0-9-]", "", seat.transcript or ""):
        raise Ended(NO_TRANSCRIPT.format(**texts))
    if seat.session and autostart.holds_seat(seat.transcript):
        return seat.session
    raise Ended(SEAT_LINE.format(**texts), 0)

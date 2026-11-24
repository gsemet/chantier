"""The watcher's lines (`watch.py`): how it tells an event the server gave it, its last lines when
it cannot link or ends, and the start line's clause for a board of another version, one constant
each, so the tests read them from here."""

from __future__ import annotations

from typing import Any

from chantier.hub import journal, schemas
from chantier.hub.schemas import PUBLISHED

FAILED = 1
SEAT_LINE = "watch: the seat of {project} is another session's now; ended"
NO_KEY = (
    "watch: this run has no session key (the host gave no session id), so it cannot hold the "
    "seat of {project}; no board started; ended: for the Chief of Staff, start the watcher from "
    "the session's own background command, or the board by hand ({cli} serve --seat <session id> "
    "--forge-always)"
)
NO_SEAT = (
    "watch: no seat for {project}, so no board started; ended: for the Chief of Staff, take the "
    "seat ({cli} seat take <session id>), then start again: {watch}"
)
NO_TRANSCRIPT = (
    "watch: the seat of {project} records no session transcript, so it cannot be told this "
    "session's; no board started; ended: for the Chief of Staff, take the seat again from this "
    "session ({cli} seat take <session id>), then start again: {watch}"
)
UNREADABLE_SEAT = (
    "watch: the seat of {project} cannot be read ({error}), so no board started; ended: for the "
    "Chief of Staff, take the seat again ({cli} seat take <session id>), then start again: {watch}"
)
NOT_STARTED = (
    "watch: the board did not start within 20 s: for the Chief of Staff, start it with {cli} "
    "serve --seat {session} and read its error"
)
BAD_KEY = (
    "watch: the board at {where} refused the key of server.json: for the Chief of Staff, restart "
    "it: stop it ({stop}), then start again: {watch}"
)
REFUSED = (
    "watch: the board at {where} refused this watcher: {sentence}: for the Chief of Staff, "
    "restart it to run this version: stop it ({stop}), then start again: {watch}"
)
NOT_SERVED = (
    "watch: the board at {where} does not serve the events of {project} ({error}): for the Chief "
    "of Staff, restart it: stop it ({stop}), then start again: {watch}"
)
NO_BOARD = (
    "; no board started: a chantier dev session holds its seat and its build serves this "
    "surface; linking when its board runs"
)
OTHER_VERSION = "; board is chantier {version}: restart it to run this version"
EVENTS_END = (
    "watch: {name} still running: for the Chief of Staff, start again in the background now: "
    "{watch}"
)
IDLE_END = (
    "watch: no event for {name} in 2 h; ended, so a session that has ended leaves no board "
    "running: for the Chief of Staff, start again in the background now: {watch}"
)
STREAM_TOLD = (
    "watch: {name} told up to cursor {n}; still watching (if this watcher stops, start again: "
    "{watch})"
)


class Ended(Exception):
    """The watcher ends with this last line and this exit code."""

    def __init__(self, line: str, code: int = FAILED) -> None:
        super().__init__(line)
        self.line, self.code = line, code


def told(e: dict[str, Any]) -> str:
    """The line an event is told by: the sentence the server gives (as `text`) a line of a
    published type, not newer, addressed, whose payload it accepts; else its type's text."""
    type_, text = e.get("type"), e.get("text")
    if (
        isinstance(type_, str)
        and type_ in PUBLISHED
        and not journal.newer(e)
        and e.get("audience")
        and isinstance(text, str)
        and schemas.check(type_, {k: v for k, v in e.items() if k not in journal.HEADER}) is None
    ):
        return text
    return journal.event_text(e)

"""The clock: UTC stamps and ages."""

from __future__ import annotations

from datetime import UTC, datetime

FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_fixed: list[datetime] = []  # at most one: the instant `--clock` pins for this process


def fix(timestamp: str) -> None:
    """Make the process answer as if it were this instant (`YYYY-MM-DDTHH:MM:SSZ`, UTC):
    `now`, `stamp` and `age_minutes` all follow it. Raises ValueError on another shape."""
    _fixed[:] = [datetime.strptime(timestamp, FORMAT).replace(tzinfo=UTC)]


def _current() -> datetime:
    return _fixed[0] if _fixed else datetime.now(UTC)


def now() -> str:
    return _current().strftime(FORMAT)


def stamp() -> str:
    """The date in an archive's name: its order is the date's."""
    return _current().strftime("%y%m%d-%H%M")


def age_minutes(ts: str | None) -> float | None:
    if not ts:
        return None
    then = datetime.strptime(ts, FORMAT).replace(tzinfo=UTC)
    return (_current() - then).total_seconds() / 60

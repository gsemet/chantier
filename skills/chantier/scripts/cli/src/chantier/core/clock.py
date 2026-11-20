"""The clock: UTC stamps and ages."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

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


def real_now() -> str:
    """The wall clock's instant, whatever `--clock` pins: for the moment a process started, which
    the OS fixes (a liveness check compares it with the process's creation time)."""
    return datetime.now(UTC).strftime(FORMAT)


def stamp() -> str:
    """The date in an archive's name: its order is the date's."""
    return _current().strftime("%y%m%d-%H%M")


def local_hhmm(ts: str | None) -> str:
    """A stamp as `HH:MM` in the machine's local time, as `status` prints times; `?` for none."""
    try:
        return datetime.strptime(str(ts), FORMAT).replace(tzinfo=UTC).astimezone().strftime("%H:%M")
    except ValueError:
        return "?"


def age_minutes(ts: str | None) -> float | None:
    if not ts:
        return None
    then = datetime.strptime(ts, FORMAT).replace(tzinfo=UTC)
    return (_current() - then).total_seconds() / 60


def parse(ts: str) -> datetime:
    """A stamp as an instant."""
    return datetime.strptime(ts, FORMAT).replace(tzinfo=UTC)


def after(seconds: int, since: str | None = None) -> str:
    """The stamp `seconds` after `since` (default: now)."""
    base = parse(since) if since else _current()
    return (base + timedelta(seconds=seconds)).strftime(FORMAT)


def seconds_until(ts: str) -> float:
    """How long until the stamp; negative once it has passed."""
    return (parse(ts) - _current()).total_seconds()

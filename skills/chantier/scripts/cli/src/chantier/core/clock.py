"""The clock: UTC stamps and ages."""

from __future__ import annotations

from datetime import UTC, datetime


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp() -> str:
    """The date in an archive's name: its order is the date's."""
    return datetime.now(UTC).strftime("%y%m%d-%H%M")


def age_minutes(ts: str | None) -> float | None:
    if not ts:
        return None
    then = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    return (datetime.now(UTC) - then).total_seconds() / 60

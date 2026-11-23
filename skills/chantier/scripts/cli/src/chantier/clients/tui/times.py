"""The times and words `chantier live` draws: the server's clock text, the time left of a lease,
an age and the words of a Ready row. Pure functions, no Rich and no network."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

FORMAT = "%Y-%m-%dT%H:%M:%SZ"
SECONDS = 60
HOURS, DAY = 3600, 86400
NO_TIME = "----- --:--:--"


def parse(ts: Any) -> datetime | None:
    try:
        return datetime.strptime(str(ts), FORMAT).replace(tzinfo=UTC)
    except ValueError:
        return None


def hms(ts: Any) -> str:
    """`HH:MM:SS` of a chantier time (UTC), as every chantier text shows it."""
    text = str(ts or "")
    return text[11:19] if len(text) >= 19 else "--:--:--"  # noqa: PLR2004 - ISO 8601 slots


def since(ts: Any, now: datetime) -> str:
    """How long ago, rounded down: `<n> s`, `<n> min`, `<n> h`, `1 day`, `<n> days`; an instant
    ahead of now reads `0 s`; a time that does not parse reads empty."""
    at = parse(ts)
    if at is None:
        return ""
    seconds = max(0, int((now - at).total_seconds()))
    if seconds < SECONDS:
        return f"{seconds} s"
    if seconds < HOURS:
        return f"{seconds // SECONDS} min"
    if seconds < DAY:
        return f"{seconds // HOURS} h"
    days = seconds // DAY
    return "1 day" if days == 1 else f"{days} days"


def offset_text(at: datetime) -> str:
    """The UTC offset of an aware time as `UTC+01:00`."""
    delta = at.utcoffset() or timedelta(0)
    minutes = int(delta.total_seconds() // SECONDS)
    sign = "-" if minutes < 0 else "+"
    return f"UTC{sign}{abs(minutes) // SECONDS:02d}:{abs(minutes) % SECONDS:02d}"


def lease_left(lease: dict[str, Any] | None, now: datetime) -> str | None:
    """The time left of a lease from its facts: none when it ended (or never was); `mm:ss`
    while it expires after now; else its gate's word, else
    `not confirmed <n> min`, the words of the CLI's leases."""
    if not lease or lease.get("ended"):
        return None
    expires = parse(lease.get("expires"))
    if expires is None:
        return None
    left = (expires - now).total_seconds()
    if left > 0:
        whole = int(left)
        return f"{whole // SECONDS:02d}:{whole % SECONDS:02d}"
    if lease.get("gate"):
        return str(lease["gate"])
    return f"not confirmed {int(-left // SECONDS)} min"


def age(since_: Any, now: datetime) -> str:
    """How long ago: `<m>m`, or `<h>h<mm>m` past an hour."""
    at = parse(since_)
    if at is None:
        return ""
    minutes = max(0, int((now - at).total_seconds() // SECONDS))
    if minutes < SECONDS:
        return f"{minutes}m"
    return f"{minutes // SECONDS}h{minutes % SECONDS:02d}m"


# Ready's state words, the first match top to bottom: (word, the board's state colour)
NOT_READ = ("not read", "queued")


def ready_word(pr: dict[str, Any] | None) -> tuple[str, str]:
    """The word and the state-colour name of a Ready row from its PR row (None: no row)."""
    if pr is None:
        return NOT_READ
    why = pr.get("why")
    if why == "merged":
        return "merged, not recorded", "merged"
    if pr.get("ready_now"):
        return "ready to merge", "ready"
    words = {
        "draft": ("draft", "draft"),
        "closed": ("closed", "blocked"),
        "conflicting": ("conflicting", "blocked"),
        "failing": ("checks failing", "blocked"),
    }
    if why in words:
        return words[why]
    if pr.get("checking") or pr.get("checks") == "running":
        return "checks running", "waits"
    return "to review", "queued"

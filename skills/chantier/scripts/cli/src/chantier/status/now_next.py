"""The two sentences a CR's view shows: what it is doing now, and what comes next."""

from __future__ import annotations

from chantier.core.records import BatchRecord, CrEntry
from chantier.core.repo import Repo
from chantier.core.waits import open_counted
from chantier.rails import is_held
from chantier.status.words import (
    forge_word,
    no_start,
    notify,
    parked_reason,
    step,
    unheld,
    waits_on,
)


def _apart_now_next(d: BatchRecord, c: CrEntry) -> tuple[str, str] | None:
    """A CR parked, held or unheld: what it is doing now and what comes next; None for any other."""
    if parked_reason(c):
        if open_counted(c):
            return (
                c.blocked_reason or "Parked.",
                "Its wait cleared, the Foreman takes it back on top.",
            )
        return (
            "Parked: its wait is cleared.",
            "The Foreman takes it back, before any queued CR.",
        )
    if c.status == "blocked" and is_held(c):
        where = " and the stack" if d.mode == "stack" else ""
        return (
            f"Held by the user (order {c.held}): out of the slots{where}.",
            "The user's `order unhold`, through the Chief of Staff.",
        )
    if unheld(c):
        return (
            f"Unheld ({(c.blocked_reason or '').removeprefix('unheld: ')}): back on top, to take "
            "back.",
            "A Driver takes it back, before any queued CR.",
        )
    return None


def now_next(repo: Repo, d: BatchRecord, c: CrEntry, waiting: list[str]) -> tuple[str, str]:
    pr = c.pr or f"its {forge_word([])}"
    if (apart := _apart_now_next(d, c)) is not None:
        return apart
    if waits_on(c):
        reason = c.blocked_reason or ""
        what = reason.split(":", 1)[1].strip() or "something on its way"
        return (
            reason,
            f"Waits for {what}; the Foreman takes it back when that lands.",
        )
    if c.status == "blocked":
        return (
            c.blocked_reason or "Blocked.",
            "The user's answer, through the Chief of Staff.",
        )
    if c.status == "ready":
        return notify(repo, d, c, pr)
    return {
        "Queued": (
            f"Waits for {', '.join(waiting)}." if waiting else no_start(d),
            "A Driver starts it.",
        ),
        "Round": ("A coder and its reviews are working.", "The long gate, then the ship."),
        "CI": (
            f"{pr} is open: CI, then the verifier at the pushed head (it records `verdict`).",
            "The hand-back.",
        ),
        "Release": ("The Release driver follows the project's procedure.", "The next step of it."),
        "Merged": (f"Merged: {pr}.", "Nothing."),
        "Dropped": ("Dropped on the user's word.", "Nothing."),
    }[step(c)]

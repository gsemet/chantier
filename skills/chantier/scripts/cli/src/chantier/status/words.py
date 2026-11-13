"""The words and icons of a CR's status."""

from __future__ import annotations

from chantier.core.records import BatchRecord, CrEntry
from chantier.rails import over_budget, slot_free, waits_all

ASKING = {"question", "approval", "merge", "fix", "infra", "budget", "refused", "rounds", "waits"}


ENDED = {"merged", "cancelled"}


def step(c: CrEntry) -> str:
    status = c.status
    if status == "queued":
        return "Queued"
    if status == "ready":
        return "Notify"
    if status == "blocked":
        word = (c.blocked_reason or "").split(":")[0].split(" ")[0].lower()
        return word.capitalize() if word in ASKING else "Blocked"
    if status in ENDED:
        return "Merged" if status != "cancelled" else "Dropped"
    if c.kind == "release":
        return "Release"
    return "CI" if c.pr else "Round"


def forge_word(links: list[str | None]) -> str:
    """ "MR" for a GitLab merge request link, "PR" for any other, "PR/MR" with no link yet."""
    shown = [x for x in links if x]
    if not shown:
        return "PR/MR"
    return "MR" if any("/merge_requests/" in x for x in shown) else "PR"


def severity(c: CrEntry) -> str:
    if c.status == "blocked":
        return "red"
    if c.status in {"ready", "merged"}:
        return "green"
    return "grey" if c.status == "cancelled" else "yellow"


def _round(c: CrEntry) -> int:
    """The round under way, or the last one done: `chantier round` counts it."""
    return max(c.round, 1)


def waits(d: BatchRecord, c: CrEntry) -> list[str]:
    """What a queued CR waits for: the rule of `take`, read from the batch's record."""
    return waits_all(d.crs, c, d.mode) if c.status == "queued" else []


def waits_on(c: CrEntry) -> bool:
    """A blocked CR that waits for a thing already on its way: nobody has to decide."""
    return c.status == "blocked" and (c.blocked_reason or "").lower().startswith("waits:")


def can_start(d: BatchRecord) -> bool:
    """A queued CR could start now: `take` refuses on no free slot and on a spent budget."""
    return slot_free(d) and not over_budget(d)


def icon(c: CrEntry, waiting: list[str], free: bool) -> str:
    """The icon of a state, the one the report copies; `severity` is another reading."""
    status = c.status
    if status == "queued":
        return "🟠" if waiting or not free else "⚪"
    if status == "blocked":
        return "🟠" if waits_on(c) else "🔴"
    return {"working": "🟡", "ready": "🔵", "merged": "✅", "cancelled": "⚪"}[status]


def label(c: CrEntry, max_rounds: int, waiting: list[str] | None = None, free: bool = True) -> str:
    """`🔴 blocked CI 1/3`: how a CR's state reads in every table."""
    state = "dropped" if c.status == "cancelled" else c.status
    mark = icon(c, waiting or [], free)
    if waiting:
        return f"{mark} {state}, waits for {', '.join(waiting)}"
    if c.status in ENDED | {"queued"}:
        return f"{mark} {state}"
    return f"{mark} {state} {step(c)} {_round(c)}/{max_rounds}"


def no_start(d: BatchRecord) -> str:
    """Why a queued CR with nothing to wait for does not start: the budget, else the slots."""
    spent = over_budget(d)
    return "Waiting for the budget." if spent else "Waiting for a free slot."


def steering_word(steering: str | None) -> str:
    """Who steers the batch, in the words the user reads; a batch that says nothing is unknown."""
    return {"direct": "direct (the Chief of Staff)", "foreman": "Foreman"}.get(
        steering or "", "unknown"
    )


def shape_word(mode: str | None) -> str:
    return mode if mode in ("stack", "series", "parallel") else "unknown"

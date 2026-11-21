"""The words and icons of a CR's status."""

from __future__ import annotations

from chantier.core.records import BatchRecord, CrEntry, round_limit
from chantier.core.repo import Repo
from chantier.core.waits import open_counted, what
from chantier.rails import over_budget, slot_free, waits_all
from chantier.stack_words import (
    PR_IN_DRAFT,
    READY_LOCALLY,
    READY_TO_MERGE,
    draft_clause,
    draft_waits,
    ready_word,
)

ASKING = {"question", "approval", "merge", "fix", "infra", "budget", "refused", "rounds", "waits"}


ENDED = {"merged", "cancelled"}


def parked_reason(c: CrEntry) -> bool:
    """A blocked CR the Foreman parked: its reason starts with `parked:`."""
    return c.status == "blocked" and (c.blocked_reason or "").startswith("parked:")


def step(c: CrEntry) -> str:
    status = c.status
    if status in {"queued", "ready"}:
        return "Queued" if status == "queued" else "Notify"
    if status == "blocked":
        word = (c.blocked_reason or "").split(":")[0].split(" ")[0].lower()
        return "Parked" if parked_reason(c) else word.capitalize() if word in ASKING else "Blocked"
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


def next_to_start(d: BatchRecord) -> str | None:
    """The queued CR that `take` would give a slot first, by order: none when the budget is spent
    or when every queued CR waits. The Foreman may take another one `take` accepts."""
    if over_budget(d):
        return None
    ready = [c for c in d.crs if c.status == "queued" and not waits(d, c)]
    return min(ready, key=lambda c: c.order).id if ready else None


_PHASE_WORDS = {"conflict-resolver": "conflict resolver", "pr": "PR", "ci": "CI"}


def _blocked_text(c: CrEntry) -> str | None:
    if parked_reason(c):
        mine = open_counted(c)
        return (
            f"parked: waits for {'; '.join(what(w) for w in mine)}"
            if mine
            else "parked: wait cleared"
        )
    return None if waits_on(c) else "waits for the user"


def phase_text(c: CrEntry) -> str | None:
    """The step a CR shows, the text every surface copies: its Driver's recorded step while it
    works, "waits for the user" when it is blocked and nobody else is on it."""
    if c.status == "blocked":
        return _blocked_text(c)
    if c.status != "working" or not c.phase:
        return None
    n = _round(c)
    word = _PHASE_WORDS.get(c.phase, c.phase)
    detail = c.phase_detail or ""
    if c.phase in {"coder", "inspector"}:
        return f"{word} r{n}"
    if c.phase == "review":
        return f"{detail} r{n}".strip()
    if c.phase in {"gate", "release"}:
        return f"{word} {detail}".strip()
    return word


READY_ICON = {READY_LOCALLY: "🟣", PR_IN_DRAFT: "🟤", READY_TO_MERGE: "🟢"}


def icon(c: CrEntry, waiting: list[str], free: bool, ready: str | None = None) -> str:
    """The icon of a state, the one the report copies; `severity` is another reading. A ready
    CR's icon follows its word (`ready_word`)."""
    status = c.status
    if status == "queued":
        return "🟠" if waiting or not free else "⚪"
    if status == "blocked":
        return "🟠" if waits_on(c) else "🔴"
    if status == "ready":
        return READY_ICON.get(ready or PR_IN_DRAFT, "🟤")
    return {"working": "🟡", "merged": "✅", "cancelled": "⚪"}[status]


def label(
    c: CrEntry,
    max_rounds: int,
    waiting: list[str] | None = None,
    free: bool = True,
    ready: str | None = None,
) -> str:
    """`🔴 blocked CI 1/3`: how a CR's state reads in every table. A ready CR reads its word
    (`ready_word`); a PR in draft is held by what it waits for, as a queued CR is."""
    state = {"cancelled": "dropped", "ready": ready or PR_IN_DRAFT}.get(c.status, c.status)
    if c.moved_to():
        state = f"dropped to {c.moved_to()}"
    mark = icon(c, waiting or [], free, ready)
    if waiting:
        return f"{mark} {state}, waits for {', '.join(waiting)}"
    if c.status in ENDED | {"queued"}:
        return f"{mark} {state}"
    return f"{mark} {state} {step(c)} {_round(c)}/{max_rounds}"


def state_label(repo: Repo, d: BatchRecord, c: CrEntry, waiting: list[str]) -> str:
    """The CR's `label` as the record gives it: every table, STATUS file and view copies it."""
    word = ready_word(d, c, repo)
    held = [draft_waits(d, c, repo)] if word == PR_IN_DRAFT else waiting
    return label(c, round_limit(d, c), held, can_start(d), word)


def notify(repo: Repo, d: BatchRecord, c: CrEntry, pr: str) -> tuple[str, str]:
    """The now and next lines of a ready CR, by the word it reads."""
    word = ready_word(d, c, repo)
    if word == READY_TO_MERGE:
        return f"Ready to merge: {pr} waits for the user's merge.", "The merge, then the archive."
    if word == READY_LOCALLY:
        return "Ready locally: no PR yet.", "Its PR."
    clause = draft_clause(d, c, repo, c.kind == "release" and bool(c.pr))
    out = "" if c.pr_draft is False else " and the PR is out of draft"
    return f"PR in draft: {clause}.", f"Ready to merge once what is under it is{out}."


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

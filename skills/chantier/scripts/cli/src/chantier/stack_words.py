"""The word a ready CR reads (`ready locally`, `PR in draft`, `ready to merge`) and what a PR in
draft waits for, from the record: the stack's order, and for a CR the stack driver has not placed
its PR's base on the forge as `ship` last read it."""

from __future__ import annotations

from chantier.core.records import BatchRecord, CrEntry
from chantier.core.repo import Repo
from chantier.rails import ENDED, apart_owner, is_held, out_of_order
from chantier.stack_apart import parked_text, waits_with
from chantier.stacks import chain, held_text, stack_base

READY_LOCALLY = "ready locally"
PR_IN_DRAFT = "PR in draft"
READY_TO_MERGE = "ready to merge"


def _out_of_draft(c: CrEntry) -> bool:
    """A CR handed back ready whose PR is recorded as out of draft."""
    return c.status == "ready" and bool(c.pr) and c.pr_draft is False


def _by_forge_base(d: BatchRecord, c: CrEntry) -> bool:
    """True when `c` reads its word from its PR's base on the forge, not from the order: a CR of
    the chain that the stack driver has not placed, not a release, with a recorded base."""
    return (
        not c.stacked
        and c.kind != "release"
        and bool(c.pr_base)
        and c.id in {x.id for x in chain(d)}
    )


def _forge_case(d: BatchRecord, c: CrEntry, repo: Repo) -> tuple[str, CrEntry | None]:
    """Where a CR read by its PR's base sits: `default` (the default branch), `open` (the branch
    of a CR neither ended nor held, the owner), `merged` (the branch of a CR recorded merged) or
    `other` (a cancelled or held CR's branch, the owner, or a branch of no CR, None)."""
    if c.pr_base == repo.config["default_branch"]:
        return "default", None
    owner = next((x for x in d.crs if x.branch == c.pr_base), None)
    if owner is None or owner.id == c.id:
        return "other", None
    if owner.status == "merged":
        return "merged", owner
    gone = owner.status in ENDED or out_of_order(d.crs, owner, d.mode)
    return ("other" if gone else "open"), owner


def _ready_word(d: BatchRecord, c: CrEntry, repo: Repo, seen: frozenset[str]) -> str | None:
    """`ready_word`, with the ids of the CRs the walk along PR bases has met (a loop of bases
    ends in `PR in draft`)."""
    if c.status != "ready":
        return None
    if not c.pr:
        return READY_LOCALLY
    if c.pr_draft is not False or out_of_order(d.crs, c, d.mode):
        return PR_IN_DRAFT
    return _out_of_draft_word(d, c, repo, seen)


def _out_of_draft_word(d: BatchRecord, c: CrEntry, repo: Repo, seen: frozenset[str]) -> str:
    """The word of a ready CR whose PR is recorded out of draft: ready to merge, or the PR in
    draft it waits under."""
    place = chain(d)
    ids = [x.id for x in place]
    if c.id not in ids:
        default: str = repo.config["default_branch"]
        return READY_TO_MERGE if pr_base_of(d, c, repo) == default else PR_IN_DRAFT
    under = place[: ids.index(c.id)]
    by_order = READY_TO_MERGE if all(_out_of_draft(x) for x in under) else PR_IN_DRAFT
    if not _by_forge_base(d, c):
        return by_order
    kind, owner = _forge_case(d, c, repo)
    if kind == "default":
        return READY_TO_MERGE
    if kind == "merged":
        return by_order
    if kind != "open" or owner is None or c.id in seen:
        return PR_IN_DRAFT
    word = _ready_word(d, owner, repo, seen | {c.id})
    return READY_TO_MERGE if word == READY_TO_MERGE else PR_IN_DRAFT


def ready_word(d: BatchRecord, c: CrEntry, repo: Repo) -> str | None:
    """The word a ready CR reads, derived from the record; None for a CR not handed back ready.
    Ready to merge: the PR is recorded out of draft and, in a stack, every CR under it is too (for
    a CR the stack driver has not placed, with a recorded base: its PR's base is the default
    branch, or the branch of a CR that reads ready to merge); elsewhere its base is the default
    branch. A PR with no recorded draft state reads as a draft: never ahead of the forge."""
    return _ready_word(d, c, repo, frozenset())


def pr_base_of(d: BatchRecord, c: CrEntry, repo: Repo) -> str:
    """The base its PR has: the forge's, as `ship` last read it; with none recorded (no PR
    shipped, an older record, a failed read) the record's plan, `stack_base`."""
    return c.pr_base or stack_base(d, c, repo)


def _waited_by_forge(d: BatchRecord, c: CrEntry, repo: Repo) -> tuple[bool, CrEntry | str | None]:
    """`draft_waited` for a CR read by its PR's base: whether this decides it, and the answer;
    a merged CR's branch is decided by the order (False)."""
    kind, owner = _forge_case(d, c, repo)
    if kind == "default":
        return True, None
    if kind == "open" and owner is not None:
        word = _ready_word(d, owner, repo, frozenset({c.id}))
        return True, None if word == READY_TO_MERGE else owner
    return (False, None) if kind == "merged" else (True, owner or c.pr_base)


def _apart_text(d: BatchRecord, c: CrEntry) -> str:
    """What an apart CR, or one waiting with it, waits for: the hold's way back, or the park's
    waits and its way back."""
    owner = apart_owner(d.crs, c, d.mode)
    if is_held(owner):
        return (
            held_text(c)
            if c is owner
            else (f"waits with {waits_with(d, c)}: `order unhold {owner.id}`")
        )
    waits = parked_text(owner) or "wait cleared"
    own = f"parked ({waits})" if c is owner else f"waits with {waits_with(d, c)} ({waits})"
    return f"{own}: back once its wait is cleared"


def draft_waited(d: BatchRecord, c: CrEntry, repo: Repo) -> CrEntry | str | None:
    """What a PR in draft waits for: for a held CR, the text of its hold; for a parked CR, or one
    that waits with an apart CR, what it waits for and its way back. For a CR the stack driver
    has not placed, with a recorded base (`ready_word`'s second case): None (its turn out of
    draft) on the default branch, the open CR whose branch it sits on while that CR does not read
    ready to merge, else None; on a merged CR's branch, as below; on any other base the CR whose
    branch it is, else the branch. Otherwise the CR whose branch its PR sits on, on the forge, when
    that CR is not out of draft; else the CR under it in the stack not yet out of draft, else the
    CR whose branch its base is, else the base branch itself (no CR of the batch), else None (its
    own turn out of draft)."""
    if out_of_order(d.crs, c, d.mode):
        return _apart_text(d, c)
    default: str = repo.config["default_branch"]
    by_forge = _by_forge_base(d, c)
    if by_forge:
        decided, waited = _waited_by_forge(d, c, repo)
        if decided:
            return waited
    if c.pr_base and c.pr_base != default:
        on = next((x for x in d.crs if x.branch == c.pr_base), None)
        if on is not None and not _out_of_draft(on) and not (by_forge and on.status == "merged"):
            return on
    place = chain(d)
    ids = [x.id for x in place]
    if c.id in ids:
        below = [x for x in place[: ids.index(c.id)] if not _out_of_draft(x)]
        if below:
            return below[-1]
    base = pr_base_of(d, c, repo)
    if base != default:
        return next((x for x in d.crs if x.branch == base), base)
    return None


def draft_clause(d: BatchRecord, c: CrEntry, repo: Repo, prepared: bool) -> str:
    """`its PR <pr> is <state>; it waits <what>`: the clause the ready line of a PR in draft ends
    with and the CR's now line repeats, from the record."""
    if c.pr_draft is None:
        state = f"of unknown draft state (draft not read: ship {c.id} {c.pr})"
    else:
        state = "a draft on the forge" if c.pr_draft else "out of draft on the forge"
    waited = draft_waited(d, c, repo)
    own = f"the release PR {c.pr} is" if prepared else f"its PR {c.pr} is"
    if out_of_order(d.crs, c, d.mode):
        return f"{own} {state}; it waits: {waited}"
    if waited is None:
        what = "for its turn out of draft"
    elif isinstance(waited, str):
        what = f"on the branch {waited} (no CR of this batch)"
    else:
        what = f"on {waited.id} ({waited.pr or 'no PR yet'})"
    return f"{own} {state}; it waits {what}"


def draft_waits(d: BatchRecord, c: CrEntry, repo: Repo) -> str:
    """The same answer as a word for the views: the CR's id, the branch, or its own turn."""
    waited = draft_waited(d, c, repo)
    if waited is None:
        return "its turn out of draft"
    return waited if isinstance(waited, str) else waited.id


def state_word(d: BatchRecord, c: CrEntry, repo: Repo) -> str:
    """The state as a person reads it: the CR's status, a ready CR by its word."""
    return ready_word(d, c, repo) or c.status

"""Where a CR's PR sits: the stack, the base of a PR, and the word a ready CR reads.

Read by the commands and by the status and board views, so it lives below both."""

from __future__ import annotations

from chantier.core.records import BatchRecord, CrEntry, GateWaiver
from chantier.core.repo import Repo
from chantier.rails import ENDED, series_predecessor

READY_LOCALLY = "ready locally"
PR_IN_DRAFT = "PR in draft"
READY_TO_MERGE = "ready to merge"


def chain(b_data: BatchRecord) -> list[CrEntry]:
    """The stack as it stands: the CRs not ended, in order, the release CR last whatever its
    `order` (it is the top piece). A fix CR sits outside it, on the default branch. What a
    partial merge leaves forms the next stack, so the first CR left stands on the default
    branch; a CR added by `order add` goes on top (under the release)."""
    if b_data.mode != "stack":
        return []
    return sorted(
        [x for x in b_data.crs if x.status not in {"cancelled", "merged"} and x.kind != "fix"],
        key=lambda x: (x.kind == "release", x.order),
    )


def top_cr(b_data: BatchRecord) -> CrEntry | None:
    """In an ordered batch (stack, series), the last open CR under the release, in order: the
    branch the release starts on and its PR sits on. A fix CR and the release are not in it."""
    if b_data.mode not in {"stack", "series"}:
        return None
    open_ = [x for x in b_data.crs if x.status not in ENDED and x.kind not in {"release", "fix"}]
    return max(open_, key=lambda x: x.order, default=None)


def stack_top(b_data: BatchRecord) -> CrEntry | None:
    """The stack's top under the release: the last CR of `chain`, the release and a fix left out.
    The CR whose long gate validates a stack waiver; never stored, read from the chain."""
    return next((x for x in reversed(chain(b_data)) if x.kind not in {"release", "fix"}), None)


def waived_gate(b_data: BatchRecord, c: CrEntry) -> GateWaiver | None:
    """The waiver that covers this CR's long gate, or None. A `cr` waiver covers its CR; a
    `stack` waiver covers every CR of the chain but the stack's top, whose gate validates."""
    w = c.gate_waiver
    if w is None:
        return None
    if w.scope != "stack":
        return w
    top = stack_top(b_data)
    return w if top is not None and top.id != c.id else None


def validating_cr(b_data: BatchRecord, c: CrEntry) -> CrEntry | None:
    """The CR whose gate validates this CR's `stack` waiver, None for any other CR."""
    w = waived_gate(b_data, c)
    return stack_top(b_data) if w is not None and w.scope == "stack" else None


def validated_ids(b_data: BatchRecord, c: CrEntry) -> list[str]:
    """The CRs a stack waiver leaves to this CR's gate: the stack's top, when it carries one."""
    top = stack_top(b_data)
    if top is None or top.id != c.id or c.gate_waiver is None or c.gate_waiver.scope != "stack":
        return []
    return [x.id for x in chain(b_data) if validating_cr(b_data, x) is c]


def next_merge(b_data: BatchRecord) -> CrEntry | None:
    """In an ordered batch (stack, series), the CR the user merges next: the first, in order, that
    is not merged or cancelled. A fix CR and the release CR do not count. None in a parallel
    batch: the record names no next merge there."""
    if b_data.mode not in {"stack", "series"}:
        return None
    open_ = [x for x in b_data.crs if x.status not in ENDED and x.kind not in {"release", "fix"}]
    return min(open_, key=lambda x: x.order, default=None)


def start_base(b_data: BatchRecord, c: CrEntry, repo: Repo) -> str:
    """The branch a CR starts on: that of its last dependency still open, in the order of
    `after`; with none open, the default branch, whatever its place in a stack. A release in an
    ordered batch starts on the top CR's branch, with none open under it on the default branch;
    in a parallel batch, or alone, on the default branch."""
    default: str = repo.config["default_branch"]
    if c.kind == "release":
        top = top_cr(b_data)
        return top.branch if top else default
    if b_data.mode == "series":
        pred = series_predecessor(b_data.crs, c)
        return pred.branch if pred and pred.status != "merged" else default
    if c.after and c.kind not in {"release", "fix"}:
        found = {x.id: x for x in b_data.crs}
        open_ = [found[i] for i in c.after if i in found and found[i].status not in ENDED]
        return open_[-1].branch if open_ else default
    return default


def stack_base(b_data: BatchRecord, c: CrEntry, repo: Repo, planned: bool = False) -> str:
    """The base its PR has: its place in the stack once `stack` marked the CR (`planned`: the
    place it will take); otherwise where it started. A CR sits on the one below it in the chain
    (the first on the default branch), whatever its `after`; a CR with an open dependency that
    `stack` has not placed yet, on that dependency's branch."""
    default: str = repo.config["default_branch"]
    if c.kind == "release":  # the top of the stack: on the top CR's branch
        return start_base(b_data, c, repo)
    if not c.stacked and ((c.after and c.kind != "fix") or not planned):
        return start_base(b_data, c, repo)  # not placed by `stack` yet: where it started
    order = chain(b_data)
    ids = [x.id for x in order]
    i = ids.index(c.id) if c.id in ids else 0
    return order[i - 1].branch if i > 0 else default


def _out_of_draft(c: CrEntry) -> bool:
    """A CR handed back ready whose PR is recorded as out of draft."""
    return c.status == "ready" and bool(c.pr) and c.pr_draft is False


def ready_word(d: BatchRecord, c: CrEntry, repo: Repo) -> str | None:
    """The word a ready CR reads, derived from the record; None for a CR not handed back ready.
    Ready to merge: the PR is recorded out of draft and, in a stack, every CR under it is too;
    elsewhere its base is the default branch. A PR with no recorded draft state reads as a draft:
    never ahead of the forge."""
    if c.status != "ready":
        return None
    if not c.pr:
        return READY_LOCALLY
    if c.pr_draft is not False:
        return PR_IN_DRAFT
    place = chain(d)
    ids = [x.id for x in place]
    if c.id in ids:
        under = place[: ids.index(c.id)]
        return READY_TO_MERGE if all(_out_of_draft(x) for x in under) else PR_IN_DRAFT
    default: str = repo.config["default_branch"]
    return READY_TO_MERGE if pr_base_of(d, c, repo) == default else PR_IN_DRAFT


def pr_base_of(d: BatchRecord, c: CrEntry, repo: Repo) -> str:
    """The base its PR has: the forge's, as `ship` last read it; with none recorded (no PR
    shipped, an older record, a failed read) the record's plan, `stack_base`."""
    return c.pr_base or stack_base(d, c, repo)


def draft_waits(d: BatchRecord, c: CrEntry, repo: Repo) -> str:
    """What a PR in draft waits for: the CR whose branch its PR sits on, on the forge, when that
    CR is not out of draft; else the CR under it in the stack not yet out of draft, else the CR
    whose branch its base is, else its own turn out of draft."""
    default: str = repo.config["default_branch"]
    if c.pr_base and c.pr_base != default:
        on = next((x for x in d.crs if x.branch == c.pr_base), None)
        if on is not None and not _out_of_draft(on):
            return on.id
    place = chain(d)
    ids = [x.id for x in place]
    if c.id in ids:
        below = [x for x in place[: ids.index(c.id)] if not _out_of_draft(x)]
        if below:
            return below[-1].id
    base = pr_base_of(d, c, repo)
    if base != repo.config["default_branch"]:
        return next((x.id for x in d.crs if x.branch == base), base)
    return "its turn out of draft"


def state_word(d: BatchRecord, c: CrEntry, repo: Repo) -> str:
    """The state as a person reads it: the CR's status, a ready CR by its word."""
    return ready_word(d, c, repo) or c.status

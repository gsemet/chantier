"""Where a CR's PR sits: the stack and the base of a PR (the word a ready CR reads: `stack_words`).

Read by the commands and by the status and board views, so it lives below both."""

from __future__ import annotations

from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.records import BatchRecord, CrEntry, GateWaiver
from chantier.core.repo import Repo
from chantier.rails import (
    ENDED,
    apart,
    base_owner,
    is_held,
    out_of_order,
    series_predecessor,
)
from chantier.stack_apart import dependents

FORMING = 2  # the ready CRs with a PR that make the first stack due (`stack_due`)


def refuse_held(c: CrEntry) -> None:
    """`take <cr>` of a held CR: refused, it stays held until the user's `order unhold`."""
    if is_held(c):
        raise ChantierError(
            f"{c.id} is held (order {c.held}): only the user's `order unhold {c.id}` releases it",
            EXIT_PRECONDITION,
        )


def held_text(c: CrEntry) -> str:
    """What a held CR waits for: its way back, the user's `order unhold`."""
    where = " out of the stack" if c.status == "ready" else ""
    return f"held{where} (order {c.held}): `order unhold {c.id}`"


def chain(b_data: BatchRecord) -> list[CrEntry]:
    """The stack as it stands: the CRs not ended, in order, the release CR last whatever its
    `order` (it is the top piece). A fix CR sits outside it, on the default branch. What a
    partial merge leaves forms the next stack, so the first CR left stands on the default
    branch; a CR added by `order add` goes on top (under the release)."""
    if b_data.mode != "stack":
        return []
    return sorted(
        [
            x
            for x in b_data.crs
            if x.status not in {"cancelled", "merged"}
            and x.kind != "fix"
            and not out_of_order(b_data.crs, x, b_data.mode)
        ],
        key=lambda x: (x.kind == "release", x.order),
    )


def top_cr(b_data: BatchRecord, landed: frozenset[str] = frozenset()) -> CrEntry | None:
    """In an ordered batch (stack, series), the last open CR under the release, in order: the
    branch the release starts on and its PR sits on. A fix CR and the release are not in it, nor
    a CR of `landed` (seen merged on the forge, see `hub.journal.seen_merged`)."""
    if b_data.mode not in {"stack", "series"}:
        return None
    open_ = [
        x
        for x in b_data.crs
        if x.status not in ENDED
        and x.id not in landed
        and x.kind not in {"release", "fix"}
        and not out_of_order(b_data.crs, x, b_data.mode)
    ]
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
    open_ = [
        x
        for x in b_data.crs
        if x.status not in ENDED
        and x.kind not in {"release", "fix"}
        and not out_of_order(b_data.crs, x, b_data.mode)
    ]
    return min(open_, key=lambda x: x.order, default=None)


def _alone(c: CrEntry) -> bool:
    """A CR that is neither a release nor a fix."""
    return c.kind not in {"release", "fix"}


def _open_after(
    b_data: BatchRecord, c: CrEntry, landed: frozenset[str] = frozenset()
) -> list[CrEntry]:
    """The dependencies of `c` still open, in the order of `after`; a CR of `landed` is ended."""
    found = {x.id: x for x in b_data.crs}
    return [
        found[i] for i in c.after if i in found and found[i].status not in ENDED and i not in landed
    ]


def stack_due(b_data: BatchRecord) -> list[CrEntry]:
    """The CRs that make the batch's first stack due, in `chain` order, else []. Due: a running
    stack batch, no stack driver recorded, no CR of the batch (merged and cancelled included)
    placed by `stack`, and `FORMING` CRs or more of the chain, the release and a fix aside,
    `ready` with a PR and with every open dependency `ready` too."""
    d = b_data
    if d.mode != "stack" or d.status != "running" or d.stack_agent:
        return []
    if any(x.stacked for x in d.crs):
        return []
    due = [
        x
        for x in chain(d)
        if _alone(x)
        and x.status == "ready"
        and x.pr
        and all(y.status == "ready" for y in _open_after(d, x))
    ]
    return due if len(due) >= FORMING else []


def held_lines(b_data: BatchRecord, repo: Repo) -> list[str]:
    """One `status` line per held CR, in order: a ready CR held in a stack (where it sits and how
    it comes back), or a CR held while it was live (out of the slots, with the CRs that wait with
    it). An unheld CR still `blocked` is not held: its row says so."""
    default: str = repo.config["default_branch"]
    lines = []
    for c in sorted(b_data.crs, key=lambda x: x.order):
        if not is_held(c):
            continue
        if c.status == "ready" and b_data.mode == "stack":
            lines.append(
                f"held: {c.id} (order {c.held}) out of the stack, PR {c.shown_pr() or '-'} on "
                f"{default}: `order unhold {c.id}` puts it back"
            )
            continue
        waiting = [x.id for x in dependents(b_data.crs, c, b_data.mode)]
        tail = f"; waiting with it: {', '.join(waiting)}" if waiting else ""
        where = " and the stack" if b_data.mode == "stack" else ""
        lines.append(
            f"held: {c.id} (order {c.held}), was working, out of the slots{where}: only the "
            f"user's `order unhold {c.id}` brings it back{tail}"
        )
    return lines


def stack_line(b_data: BatchRecord) -> list[str]:
    """The `status` line that says the batch's first `take stack` is due; [] when it is not."""
    due = stack_due(b_data)
    if not due:
        return []
    ids = ", ".join(x.id for x in due)
    return [
        f"stack: take stack now: {ids} ready with a PR, no stack made yet "
        "(`take stack --epoch <n>`)"
    ]


def _below_with_pr(
    b_data: BatchRecord, c: CrEntry, landed: frozenset[str] = frozenset()
) -> tuple[int, CrEntry] | None:
    """The first CR with a PR (so its branch is on the remote) found walking `chain` down from
    `c`, with its place in the chain; None when no CR below `c` has one. A CR of `landed` has
    none to count."""
    order = chain(b_data)
    ids = [x.id for x in order]
    top = ids.index(c.id) if c.id in ids else 0
    return next(
        (
            (i, order[i])
            for i in range(top - 1, -1, -1)
            if order[i].pr and order[i].id not in landed
        ),
        None,
    )


def _nearest_open(
    b_data: BatchRecord, c: CrEntry, landed: frozenset[str] = frozenset()
) -> tuple[int, CrEntry] | None:
    """The open dependency of `c` that sits highest in `chain`, whatever its place in `after`,
    with that place; a dependency outside the chain (a fix CR) ranks below every CR of it (-1)."""
    ids = [x.id for x in chain(b_data)]
    ranked = [(ids.index(x.id) if x.id in ids else -1, x) for x in _open_after(b_data, c, landed)]
    return max(ranked, key=lambda r: r[0], default=None)


def start_on_for(
    b_data: BatchRecord, c: CrEntry, landed: frozenset[str] = frozenset()
) -> str | None:
    """The branch a CR taken from `queued` is to start on, to record on it: in a stack batch, for
    a CR that is neither a release nor a fix and has no open dependency, the branch of the nearest
    CR below it in `chain` that has a PR (`stack_start`'s rule 2), else None (the default branch);
    in a series batch, the branch of an open `series_predecessor` (the one `start_base`'s series
    rule gives). None in a parallel batch and for any other CR; a stack CR with an open
    dependency gets none, its base follows its dependencies' places. A CR of `landed` (its PR seen
    merged on the forge) reads as ended."""
    if b_data.mode == "series":
        pred = series_predecessor(b_data.crs, c) if _alone(c) else None
        return pred.branch if pred and pred.status != "merged" and pred.id not in landed else None
    if b_data.mode != "stack" or not _alone(c) or _open_after(b_data, c, landed):
        return None
    below = _below_with_pr(b_data, c, landed)
    return below[1].branch if below else None


def _live_start(b_data: BatchRecord, c: CrEntry, landed: frozenset[str] = frozenset()) -> bool:
    """True when `c.start_on` names the branch of a CR that is neither ended (nor in `landed`)
    nor out of order (apart, or waiting with an apart CR)."""
    owner = next((x for x in b_data.crs if x.branch == c.start_on), None) if c.start_on else None
    return (
        owner is not None
        and owner.status not in ENDED
        and owner.id not in landed
        and not out_of_order(b_data.crs, owner, b_data.mode)
    )


def _dependent_base(b_data: BatchRecord, c: CrEntry) -> str | None:
    """The shared base rule: a dependent's base is the branch of the last out-of-order CR among
    its candidates; None for a CR that is not a dependent (or is a fix or a release)."""
    if c.kind in {"release", "fix"}:
        return None
    owner = base_owner(b_data.crs, c, b_data.mode)
    return owner.branch if owner is not None else None


def _outside_base(b_data: BatchRecord, c: CrEntry, default: str) -> str | None:
    """The base of a CR out of order, before the series and stack rules: an apart CR is on the
    default branch, a dependent on its base owner's branch; None for any other CR."""
    return default if apart(c) else _dependent_base(b_data, c)


def stack_start(
    b_data: BatchRecord, c: CrEntry, repo: Repo, landed: frozenset[str] = frozenset()
) -> str:
    """The branch a CR of a stack batch starts on, and the place the record gives it until
    `stack` places it (a CR that is neither a release nor a fix). First match wins:
    1. its `start_on`, recorded at its take, while the CR that owns that branch is not ended;
    2. the branch of the nearest CR below it in `chain` that has a PR, unless one of its open
       dependencies sits higher in `chain`: then the nearest such dependency's branch;
    3. with no CR below that has a PR, the nearest open dependency's branch (highest in `chain`,
       a dependency outside the chain ranking lowest), else the default branch.
    A CR of `landed` (its PR seen merged on the forge) reads as ended in all three."""
    default: str = repo.config["default_branch"]
    if _live_start(b_data, c, landed):
        return str(c.start_on)
    below = _below_with_pr(b_data, c, landed)
    dep = _nearest_open(b_data, c, landed)
    if below is not None:
        return dep[1].branch if dep is not None and dep[0] > below[0] else below[1].branch
    return dep[1].branch if dep is not None else default


def start_base(
    b_data: BatchRecord, c: CrEntry, repo: Repo, landed: frozenset[str] = frozenset()
) -> str:
    """The branch a CR starts on. A release in an ordered batch: the top CR's branch, with none
    open under it the default branch. A series batch: the previous CR's branch. A stack batch,
    for a CR that is neither a release nor a fix: `stack_start`. Otherwise (a parallel batch, a
    fix): the branch of its last open dependency in the order of `after`, else the default
    branch. `landed`: the CRs seen merged on the forge, read as ended."""
    default: str = repo.config["default_branch"]
    if c.kind == "release":
        top = top_cr(b_data, landed)
        return top.branch if top else default
    if (outside := _outside_base(b_data, c, default)) is not None:
        return outside
    if b_data.mode == "series":
        pred = series_predecessor(b_data.crs, c)
        open_pred = pred is not None and pred.status != "merged" and pred.id not in landed
        return pred.branch if pred and open_pred else default
    stackable = b_data.mode == "stack" and c.kind != "fix"
    owner = next((x for x in b_data.crs if x.branch == c.start_on), None) if c.start_on else None
    held_owner = (
        owner is not None
        and owner.status not in ENDED
        and out_of_order(b_data.crs, owner, b_data.mode)
    )
    if stackable and not held_owner and (not c.stacked or c.start_on):  # an owner out of order
        return stack_start(b_data, c, repo, landed)
    if c.after and c.kind != "fix":
        open_ = _open_after(b_data, c, landed)
        if open_:
            return open_[-1].branch
    return default


def stack_base(
    b_data: BatchRecord,
    c: CrEntry,
    repo: Repo,
    planned: bool = False,
    *,
    landed: frozenset[str] = frozenset(),
) -> str:
    """The base its PR has. A CR placed by `stack` sits on the one below it in the chain (the
    first on the default branch), whatever its `after`. A CR not placed yet (and not a release or
    a fix) has `stack_start`'s base, for either value of `planned`. The release sits on the top
    CR; a fix CR keeps `start_base`'s result (`planned` only matters for that fix CR's place,
    the default branch). `landed`: the CRs seen merged on the forge, read as ended (the stacked
    rule skips them, `stack_start` and `start_base` take them as they are)."""
    default: str = repo.config["default_branch"]
    if c.kind == "release":  # the top of the stack: on the top CR's branch
        return start_base(b_data, c, repo, landed)
    if (outside := _outside_base(b_data, c, default)) is not None:
        return outside
    if not c.stacked:
        if c.kind != "fix":
            return stack_start(b_data, c, repo, landed)
        if not planned:
            return start_base(b_data, c, repo, landed)
    order = chain(b_data)
    ids = [x.id for x in order]
    i = ids.index(c.id) if c.id in ids else 0
    below = next((x for x in reversed(order[:i]) if x.id not in landed), None)
    return below.branch if below is not None else default


def off_place(d: BatchRecord, c: CrEntry, repo: Repo) -> tuple[str, str] | None:
    """For a working CR whose PR is not on its place in the stack: the base its PR is on (as
    `ship` last read it) and the CR (else the branch) it is to be stacked on. None otherwise,
    and for a CR with no `pr_base` recorded (no forge read to doubt it)."""
    if c.status != "working" or not c.pr or not c.pr_base or d.mode != "stack":
        return None
    planned = stack_base(d, c, repo, planned=True)
    if c.pr_base == planned:
        return None
    below = next((x.id for x in d.crs if x.branch == planned), planned)
    return c.pr_base, below


def to_come(d: BatchRecord, c: CrEntry, repo: Repo) -> bool:
    """True when `c` is not in the stack as it stands: it has no PR, or its working PR is off its
    place, or it is working and not placed by the stack driver yet (`stack <cr>...` has not named
    its PR)."""
    return (
        not c.pr or off_place(d, c, repo) is not None or (c.status == "working" and not c.stacked)
    )

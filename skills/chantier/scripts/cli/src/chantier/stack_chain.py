"""The CR below a CR the record places on another CR's branch (checked at `ship` and at
`stack --out-of-draft`: `commands/chain_check.py`). Read-only, through the base rules of stacks."""

from __future__ import annotations

from chantier.core.records import BatchRecord, CrEntry
from chantier.core.repo import Repo
from chantier.rails import ENDED, apart
from chantier.stacks import _live_start, stack_base, start_base


def chain_below(
    d: BatchRecord, c: CrEntry, repo: Repo, landed: frozenset[str] = frozenset()
) -> CrEntry | None:
    """Read-only: the CR below `c` that the record places `c` on, when `c` is one of the CRs
    whose branch must hold that CR's recorded head; None otherwise. Checked: the release CR of a
    stack or series batch (its CR below is the top CR); in a stack batch a CR placed by `stack`,
    or taken onto another CR's branch and not placed yet with a live `start_on`; in a series
    batch every CR that is not the release. Not checked: a fix, a held (apart) CR, an ended CR,
    a CR of `landed`, and a CR whose base is the default branch or a branch no open CR owns. The
    base comes from `stack_base` / `start_base`, never from a copy of their rules."""
    if d.mode not in {"stack", "series"} or c.kind == "fix":
        return None
    if c.status in ENDED or c.id in landed or apart(c):
        return None
    if d.mode == "stack":
        if c.kind != "release" and not c.stacked and not _live_start(d, c, landed):
            return None
        base = stack_base(d, c, repo, landed=landed)
    else:
        base = start_base(d, c, repo, landed)
    return next(
        (
            x
            for x in d.crs
            if x.id != c.id and x.branch == base and x.status not in ENDED and x.id not in landed
        ),
        None,
    )

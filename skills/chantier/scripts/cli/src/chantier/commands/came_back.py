"""A CR taken out of a batch (`order drop` to the inbox or the backlog) that joins one again:
its `formerly.json` gives it its number back, and its branch and PR while its branch exists."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import NamedTuple

from chantier.core.batch import Batch
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.files import read_text
from chantier.core.git import branch_exists
from chantier.core.records import CrEntry
from chantier.lifecycle.filing import slugify

FORMERLY_FORM = '{"cr": "CR-<n>", "batch", "branch", "worktree", "pr", "pr_draft"}'


class Formerly(NamedTuple):
    """`formerly.json`: where a CR taken out of a batch came from (`order drop`)."""

    cr: str
    batch: str | None
    branch: str | None
    worktree: str | None
    pr: str | None
    pr_draft: bool | None


def came_back(prepared: Path) -> Formerly | None:
    """`<folder>/formerly.json` of a CR that comes back to a batch; None when there is none.
    A file that is not of the form `order drop` writes is refused, before anything moves."""
    path = prepared / "formerly.json"
    if not path.is_file():
        return None
    refusal = ChantierError(f"{path}: expected {FORMERLY_FORM}", EXIT_PRECONDITION)
    try:
        data = json.loads(read_text(path))
    except (OSError, ValueError) as e:
        raise refusal from e
    if not isinstance(data, dict) or not re.fullmatch(r"CR-\d+", str(data.get("cr"))):
        raise refusal
    texts = {k: data.get(k) for k in ("batch", "branch", "worktree", "pr")}
    draft = data.get("pr_draft")
    if not all(t is None or isinstance(t, str) for t in texts.values()):
        raise refusal
    if not (draft is None or isinstance(draft, bool)):
        raise refusal
    return Formerly(data["cr"], **texts, pr_draft=draft)


def holds(b: Batch, came: Formerly, prepared: Path) -> CrEntry | None:
    """The batch's entry that `came` reopens: the same CR, cancelled, with a `left_to`, in the
    batch `formerly.json` names. Any other entry of that id is a clash, refused."""
    held = next((c for c in b.record.crs if c.id == came.cr), None)
    if held is None:
        return None
    if came.batch == b.id and held.status == "cancelled" and held.left_to:
        return held
    raise ChantierError(
        f"{b.repo.rel(prepared)}: formerly.json names {came.cr}, which {b.id} already holds",
        EXIT_PRECONDITION,
    )


def came_back_line(b: Batch, c: CrEntry, came: Formerly, title: str) -> str:
    """Give the CR its former branch, worktree and PR while the branch exists, else fresh names;
    the line that says which."""
    repo = b.repo
    if came.branch and branch_exists(came.branch, repo.clone if repo.external else repo.root):
        c.branch, c.worktree = came.branch, came.worktree or str(repo.worktrees / f"{b.id}-{c.id}")
        c.pr, c.pr_draft = came.pr, came.pr_draft
        return f"{c.id} joins with its branch {came.branch} and " + (
            f"PR {came.pr}" if came.pr else "no PR"
        )
    c.branch = f"chantier/{b.id}/{c.id.lower()}-{slugify(title)}"
    c.worktree = str(repo.worktrees / f"{b.id}-{c.id}")
    c.unset("pr")
    c.unset("pr_draft")
    return f"{c.id} joins fresh: its branch {came.branch} is gone" + (
        f"; its former PR {came.pr} is left as it is" if came.pr else ""
    )


def reopen(b: Batch, c: CrEntry) -> None:
    """A cancelled CR that comes back to its batch starts again, keeping its notes and cost."""
    for name in (
        "agent",
        "left_to",
        "head",
        "pr_base",
        "start_on",
        "blocked_reason",
        "gate_waiver",
        "after",
    ):
        c.unset(name)
    c.clear_phase()
    c.status, c.round, c.attempts, c.stacked = "queued", 0, 0, False
    c.order = max((x.order for x in b.record.crs), default=0) + 1

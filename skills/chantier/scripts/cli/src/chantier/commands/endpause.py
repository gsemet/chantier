"""The end of a batch's last CR: the merged CRs' worktrees and branches are removed, then the
batch is paused (the one pause body, `closing.record_pause`)."""

from __future__ import annotations

from pathlib import Path

from chantier.commands.closing import record_pause
from chantier.commands.leftover import DESTINATIONS, left, way_back
from chantier.core.batch import read_batch
from chantier.core.clock import now
from chantier.core.endblockers import end_blockers
from chantier.core.git import branch_exists, refusal
from chantier.core.records import BatchRecord, CrEntry
from chantier.core.repo import Repo
from chantier.lifecycle.session import RenderedBatch
from chantier.rails import all_merged

__all__ = ["end_of_batch", "left_open", "way_back"]
PAUSE = "`chantier pause --epoch <n>`"


def _cleanup(repo: Repo, c: CrEntry) -> tuple[str, bool]:
    """One merged CR's worktree and branch, removed without `--force`; its line, and whether
    something was left."""
    if c.agent:
        return f"cleanup: {c.id} kept: agent {c.agent} still held", True
    cwd = repo.clone if repo.external else repo.root
    gone: list[str] = []
    if c.worktree and Path(c.worktree).exists():
        why = refusal("worktree", "remove", c.worktree, cwd=cwd)
        if why:
            return f"cleanup: {c.id} worktree {c.worktree} not removed: {why}", True
        gone.append(f"worktree {c.worktree}")
    if c.branch and branch_exists(c.branch, cwd):
        why = refusal("branch", "-D", c.branch, cwd=cwd)
        if why:
            return f"cleanup: {c.id} branch {c.branch} not removed: {why}", True
        gone.append(f"branch {c.branch}")
    if gone:
        return f"cleanup: {c.id} {' and '.join(gone)} removed", False
    return f"cleanup: {c.id} worktree and branch already gone", False


def _next_line() -> str:
    return (
        "next: the retro (with its critic), then offer the close (`chantier close`, then "
        "`close --yes` on the user's yes)"
    )


def left_open(d: BatchRecord) -> list[str]:
    """A CR ended and every CR not ended is parked, held or blocked, or queued behind such CRs:
    the batch pauses nothing and cleans nothing; one line says what keeps it open."""
    rest = left(d)
    if not rest:
        return []
    ways = "; ".join(way_back(d, c) for c in rest)
    return [
        f"{d.id}: every other CR is merged or cancelled; {ways}: "
        f"the batch stays open until it comes back or the user sends it out "
        f"(`order drop <cr> --note <{DESTINATIONS}>`)"
    ]


def end_of_batch(repo: Repo, batch: str, trigger: str) -> list[str]:
    """The batch's last CR just ended (locks released): clean, then pause, and say what is next.
    When the pause cannot run, nothing is cleaned and the line says what blocks it."""
    d = read_batch(repo, batch)
    if d.status == "paused":
        return []
    if not all_merged(d):
        return left_open(d)
    causes = end_blockers(d)
    if causes:
        return [
            f"every CR is merged or cancelled, not paused: {'; '.join(causes)}; "
            f"{PAUSE} once they are done"
        ]
    git_lines = [_cleanup(repo, c) for c in d.crs if c.status == "merged"]
    with RenderedBatch(repo, batch, actor="foreman") as b:
        blocked = end_blockers(b.record)
        if blocked:  # it changed while we cleaned
            return [
                *[t for t, _ in git_lines],
                f"every CR is merged or cancelled, not paused: {'; '.join(blocked)}; "
                f"{PAUSE} once they are done",
            ]
        for o in b.record.orders:
            if not o.done:
                o.done = now()
                b.log("order-done", None, order=o.id)
        summary = record_pause(repo, b, trigger)
    kept = any(left for _, left in git_lines)
    return [
        *[t for t, _ in git_lines],
        f"paused {batch}: every CR is merged or cancelled; cost to date below",
        f"report: {b.dir / 'STATUS.md'}",
        *summary,
        _next_line(),
        *(
            [
                "kept: remove them once their Driver has ended, or on the user's word at "
                "`close`, which names them"
            ]
            if kept
            else []
        ),
    ]

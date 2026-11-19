"""The end of a batch's last CR: the merged CRs' worktrees and branches are removed, then the
batch is paused (the one pause body, `closing.record_pause`)."""

from __future__ import annotations

from pathlib import Path

from chantier.commands.closing import record_pause
from chantier.core.batch import read_batch
from chantier.core.clock import now
from chantier.core.endblockers import end_blockers
from chantier.core.git import branch_exists, refusal
from chantier.core.records import CrEntry
from chantier.core.repo import Repo
from chantier.lifecycle.session import RenderedBatch
from chantier.rails import all_merged

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


def _next_line(batch: str, factory: bool) -> str:
    if factory:
        return (
            f"next: factory {batch} waits for its next ready CR (`triage <folder> --ready`): "
            "no retro and no close now; they come on the user's word (`order factory off`, then "
            "the retro and the close offer)"
        )
    return (
        "next: the retro (with its critic), then offer the close (`chantier close`, then "
        "`close --yes` on the user's yes)"
    )


def end_of_batch(repo: Repo, batch: str, trigger: str) -> list[str]:
    """The batch's last CR just ended (locks released): clean, then pause, and say what is next.
    When the pause cannot run, nothing is cleaned and the line says what blocks it."""
    d = read_batch(repo, batch)
    if not all_merged(d) or d.status == "paused":
        return []
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
        _next_line(batch, b.record.factory),
        *(
            [
                "kept: remove them once their Driver has ended, or on the user's word at "
                "`close`, which names them"
            ]
            if kept
            else []
        ),
    ]

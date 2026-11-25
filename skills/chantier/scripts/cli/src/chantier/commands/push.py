"""`push`: chantier's own update of a CR's own recorded branch after a rebase, declared legitimate
by this command: one `git push --force-with-lease=<branch>:<expected>`, from the CR's worktree, by
a caller that holds the lease. Never `--force`, never `--no-verify`, no retry, no forge call."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from chantier.commands.crs import batch_cr, cr_worktree, short_head
from chantier.core import leases
from chantier.core.errors import EXIT_CONFLICT, EXIT_EXTERNAL, EXIT_PRECONDITION, ChantierError
from chantier.core.git import git
from chantier.core.records import BatchRecord, CrEntry
from chantier.core.repo import Repo
from chantier.lifecycle.session import RenderedBatch
from chantier.stacks import chain

ONLY = "push only pushes a CR's recorded chantier/* branch"


def push(args: argparse.Namespace) -> list[str]:
    repo = Repo.find()
    batch, d, c = batch_cr(repo, args.cr, args.batch)
    what = f"push {c.id}"
    unit = _unit(d, c, args.unit)
    _refuse_branch(repo, c)
    if leases.lease_of(d, unit) is None:
        raise ChantierError(f"push needs a held lease; {unit} has none", EXIT_PRECONDITION)
    leases.require(repo, d, unit, args.lease, what)
    wt = cr_worktree(c)
    _refuse_worktree(c, wt)
    leases.renewed_in_session(repo, batch, unit, args.lease, what=what, required=True)
    remote = repo.config["remote"]
    expected = git(
        "rev-parse", "--verify", "--quiet", f"refs/remotes/{remote}/{c.branch}", cwd=wt, check=False
    )
    _run_push(c, wt, remote, expected)
    head = git("rev-parse", "HEAD", cwd=wt)
    shown = f"was {short_head(expected)}" if expected else f"new branch on {remote}"
    done = f"pushed {c.branch} at {short_head(head)} ({shown})"
    try:
        with RenderedBatch(repo, batch, actor="driver") as b:
            leases.claim(b, unit, args.lease, what=what, required=True)
            b.log("push", c.id, unit=unit, branch=c.branch, head=head, expected=expected)
    except ChantierError as e:
        if e.code != EXIT_CONFLICT:
            raise
        raise ChantierError(
            f"{what}: pushed {c.branch} at {short_head(head)} but nothing was recorded: {e}",
            EXIT_CONFLICT,
        ) from e
    return [done]


def _unit(d: BatchRecord, c: CrEntry, unit: str | None) -> str:
    """The unit whose lease the push needs: the CR's own, the stack's, or a QA order's."""
    if unit is None:
        return c.id
    if unit == "stack":
        if d.mode != "stack" or c.id not in {x.id for x in chain(d)}:
            raise ChantierError(
                f"push --unit stack: {c.id} is not in the chain of a stack batch; "
                "push it with its own lease (no --unit)",
                EXIT_PRECONDITION,
            )
        return unit
    order = next((o for o in d.orders if o.id == unit), None) if leases.is_order(unit) else None
    if order is None or order.kind != "qa" or order.cr != c.id:
        raise ChantierError(
            f"push --unit {unit}: not a QA order of {c.id}; "
            "use --unit stack, an order of this CR, or no --unit",
            EXIT_PRECONDITION,
        )
    return unit


def _refuse_branch(repo: Repo, c: CrEntry) -> None:
    if not c.branch:
        raise ChantierError(
            f"push {c.id}: no branch recorded; `take {c.id}` records it", EXIT_PRECONDITION
        )
    if not c.branch.startswith("chantier/") or c.branch == repo.config["default_branch"]:
        raise ChantierError(f"push {c.id}: {ONLY}, not {c.branch}", EXIT_PRECONDITION)


def _refuse_worktree(c: CrEntry, wt: Path) -> None:
    if git("status", "--porcelain", "--untracked-files=normal", cwd=wt):
        raise ChantierError(
            f"push {c.id}: the worktree has uncommitted work: commit first, then push",
            EXIT_PRECONDITION,
        )
    on = git("symbolic-ref", "--quiet", "--short", "HEAD", cwd=wt, check=False)
    if on != c.branch:
        raise ChantierError(
            f"push {c.id}: check out {c.branch} in {wt} (HEAD is {on or 'detached'})",
            EXIT_PRECONDITION,
        )


def _run_push(c: CrEntry, wt: Path, remote: str, expected: str) -> None:
    """The one push, outside any lock; git's own text is kept as git printed it."""
    p = subprocess.run(
        [
            "git",
            "--no-pager",
            "push",
            f"--force-with-lease={c.branch}:{expected}",
            remote,
            f"HEAD:refs/heads/{c.branch}",
        ],
        cwd=wt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        check=False,
    )
    if p.returncode != 0:
        raise ChantierError(
            f"push {c.id}: git refused the push of {c.branch}; nothing recorded\n"
            + (p.stderr or p.stdout).strip(),
            EXIT_EXTERNAL,
        )

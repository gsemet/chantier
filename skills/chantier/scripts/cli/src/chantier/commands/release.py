"""`chantier release` and `chantier cancel`."""

from __future__ import annotations

import argparse
from pathlib import Path

from chantier import procs
from chantier.commands.endpause import end_of_batch
from chantier.core import leases
from chantier.core.batch import check_epoch, find_cr_batch
from chantier.core.errors import EXIT_BUDGET, EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.records import LIVE, TRASH, CrEntry
from chantier.core.repo import Repo
from chantier.gate_slots import mtime, slot_of
from chantier.lifecycle.moveout import check_drop_free, leave_batch, pr_clause
from chantier.lifecycle.session import RenderedBatch
from chantier.lifecycle.stages import changes_lock
from chantier.rails import spent_text
from chantier.rails_release import fix_go, release_go


def release(args: argparse.Namespace) -> tuple[list[str], int]:
    """The release CR's attempts and its irreversible actions: none before every other CR is
    merged and the release PR is merged (the user's, or the steering session's under the grant);
    then the merge is the go, else each one is approved by the user, or allowed by the grant the
    user gave, within the budget. While the release PR is recorded and not merged, `go` answers
    from the grant alone (`merge` with none) and spends no approval. A fix's merge is an action too:
    `go` on the fix CR, under the grant alone."""
    repo = Repo.find()
    batch = find_cr_batch(repo, args.cr, args.batch)
    fresh: list[str] = []
    if args.action == "go":  # the only action that checks the budget: on the real spend
        from chantier.commands.batch_status import refresh_for_check  # noqa: PLC0415 - slow

        fresh = refresh_for_check(repo, batch, "driver")
    with RenderedBatch(repo, batch, actor="driver") as b:
        c = b.cr(args.cr)
        is_fix = c.kind == "fix" and args.action == "go"
        if c.kind != "release" and not is_fix:
            raise ChantierError(f"{args.cr} is not the batch's release CR", EXIT_USAGE)
        if c.status in LIVE:  # a Driver's command; the Foreman's `go` on a ready fix has none
            what = f"release {args.action} {c.id}"
            leases.claim(b, c.id, args.lease, what=what, required=True)
        if args.action == "start":  # a new attempt, on the branch the Driver set on the base
            # a merged PR of an earlier attempt is not this one's
            # (a merged PR is already cleared by `release_merged`; an attempt refreshes the
            # recorded release PR, and a Driver that opens another records it with `ship`)
            b.touch(c, attempts=c.attempts + 1, head=None)
            b.log("release-start", args.cr)
            return [f"attempt {c.attempts}: the procedure starts from its first step"], 0
        if not (args.note or "").strip():
            raise ChantierError(f'release {args.action} {args.cr} --note "<…>"', EXIT_USAGE)
        if args.action == "published":
            grant = b.record.release
            if grant is None:
                raise ChantierError("no release grant recorded: `order release` first")
            grant.published += 1
            c.append("notes", f"published: {args.note}")
            b.touch(c)
            b.log("release-published", args.cr, note=args.note)
            return [f"release {grant.published} published: {args.note}"], 0
        result, why = fix_go(b, c, args.note) if is_fix else release_go(b, c, args.note)
        words, code = _answer(b, result, why, args.note, is_fix)
        return [*words, *fresh], code


def _answer(
    b: RenderedBatch, result: str, why: str, note: str, is_fix: bool
) -> tuple[list[str], int]:
    """The words and the exit code for what `fix_go` or `release_go` decided."""
    refused = {
        "budget": (
            f"no: the budget is spent ({spent_text(b.record)} of "
            f"${b.record.budget_usd}); only the user raises it",
            EXIT_BUDGET,
        ),
        "fix": (f"no: fix {why} is not merged", EXIT_PRECONDITION),
        "merge": (f"no: {why}", EXIT_PRECONDITION),
        "ask": (
            (f"no grant for: {note}; the user merges it", EXIT_PRECONDITION)
            if is_fix
            else (
                f"no approval for: {note}; the user's word comes as `order approve`",
                EXIT_PRECONDITION,
            )
        ),
    }
    if result in refused:
        text, code = refused[result]
        return [text], code
    return [f"go: {note} ({why})"], 0


def _stop_processes(repo: Repo, c: CrEntry) -> list[str]:
    """The CR's gate's process group, if it is still that process, and the processes that run in
    its worktree: stopped; what was stopped, as `pg<n>` and paths."""
    killed = []
    v = slot_of(repo, c.id)
    h = v.holder if v else None
    # a pg the lock names counts only while it is still that process (a pid can be reused)
    if (
        v
        and h
        and h.pg is not None
        and procs.alive_since(h.pg, mtime(repo.store, v.slot.lock), False)
        and procs.stop_group(h.pg)
    ):
        killed.append(f"pg{h.pg}")
    if c.worktree and Path(c.worktree).exists():
        killed += [str(p) for p in procs.stop(procs.find(Path(c.worktree)))]
    return killed


def cancel(args: argparse.Namespace) -> list[str]:
    """A dropped CR, on the user's word: its gate and its stray processes stopped, its folder
    moved to the destination its drop order recorded (trash, backlog or the next batch,
    `3-ready`), with its work."""
    if args.epoch is None:
        raise ChantierError(
            "cancel <cr> --epoch <n>: the steering session's command for a CR the "
            "user dropped; a Driver stops its own long gate with "
            f"`gate {args.cr} --stop`",
            EXIT_PRECONDITION,
        )
    repo = Repo.find()
    with (
        changes_lock(repo),
        RenderedBatch(repo, find_cr_batch(repo, args.cr, args.batch), actor="foreman") as b,
    ):
        check_epoch(b, args.epoch)
        c = b.cr(args.cr)
        if c.status == "merged":
            raise ChantierError(f"{args.cr} is merged: nothing to cancel")
        if c.status != "cancelled" and c.left_to is None:
            raise ChantierError(
                f"cancel {args.cr}: no destination recorded; the Chief of Staff's "
                f'"order drop {args.cr} --note trash|ready|P1..P4" names it',
                EXIT_PRECONDITION,
            )
        if c.status != "cancelled":
            check_drop_free(b, c, c.left_to or TRASH)
        killed = _stop_processes(repo, c)
        leave_batch(b, c)  # it ends the CR's lease: its old Driver's next command is `claim lost`
        b.touch(c, status="cancelled", agent=None)
        to = c.left_to or TRASH
        b.log("cancel", args.cr, killed=killed, path=c.path, to=to)
        batch_id = b.id
        clause = pr_clause(b, c)
    here = "" if to == TRASH else f" to {to}"
    return [
        f"cancelled {args.cr}{here}; stopped {len(killed)}: {' '.join(killed) or 'none'}",
        *([clause.removeprefix("; ")] if clause else []),
        *end_of_batch(repo, batch_id, f"cancel {args.cr}"),
    ]

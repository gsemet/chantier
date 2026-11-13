"""`chantier release` and `chantier cancel`."""

from __future__ import annotations

import re
from pathlib import Path

from chantier import procs
from chantier.commands.gate_lock import lock_holder
from chantier.commands.registry import BATCH, BATCH_EPOCH, Subparsers, add_command
from chantier.core.batch import check_epoch, find_cr_batch
from chantier.core.errors import EXIT_BUDGET, EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.lifecycle.convert import open_repo
from chantier.lifecycle.session import RenderedBatch
from chantier.lifecycle.stages import changes_lock, trash_cr
from chantier.rails import all_merged, spent_text
from chantier.rails_release import fix_go, release_go


def release(args) -> tuple[list[str], int]:
    """The release CR's attempts and its irreversible actions: none before every other CR is
    merged and the release PR is merged (the user's, or the steering session's under the grant);
    then the merge is the go, else each one is approved by the user, or allowed by the grant the
    user gave, within the budget. A fix's merge is an action too:
    `go` on the fix CR, under the grant alone."""
    repo = open_repo()
    with RenderedBatch(repo, find_cr_batch(repo, args.cr, args.batch), actor="driver") as b:
        c = b.cr(args.cr)
        is_fix = c.get("kind") == "fix" and args.action == "go"
        if c.get("kind") != "release" and not is_fix:
            raise ChantierError(f"{args.cr} is not the batch's release CR", EXIT_USAGE)
        if args.action == "start":  # a new attempt, on the branch the Driver set on the base
            # a merged PR of an earlier attempt is not this one's
            # (a merged PR is already cleared by `release_merged`; an attempt refreshes the
            # recorded release PR, and a Driver that opens another records it with `ship`)
            b.touch(c, attempts=c.get("attempts", 0) + 1, head=None)
            b.log("release-start", args.cr)
            return [f"attempt {c['attempts']}: the procedure starts from its first step"], 0
        if not (args.note or "").strip():
            raise ChantierError(f'release {args.action} {args.cr} --note "<…>"', EXIT_USAGE)
        if args.action == "published":
            grant = b.data["release"]
            grant["published"] = grant.get("published", 0) + 1
            c.setdefault("notes", []).append(f"published: {args.note}")
            b.touch(c)
            b.log("release-published", args.cr, note=args.note)
            return [f"release {grant['published']} published: {args.note}"], 0
        result, why = fix_go(b, c, args.note) if is_fix else release_go(b, c, args.note)
        return _answer(b, result, why, args.note, is_fix)


def _answer(
    b: RenderedBatch, result: str, why: str, note: str, is_fix: bool
) -> tuple[list[str], int]:
    """The words and the exit code for what `fix_go` or `release_go` decided."""
    refused = {
        "budget": (
            f"no: the budget is spent ({spent_text(b.data)} of "
            f"${b.data['budget_usd']}); only the user raises it",
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


def cancel(args) -> list[str]:
    """A dropped CR, on the user's word: its gate and its stray processes stopped, its folder
    in the trash with its work."""
    if args.epoch is None:
        raise ChantierError(
            "cancel <cr> --epoch <n>: the steering session's command for a CR the "
            "user dropped; a Driver stops its own long gate with "
            f"`gate {args.cr} --stop`",
            EXIT_PRECONDITION,
        )
    repo = open_repo()
    with (
        changes_lock(repo),
        RenderedBatch(repo, find_cr_batch(repo, args.cr, args.batch), actor="foreman") as b,
    ):
        check_epoch(b, args.epoch)
        c = b.cr(args.cr)
        if c["status"] == "merged":
            raise ChantierError(f"{args.cr} is merged: nothing to cancel")
        killed = []
        m = re.fullmatch(rf"{re.escape(args.cr)} pid \d+ pg(\d+)", lock_holder(repo))
        if m and procs.stop_group(int(m[1])):
            killed.append(f"pg{m[1]}")
        if c.get("worktree") and Path(c["worktree"]).exists():
            killed += [str(p) for p in procs.stop(procs.find(Path(c["worktree"])))]
        trash_cr(b, c)
        b.touch(c, status="cancelled", agent=None)
        b.log("cancel", args.cr, killed=killed, path=c.get("path"))
        done = all_merged(b)
    return [f"cancelled {args.cr}; stopped {len(killed)}: {' '.join(killed) or 'none'}"] + (
        ["every CR is merged or cancelled: `chantier pause`"] if done else []
    )


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "release",
        release,
        "release driver: start an attempt, go for an irreversible action, published",
        BATCH,
    )
    s.add_argument("action", choices=["start", "go", "published"])
    s.add_argument("cr")
    s.add_argument("--note", help="go: the irreversible action; published: version and link")

    s = add_command(
        sub, "cancel", cancel, "stop a CR's processes and mark it cancelled", BATCH_EPOCH
    )
    s.add_argument("cr")

"""The delivery of a CR: `verdict`, `ship` and `stack`."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

from chantier.commands.crs import batch_cr, cr_events, cr_worktree, gate_passed, short_head, work
from chantier.commands.facts import stack_base, stack_lines
from chantier.commands.registry import BATCH, Subparsers, add_command
from chantier.core.batch import read_batch, resolve_batch
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.files import read_text
from chantier.core.git import git
from chantier.core.records import CrEntry
from chantier.core.repo import Repo
from chantier.lifecycle.convert import open_repo
from chantier.lifecycle.session import RenderedBatch
from chantier.plugin_files import archive_path

VERDICTS = ("VERIFIED", "NOT VERIFIED")
HISTORY_CHARS = 120


def verdict(args: argparse.Namespace) -> list[str]:
    """A verdict on the worktree's head, in the log: the last one at a head decides. It knows a
    verdict, not a role; a card says who runs it."""
    repo = open_repo()
    result = " ".join(" ".join(args.result).upper().split())
    if result not in VERDICTS:
        raise ChantierError('verdict <cr> VERIFIED | "NOT VERIFIED"', EXIT_USAGE)
    try:
        batch, _, c = batch_cr(repo, args.cr, args.batch)
    except ChantierError as e:
        raise ChantierError(str(e), EXIT_PRECONDITION) from e
    wt = cr_worktree(c)
    if git("status", "--porcelain", "--untracked-files=normal", cwd=wt):
        raise ChantierError(
            f"{c.id}: the worktree has uncommitted work: a verdict binds to a head, commit first",
            EXIT_PRECONDITION,
        )
    head = git("rev-parse", "HEAD", cwd=wt)
    with RenderedBatch(repo, batch, actor="driver") as b:
        b.log("verdict", c.id, result=result, head=head)
    return [f"verdict {c.id} {result} at {short_head(head)}"]


def _stale_body_shas(repo: Repo, c: CrEntry, wt: Path, head: str) -> list[str]:
    """The lines of the posted PR body (`work/pr-body.md`) that name a commit of the worktree
    which is not in the new head's history (a restack made it stale). A line marked `STALE` or
    `carried from` is the template's own mark and is left out. Read-only git."""
    body = work(repo, c) / "pr-body.md"
    if not body.is_file():
        return []
    found = []
    for n, line in enumerate(read_text(body).splitlines(), 1):
        if "STALE" in line or "carried from" in line:
            continue
        tok = _stale_token(line, wt, head)
        if tok:
            text = line.strip()
            if len(text) > HISTORY_CHARS:
                text = text[: HISTORY_CHARS - 3] + "..."
            found.append(
                f"pr-body.md line {n} names {tok[:7]}, not in {short_head(head)}'s history: {text}"
            )
    return found


def _stale_token(line: str, wt: Path, head: str) -> str | None:
    """The first commit the line names that exists in the worktree and is not in the head. A token
    of digits only (a PR number, a date) is not read as a commit."""
    for tok in dict.fromkeys(re.findall(r"\b(?=[0-9a-f]{0,39}[a-f])[0-9a-f]{7,40}\b", line)):
        if not git("rev-parse", "--verify", "--quiet", f"{tok}^{{commit}}", cwd=wt, check=False):
            continue
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", tok, head],
            cwd=wt,
            capture_output=True,
            check=False,
        )
        if ancestor.returncode != 0:
            return str(tok)
    return None


def _off_worktree(repo: Repo, c: CrEntry, wt: Path, head: str) -> list[str]:
    """What is off in the worktree: uncommitted changes, a head not pushed."""
    off = []
    dirty = git("status", "--porcelain", "--untracked-files=normal", cwd=wt)
    if dirty:
        what = (
            "untracked files"
            if all(ln.startswith("??") for ln in dirty.splitlines())
            else "uncommitted changes"
        )
        off.append(
            f"{what} in the worktree, not in the PR: "
            f"{' '.join(ln.split(maxsplit=1)[-1] for ln in dirty.splitlines()[:5])}"
        )
    ref = f"{repo.config['remote']}/{c.branch}"
    pushed = git("rev-parse", "--verify", "--quiet", ref, cwd=wt, check=False)
    if pushed != head:
        where_ = "not pushed" if not pushed else "at " + pushed[:7]
        off.append(
            f"{ref} is {where_}, not this head: push with --force-with-lease, then ship again"
        )
    return off


def ship(args: argparse.Namespace) -> list[str]:
    """The Driver pushed and opened or updated the PR itself; this records the link at the
    worktree's head and says what is off: an uncommitted change, a head not pushed, no long gate
    passed at this head."""
    repo = open_repo()
    batch, d, c = batch_cr(repo, args.cr, args.batch)
    wt = cr_worktree(c)
    if "://" not in args.pr:
        raise ChantierError("ship <cr> <pr link>", EXIT_USAGE)
    head = git("rev-parse", "HEAD", cwd=wt)
    off = _off_worktree(repo, c, wt, head)
    short = short_head(head)  # display only: the CR and the event keep the full SHA
    where = archive_path(repo, c)
    seen = None
    if where:
        seen = bool(
            git("ls-tree", "-d", "--name-only", head, where.rstrip("/"), cwd=wt, check=False)
        )
        if not seen:
            off.append(f"archive missing from the PR at {where}")
    if not gate_passed(cr_events(repo, batch, c.id), head):
        off.append(f"no long gate passed at {short} (`chantier gate`)")
    off += _stale_body_shas(repo, c, wt, head)
    base = stack_base(d, c, repo)
    with RenderedBatch(repo, batch, actor="driver") as b:
        b.touch(b.cr(c.id), pr=args.pr, head=head, archive_seen=seen)
        b.log("ship", c.id, pr=args.pr, base=base, head=head, off=off)
    return [f"recorded {args.pr} (base {base}, head {short})"] + [f"off: {x}" for x in off]


def stack(args: argparse.Namespace) -> list[str]:
    """The stack's order, as its driver set it; each PR's base follows from it."""
    repo = open_repo()
    batch = resolve_batch(repo, args.batch)
    if not args.crs:  # read only: no lock, no event, no epoch
        d = read_batch(repo, batch)
        if d.mode != "stack":
            raise ChantierError(f"batch {batch} is not a stack")
        return stack_lines(repo, batch, d)
    with RenderedBatch(repo, batch, actor="stack") as b:
        if b.record.mode != "stack":
            raise ChantierError(f"batch {batch} is not a stack")
        place = {cr: i for i, cr in enumerate(args.crs, 1)}
        for cr in args.crs:
            below = [a for a in b.cr(cr).after if place.get(a, 0) > place[cr]]
            if below:
                raise ChantierError(
                    f"{cr} depends on {', '.join(below)}: it cannot sit below "
                    f"{'it' if len(below) == 1 else 'them'}"
                )
        for i, cr in enumerate(args.crs, 1):
            b.touch(b.cr(cr), order=i, stacked=True)
        b.log("stack-order", None, crs=args.crs)
    return [f"stack order: {' → '.join(args.crs)}"]


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "verdict",
        verdict,
        "the Verifier's verdict on the CR's worktree head: VERIFIED or \"NOT VERIFIED\"",
        BATCH,
    )
    s.add_argument("cr")
    s.add_argument("result", nargs="+", help="VERIFIED, or NOT VERIFIED (one argument or two)")

    s = add_command(
        sub, "ship", ship, "record the PR the Driver opened or updated; say what is off", BATCH
    )
    s.add_argument("cr")
    s.add_argument("pr", help="the PR link")

    s = add_command(sub, "stack", stack, "the stack's order, as its driver set it", BATCH)
    s.add_argument(
        "crs",
        nargs="*",
        help="the stack's order, as its driver set it, bottom first; "
        "with no CR, print the stack as it stands (writes nothing)",
    )

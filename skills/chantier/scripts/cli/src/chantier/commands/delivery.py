"""The delivery of a CR: `verdict`, `ship` and `stack`."""

from __future__ import annotations

import re
import subprocess

from chantier.commands.crs import batch_cr, cr_events, cr_worktree, gate_passed, short_head, work
from chantier.commands.facts import stack_base, stack_lines
from chantier.commands.registry import BATCH, Subparsers, add_command
from chantier.core.batch import read_batch, resolve_batch
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.files import read_text
from chantier.core.git import git
from chantier.core.repo import Repo
from chantier.lifecycle.convert import open_repo
from chantier.lifecycle.session import RenderedBatch
from chantier.plugin_files import archive_path

VERDICTS = ("VERIFIED", "NOT VERIFIED")
HISTORY_CHARS = 120


def verdict(args) -> list[str]:
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
            f"{c['id']}: the worktree has uncommitted work: a verdict binds to a "
            "head, commit first",
            EXIT_PRECONDITION,
        )
    head = git("rev-parse", "HEAD", cwd=wt)
    with RenderedBatch(repo, batch, actor="driver") as b:
        b.log("verdict", c["id"], result=result, head=head)
    return [f"verdict {c['id']} {result} at {short_head(head)}"]


def _stale_body_shas(repo: Repo, c: dict, wt: str, head: str) -> list[str]:
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
        for tok in dict.fromkeys(re.findall(r"\b[0-9a-f]{7,40}\b", line)):
            if not git(
                "rev-parse", "--verify", "--quiet", f"{tok}^{{commit}}", cwd=wt, check=False
            ):
                continue
            if (
                subprocess.run(
                    ["git", "merge-base", "--is-ancestor", tok, head],
                    cwd=wt,
                    capture_output=True,
                    check=False,
                ).returncode
                != 0
            ):
                text = line.strip()
                found.append(
                    f"pr-body.md line {n} names {tok[:7]}, not in {short_head(head)}'s "
                    f"history: {text if len(text) <= HISTORY_CHARS else text[: HISTORY_CHARS - 3] + '...'}"
                )
                break
    return found


def ship(args) -> list[str]:
    """The Driver pushed and opened or updated the PR itself; this records the link at the
    worktree's head and says what is off: an uncommitted change, a head not pushed, no long gate
    passed at this head."""
    repo = open_repo()
    batch, d, c = batch_cr(repo, args.cr, args.batch)
    wt = cr_worktree(c)
    if "://" not in args.pr:
        raise ChantierError("ship <cr> <pr link>", EXIT_USAGE)
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
    head = git("rev-parse", "HEAD", cwd=wt)
    pushed = git(
        "rev-parse",
        "--verify",
        "--quiet",
        f"{repo.config['remote']}/{c['branch']}",
        cwd=wt,
        check=False,
    )
    if pushed != head:
        where_ = "not pushed" if not pushed else "at " + pushed[:7]
        off.append(
            f"{repo.config['remote']}/{c['branch']} is {where_}, "
            f"not this head: push with --force-with-lease, then ship again"
        )
    short = short_head(head)  # display only: the CR and the event keep the full SHA
    where = archive_path(repo, c)
    seen = None
    if where:
        seen = bool(
            git("ls-tree", "-d", "--name-only", head, where.rstrip("/"), cwd=wt, check=False)
        )
        if not seen:
            off.append(f"archive missing from the PR at {where}")
    if not gate_passed(cr_events(repo, batch, c["id"]), head):
        off.append(f"no long gate passed at {short} (`chantier gate`)")
    off += _stale_body_shas(repo, c, wt, head)
    base = stack_base(d, c, repo)
    with RenderedBatch(repo, batch, actor="driver") as b:
        b.touch(b.cr(c["id"]), pr=args.pr, head=head, archive_seen=seen)
        b.log("ship", c["id"], pr=args.pr, base=base, head=head, off=off)
    return [f"recorded {args.pr} (base {base}, head {short})"] + [f"off: {x}" for x in off]


def stack(args) -> list[str]:
    """The stack's order, as its driver set it; each PR's base follows from it."""
    repo = open_repo()
    batch = resolve_batch(repo, args.batch)
    if not args.crs:  # read only: no lock, no event, no epoch
        d = read_batch(repo, batch)
        if d["mode"] != "stack":
            raise ChantierError(f"batch {batch} is not a stack")
        return stack_lines(repo, batch, d)
    with RenderedBatch(repo, batch, actor="stack") as b:
        if b.data["mode"] != "stack":
            raise ChantierError(f"batch {batch} is not a stack")
        place = {cr: i for i, cr in enumerate(args.crs, 1)}
        for cr in args.crs:
            below = [a for a in b.cr(cr).get("after", []) if place.get(a, 0) > place[cr]]
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

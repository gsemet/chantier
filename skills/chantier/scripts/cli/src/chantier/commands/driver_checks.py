"""The Driver's refusals: what a release needs to start, and what a hand-back needs to be ready."""

from __future__ import annotations

import argparse
import subprocess

from chantier.commands.crs import (
    carry_check,
    cr_events,
    cr_worktree,
    dirty_files,
    gate_passed,
    last_gate_pass,
    last_verdict,
    same_head,
    short_head,
)
from chantier.core.batch import Batch
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.git import git
from chantier.core.records import LIVE, BatchRecord, CrEntry, EventRecord
from chantier.core.repo import Repo
from chantier.rails import ENDED
from chantier.stacks import stack_base, top_cr


def check_release_branch(repo: Repo, d: BatchRecord, c: CrEntry) -> None:
    """A release in an ordered batch with CRs open under it starts only once one branch holds all
    the work it ships: the top CR's branch holds the recorded head of every other open CR under
    it. Read only (`git merge-base --is-ancestor`); the CLI changes nothing."""
    top = top_cr(d)
    if c.kind != "release" or top is None:
        return
    ref = top.branch
    if not git("rev-parse", "--verify", "--quiet", f"refs/heads/{ref}", cwd=repo.root, check=False):
        remote = f"{repo.config['remote']}/{ref}"
        if git("rev-parse", "--verify", "--quiet", remote, cwd=repo.root, check=False):
            ref = remote
    for x in sorted(d.crs, key=lambda x: x.order):
        if x.id in {c.id, top.id} or x.status in ENDED or x.kind in {"release", "fix"}:
            continue
        if not x.head:
            raise ChantierError(
                f"{c.id}: {x.id} has no recorded head (`ship`): the stack "
                f"driver stacks the CRs first (`take stack`)",
                EXIT_PRECONDITION,
            )
        held_ = (
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", x.head, ref],
                cwd=repo.root,
                capture_output=True,
                check=False,
            ).returncode
            == 0
        )
        if not held_:
            raise ChantierError(
                f"{c.id}: {top.branch} does not hold {x.id}'s head "
                f"{short_head(x.head)}: the stack driver stacks the CRs first "
                "(`take stack`)",
                EXIT_PRECONDITION,
            )


def handback_args(args: argparse.Namespace, note: str) -> str | None:
    """The refusals that need no record; the `--no-gate` reason, if any."""
    if args.result == "ready" and not note:
        raise ChantierError("handback <cr> ready <pr link, release link or tag>", EXIT_USAGE)
    if args.result == "blocked" and not note:
        raise ChantierError(
            "handback <cr> blocked <reason>: question: …, approval: …, merge: "
            "<pr>, fix: …; <path>, infra: …, budget: …, rounds: …, refused …, "
            "waits: <what it waits for>, context: <where it stopped, what is "
            "next>",
            EXIT_USAGE,
        )
    no_gate = args.no_gate.strip() if args.no_gate is not None else None
    if no_gate is not None and (args.result != "ready" or not no_gate):
        raise ChantierError(
            "handback <cr> ready <pr link> --no-gate \"<the project's rule that "
            'declares no long gate or exempts this CR>"',
            EXIT_USAGE,
        )
    return no_gate


def handback_blocked(b: Batch, c: CrEntry, note: str, line: str) -> list[str]:
    cr = c.id
    b.log("handback", cr, result="blocked", note=note)
    b.touch(c, status="blocked", blocked_reason=note)
    c.clear_phase()
    if note.lower().startswith("waits:"):
        return [line, f"{cr} waits; the Foreman takes it back when that lands"]
    if note.lower().startswith("context:"):
        return [
            line,
            f"{cr} out of context; the Foreman restarts a fresh Driver "
            "from this state, with no ask to the Chief of Staff",
        ]
    return [line, f"{cr} blocked; the Foreman asks the Chief of Staff"]


def _gate_missing(repo: Repo, b: Batch, c: CrEntry, events: list[EventRecord]) -> tuple[str, str]:
    """The refusal for a head with no gate pass, and the head of the pass that carries to it
    (a clean rebase of the gated commits, proved by git); the first is empty when one carries."""
    head = c.head
    text = (
        f"refused: no long gate passed at {head or 'any head'} (gate "
        f'{c.id} "<cmd>"..., or --no-gate "<the project\'s rule>")'
    )
    g = last_gate_pass(events)
    if not g or not head:
        return text, ""
    base = f"{repo.config['remote']}/{stack_base(b.record, c, repo)}"
    why = carry_check(cr_worktree(c), base, head, g)
    if why is None:
        return "", g
    clause = f"(the pass at {short_head(g)} does not carry: {why}) (gate"
    return text.replace("(gate", clause, 1), ""


def handback_refusals(
    repo: Repo, b: Batch, c: CrEntry, no_gate: str | None, prepared: bool
) -> str | None:
    """A ready CR is shipped at the worktree's head, clean, pushed, gated and verified. The head
    of the gate pass it carries over a clean rebase, if that is what let it pass."""
    events, head = cr_events(repo, b.id, c.id), c.head
    wt = cr_worktree(c)
    missing = []
    now_head = git("rev-parse", "HEAD", cwd=wt)
    if not same_head(head, now_head):  # alone: the gate and verdict are for another head
        raise ChantierError(
            f"refused: the worktree's head {now_head[:7]} is not the head ship recorded "
            f"({head or 'none'}): ship {c.id} {c.pr} again, then the long gate and "
            "a verdict VERIFIED at the new head",
            EXIT_PRECONDITION,
        )
    if dirty_files(wt):
        missing.append(
            "refused: the worktree has uncommitted changes or untracked "
            "files: commit them, push, then `ship` again"
        )
    remote = f"{repo.config['remote']}/{c.branch}"
    pushed = git("rev-parse", "--verify", "--quiet", remote, cwd=wt, check=False)
    if not same_head(head, pushed):
        missing.append(
            f"refused: {remote} is "
            f"{'at ' + short_head(pushed) if pushed else 'not pushed'}, not at "
            f"{short_head(head) or 'the shipped head'}: push, then `ship` again"
        )
    carried = ""
    if no_gate is None and not gate_passed(events, head):
        text, carried = _gate_missing(repo, b, c, events)
        if text:
            missing.append(text)
    if not prepared and last_verdict(events, head) != "VERIFIED":
        missing.append(
            f"refused: no verdict VERIFIED at {head or 'any head'} (the last "
            f"verdict there: {last_verdict(events, head) or 'none'})"
        )
    if missing:
        raise ChantierError("\n".join(missing), EXIT_PRECONDITION)
    return carried or None


def live_cr(b: Batch, cr: str, result: str = "") -> CrEntry:
    """The CR a Driver holds, or the refusal that says why none does. A `ready` hand-back is also
    accepted from a `blocked` CR that still has its Driver recorded (not a release)."""
    c = b.cr(cr)
    if c.status in LIVE:
        return c
    if c.status == "blocked" and result == "ready" and c.agent and c.kind != "release":
        return c
    if c.status in ("ready", "blocked"):
        raise ChantierError(
            f"{c.id} is {c.status}: no Driver holds it until the steering "
            f'session takes it back (take {c.id} --note "<why>"), then hand '
            "back again"
        )
    raise ChantierError(f"{cr} is {c.status}: no Driver to hand it back")

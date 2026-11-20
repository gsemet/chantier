"""The Driver's refusals: what a release needs to start, and what a hand-back needs to be ready."""

from __future__ import annotations

import argparse
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from chantier.commands.carry import carry_reason, head_base
from chantier.commands.crs import (
    Judged,
    carry_at,
    conflict_cut,
    cr_events,
    cr_worktree,
    dirty_files,
    judged_gate,
    judged_verdict,
    last_verdict,
    short_head,
)
from chantier.core.batch import Batch
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.git import git
from chantier.core.heads import gate_passed, same_head
from chantier.core.records import LIVE, BatchRecord, CrEntry, EventRecord, GateWaiver
from chantier.core.repo import Repo
from chantier.rails import ENDED
from chantier.stacks import top_cr, validating_cr, waived_gate


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
                f"driver stacks the CRs first (`take stack --epoch <n>`)",
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
                "(`take stack --epoch <n>`)",
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
            "waits: <what it waits for> [--wait answer=<question> | approval | "
            "pipeline[=<sha>] | merge[=<link>]]..., context: <where it stopped, what is "
            "next>",
            EXIT_USAGE,
        )
    if args.wait and args.result != "blocked":
        raise ChantierError(
            "--wait is for a blocked hand-back: handback <cr> blocked <reason> --wait <type>",
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


def wait_specs(args: argparse.Namespace) -> list[tuple[str, str | None]]:
    """The `--wait TYPE[=REF]` values as (type, ref); a refusal for a type that is not one."""
    from chantier.core import waits  # noqa: PLC0415 - slow import

    specs: list[tuple[str, str | None]] = []
    for value in args.wait or []:
        type_, _, ref = value.partition("=")
        if type_ not in waits.TYPES:
            raise ChantierError(
                f"--wait: {type_} is not a wait type: answer, approval, pipeline or merge",
                EXIT_PRECONDITION,
            )
        if type_ == "answer" and not ref.strip():
            raise ChantierError(
                '--wait answer needs the question: --wait answer="<question>"', EXIT_PRECONDITION
            )
        specs.append((type_, ref.strip() or None))
    return specs


def handback_blocked(
    b: Batch,
    c: CrEntry,
    note: str,
    line: str,
    applied: tuple[list[dict[str, Any]], list[str]] = ([], []),
) -> list[str]:
    """The blocked hand-back; `applied` is the waits its `--wait` added and the lines about them."""
    cr = c.id
    added, outside = applied
    b.log("handback", cr, result="blocked", note=note)
    b.touch(c, status="blocked", blocked_reason=note)
    c.clear_phase()
    if added:
        kinds = ", ".join(f"{w['id']} {w['type']}" for w in added)
        return [
            f"{line}; waits: {kinds}",
            f"{cr} waits; the Foreman takes it back when that lands",
            *outside,
        ]
    if note.lower().startswith("waits:"):
        return [line, f"{cr} waits; the Foreman takes it back when that lands"]
    if note.lower().startswith("context: closing"):
        return [
            line,
            f"{cr} verified; the Foreman restarts a fresh Driver for the closing step, "
            "with no ask to the Chief of Staff",
        ]
    if note.lower().startswith("context:"):
        return [
            line,
            f"{cr} out of context; the Foreman restarts a fresh Driver "
            "from this state, with no ask to the Chief of Staff",
        ]
    return [line, f"{cr} blocked; the Foreman asks the Chief of Staff"]


CONFLICT = "the rebase resolved a conflict"


def _voided(
    events: list[EventRecord], kind: str, judged: Callable[[list[EventRecord]], Judged | None]
) -> Judged | None:
    """What a `ship --conflict` cut off, when nothing of `kind` was judged after it."""
    cut = conflict_cut(events)
    if cut < 0 or any(e.kind == kind for e in events[cut + 1 :]):
        return None
    return judged(events[:cut])


def _carry_why(repo: Repo, b: Batch, c: CrEntry, j: Judged | None, what: str) -> tuple[str, str]:
    """(the judged head to name, the reason it does not carry to the CR's head), or (its original
    head, "") when it carries."""
    if j is None:
        return "", ""
    wt = cr_worktree(c)
    why = carry_reason(wt, j, str(c.head), head_base(repo, b.record, c, wt, str(c.head)), what)
    return (j.head, why) if why else (j.origin, "")


def _gate_missing(repo: Repo, b: Batch, c: CrEntry, events: list[EventRecord]) -> tuple[str, str]:
    """The refusal for a head with no gate pass, and the head of the pass that carries to it
    (the CR's own commits have the same exact patch-ids, proved by git); the first is empty when
    one carries."""
    head = c.head
    if done := carry_at(events, head, "gate_from"):
        return "", str(done.gate_from)
    text = (
        f"refused: no long gate passed at {head or 'any head'} (gate "
        f'{c.id} "<cmd>"..., or --no-gate "<the project\'s rule>")'
    )
    j = judged_gate(events)
    voided = _voided(events, "gate", judged_gate) if j is None else None
    if not (j or voided) or not head:
        return text, ""
    g, why = (
        _carry_why(repo, b, c, j, "pass") if j else (voided.head, CONFLICT) if voided else ("", "")
    )
    if not why:
        return "", g
    clause = f"(the pass at {short_head(g)} does not carry: {why}) (gate"
    return text.replace("(gate", clause, 1), ""


def _verdict_missing(
    repo: Repo, b: Batch, c: CrEntry, events: list[EventRecord]
) -> tuple[str, str]:
    """The refusal for a head with no verdict VERIFIED, and the head of the verdict that carries
    to it (a clean rebase of the verified commits, proved by git); the first is empty when one
    carries."""
    head = c.head
    if done := carry_at(events, head, "verdict_from"):
        return "", str(done.verdict_from)
    last = last_verdict(events, head) or "none"
    text = f"refused: no verdict VERIFIED at {head or 'any head'} (the last verdict there: {last})"
    j = judged_verdict(events)
    voided = _voided(events, "verdict", judged_verdict) if j is None else None
    if not (j or voided) or not head:
        return text, ""
    v, why = (
        _carry_why(repo, b, c, j, "verdict")
        if j
        else (voided.head, CONFLICT)
        if voided
        else ("", "")
    )
    if not why:
        return "", v
    clause = f"(the verdict VERIFIED at {short_head(v)} does not carry: {why}) (the last"
    return text.replace("(the last", clause, 1), ""


@dataclass
class GateBasis:
    """What let a ready hand-back pass its long gate, when it is not a pass at its own head: the
    head of the pass carried over a clean rebase, or the waiver recorded for the CR."""

    carried: str = ""
    waiver: GateWaiver | None = None
    validated_by: str = ""
    verdict_carried: str = ""

    def words(self) -> str:
        """The waiver as the hand-back line and the event say it."""
        w = self.waiver
        if w is None:
            return ""
        why = (
            f"validated by {self.validated_by}'s gate"
            if self.validated_by
            else (f"follow-up {w.follow_up}")
        )
        return f"long gate waived ({w.order}): {why}"

    def event_keys(self) -> dict[str, str]:
        """What the `handback` event records of the basis: the carried head, the waiver."""
        w = self.waiver
        carried = {"gate_from": self.carried} if self.carried else {}
        if self.verdict_carried:
            carried["verdict_from"] = self.verdict_carried
        if w is None:
            return carried
        return {
            **carried,
            "gate_waiver": w.order,
            "gate_waiver_scope": w.scope,
            "gate_waiver_words": self.words(),
            "waiver_note": w.note,
            **({"validated_by": self.validated_by} if self.validated_by else {}),
            **({"follow_up": w.follow_up} if w.follow_up else {}),
        }


def handback_refusals(
    repo: Repo, b: Batch, c: CrEntry, no_gate: str | None, prepared: bool
) -> GateBasis:
    """A ready CR is shipped at the worktree's head, clean, pushed, gated and verified. A CR
    whose long gate is waived (`order waive`) and is not the stack's top needs no gate pass. The
    basis that let it pass, if it is not a pass at its head."""
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
    basis = GateBasis()
    waiver = waived_gate(b.record, c) if no_gate is None else None
    if waiver is not None:
        top = validating_cr(b.record, c)
        basis = GateBasis(waiver=waiver, validated_by=top.id if top else "")
    elif no_gate is None and not gate_passed(events, head):
        text, basis.carried = _gate_missing(repo, b, c, events)
        if text:
            missing.append(text)
    if not prepared and last_verdict(events, head) != "VERIFIED":
        text, basis.verdict_carried = _verdict_missing(repo, b, c, events)
        if text:
            missing.append(text)
    if missing:
        raise ChantierError("\n".join(missing), EXIT_PRECONDITION)
    return basis


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

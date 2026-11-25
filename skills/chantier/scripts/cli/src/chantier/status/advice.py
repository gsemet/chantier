"""The advice of `chantier next` and of the `next:` lines, from one place: a CR's next step
(`DRIVER_STEPS` walked on the record, the events and the worktree's facts) and the steering
session's due list (`status/due.py`). It reads only: a safety step stays its command's refusal."""

from __future__ import annotations

from collections.abc import Callable
from typing import NamedTuple

from chantier.commands.crs import carry_at, cr_events, last_verdict
from chantier.core.driver_steps import DRIVER_STEPS, HANDED_BACK, Step
from chantier.core.errors import ChantierError
from chantier.core.git import git
from chantier.core.heads import gate_passed, same_head
from chantier.core.ids import normalize_cr
from chantier.core.records import BatchRecord, CrEntry, EventRecord, read_events
from chantier.core.repo import Repo
from chantier.playbook.long_gate import load_long_gate
from chantier.stacks import waived_gate
from chantier.status.due import due
from chantier.status.now_next import now_next
from chantier.status.words import waits

QUIET = {"round", "note", "phase", "lease", "lease-late"}  # events that leave a round untouched
NO_RULE = ' --no-gate "<the project\'s rule>"'


class Facts(NamedTuple):
    """What the worktree says: its head ("" with no worktree), uncommitted changes, the head of
    the remote-tracking branch ("" when not pushed), the remote's name and the long gate's names."""

    head: str
    dirty: bool
    pushed: str
    remote: str
    gates: tuple[str, ...]


def read_facts(repo: Repo, c: CrEntry) -> Facts:
    """The reads `verdict` and `handback_refusals` make, with no fetch and no network."""
    remote, gates = str(repo.config["remote"]), tuple(load_long_gate(repo).commands)
    wt, none = c.worktree, Facts("", False, "", remote, gates)
    try:  # git refuses a folder that is not there: no worktree yet
        head = git("rev-parse", "HEAD", cwd=wt, check=False) if wt else ""
    except ChantierError:
        return none
    if not head:
        return none
    dirty = bool(git("status", "--porcelain", "--untracked-files=normal", cwd=wt, check=False))
    ref = f"{remote}/{c.branch}"
    pushed = git("rev-parse", "--verify", "--quiet", ref, cwd=wt, check=False) if c.branch else ""
    return Facts(head, dirty, pushed, remote, gates)


def to_whom(d: BatchRecord) -> str:
    """Who hears a hand-back: the steering session."""
    return "the Chief of Staff" if d.steering == "direct" else "the Foreman"


class _At(NamedTuple):
    d: BatchRecord
    c: CrEntry
    events: list[EventRecord]
    f: Facts


def _in_round(a: _At) -> bool:
    """The round's work is in: a commit since `round`, or a command of the round after it."""
    at = [i for i, e in enumerate(a.events) if e.kind == "round"]
    if not at or not a.f.head:  # no round recorded; no worktree yet: the round's Coder
        return not at
    last = a.events[at[-1]]
    moved = bool(last.wt_head) and not same_head(last.wt_head, a.f.head)
    return moved or any(e.kind not in QUIET for e in a.events[at[-1] + 1 :])


def _gated(a: _At) -> bool:
    head = a.f.head
    return (
        not a.f.gates
        or gate_passed(a.events, head)
        or carry_at(a.events, head, "gate_from") is not None
        or waived_gate(a.d, a.c) is not None
    )


def _ci(a: _At) -> bool:
    seen = any(e.kind == "verdict" and same_head(e.head, a.f.head) for e in a.events)
    return a.c.phase == "verifier" or seen


def _verified(a: _At) -> bool:
    return (
        last_verdict(a.events, a.f.head) == "VERIFIED"
        or carry_at(a.events, a.f.head, "verdict_from") is not None
    )


DONE: dict[str, Callable[[_At], bool]] = {
    "round": lambda a: a.c.round >= 1,
    "in-round": _in_round,
    "dirty": lambda a: not a.f.dirty,
    "gate": _gated,
    "push": lambda a: bool(a.f.head) and same_head(a.f.pushed, a.f.head),
    "ship": lambda a: bool(a.c.pr) and same_head(a.c.head, a.f.head),
    "ci": _ci,
    "verdict": _verified,
    "handback": lambda a: a.c.status != "working",
}


def _other(a: _At, s: Step) -> bool:
    """The step's other words: a gate failed or a verdict NOT VERIFIED at the head, no PR, or an
    in-round with no long gate named."""
    if s.name == "gate":
        return any(e.kind == "gate" and same_head(e.head, a.f.head) for e in a.events)
    if s.name == "verdict":
        return last_verdict(a.events, a.f.head) == "NOT VERIFIED"
    return (s.name == "ship" and not a.c.pr) or (s.name == "in-round" and not a.f.gates)


def fields(d: BatchRecord, c: CrEntry, f: Facts) -> dict[str, str]:
    """The values the steps' words take."""
    several = len(f.gates) > 1
    return {
        "cr": c.id,
        "n": str(c.lease.n) if c.lease else "<n>",
        "h": f.head[:7],
        "pr": c.pr or "<pr link>",
        "worktree": c.worktree,
        "gate": f.gates[0] if len(f.gates) == 1 else "<name>",
        "named": f" (named: {', '.join(f.gates)})" if several else "",
        "remote": f.remote,
        "branch": c.branch,
        "pushed": f"at {f.pushed[:7]}" if f.pushed else "not pushed",
        "to": to_whom(d),
        "no_gate": "" if f.gates else NO_RULE,
    }


def driver_step(d: BatchRecord, c: CrEntry, events: list[EventRecord], f: Facts) -> str:
    """The words of the first step of `DRIVER_STEPS` not done."""
    a = _At(d, c, events, f)
    s = next((s for s in DRIVER_STEPS if not DONE[s.name](a)), DRIVER_STEPS[-1])
    text = s.other if s.other and _other(a, s) else s.text
    return text.format(**fields(d, c, f))


def cr_step(
    repo: Repo, d: BatchRecord, c: CrEntry, events: list[EventRecord], f: Facts | None = None
) -> str:
    """A CR's next step: a working CR's from the steps; the release's and any other's from the
    sentences its view shows (`now_next`), which name who acts."""
    if c.status != "working":
        return now_next(repo, d, c, waits(d, c))[1]
    if c.kind == "release":
        return now_next(repo, d, c, waits(d, c))[0]
    return driver_step(d, c, events, f or read_facts(repo, c))


def next_line(out: list[str], text: str) -> list[str]:
    """`next: <text>`, or none when the output already holds a `next:` line."""
    return [] if any(x.startswith("next: ") for x in out) else [f"next: {text}"]


def step_after(repo: Repo, batch: str, d: BatchRecord, cr_id: str, out: list[str]) -> list[str]:
    """The `next:` line of a Driver's command, on the record read again after it."""
    cr_id = normalize_cr(cr_id)
    c = next(x for x in d.crs if x.id == cr_id)
    return next_line(out, cr_step(repo, d, c, cr_events(repo, batch, cr_id)))


def handed_back(d: BatchRecord, out: list[str]) -> list[str]:
    """The `next:` line of `handback`, ready or blocked."""
    return next_line(out, HANDED_BACK.format(to=to_whom(d)))


def first_due(repo: Repo, d: BatchRecord) -> str:
    """The first due item, and how many more `next --epoch` lists; `nothing due: wait`."""
    items = due(repo, d, read_events(repo.store, repo.batch_dir(d.id)))
    if not items:
        return "nothing due: wait"
    more = len(items) - 1
    rest = f" (+{more} more: `next --epoch {d.foreman_epoch}`)" if more else ""
    return items[0].text + rest

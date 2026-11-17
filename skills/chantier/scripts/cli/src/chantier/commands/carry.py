"""The base a head sits on, and the carry `ship` records over a rebase."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import NamedTuple

from chantier.commands.crs import (
    Judged,
    carry_at,
    carry_check,
    cr_worktree,
    judged_gate,
    judged_verdict,
    last_verdict,
    short_head,
)
from chantier.core.errors import ChantierError
from chantier.core.git import git
from chantier.core.heads import gate_passed
from chantier.core.records import BatchRecord, CrEntry, EventRecord
from chantier.core.repo import Repo
from chantier.stacks import stack_base


class Base(NamedTuple):
    """The branch a head sits on and its remote tip's full SHA."""

    branch: str
    sha: str


def _ancestor(wt: Path, older: str, newer: str) -> bool:
    p = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer],
        cwd=wt,
        capture_output=True,
        check=False,
    )
    return p.returncode == 0


def head_base(repo: Repo, d: BatchRecord, c: CrEntry, wt: Path, head: str) -> Base | None:
    """The base a head actually sits on: of the start base, the PR's base as `ship` last read it
    and the planned place, each one's remote tip that is an ancestor of the head, the nearest
    to the head. None when none is: the head sits on none of them. Read only."""
    names = [stack_base(d, c, repo), c.pr_base or "", stack_base(d, c, repo, planned=True)]
    found: dict[str, Base] = {}
    for name in dict.fromkeys(n for n in names if n):
        tip = git(
            "rev-parse",
            "--verify",
            "--quiet",
            f"{repo.config['remote']}/{name}",
            cwd=wt,
            check=False,
        )
        if tip and _ancestor(wt, tip, head):
            found.setdefault(tip, Base(name, tip))
    if not found:
        return None
    # the nearest: the one fewest commits below the head (every other tip is its ancestor)
    return min(
        found.values(), key=lambda b: int(git("rev-list", "--count", f"{b.sha}..{head}", cwd=wt))
    )


def base_keys(base: Base | None) -> dict[str, str]:
    """The `base` key a `gate` or `verdict` event records: none when no base was found."""
    return {"base": base.sha} if base else {}


def carry_reason(wt: Path, j: Judged, head: str, base: Base | None, what: str) -> str | None:
    """Why the pass or verdict judged at `j` does not carry to `head` on `base`, or None. A ref
    git cannot read gives the reason `<ref> cannot be read`."""
    try:
        return carry_check(wt, j, head, base.sha if base else None, what)
    except ChantierError as e:
        return str(e)


def ship_carry(
    repo: Repo, d: BatchRecord, c: CrEntry, head: str, events: list[EventRecord]
) -> tuple[dict[str, str], list[str]]:
    """What `ship` (without `--conflict`) records of a pass and a verdict that carry to the head
    it ships: the `carry` event's keys (empty when nothing carried) and the lines to print
    (`carried:` and `off:`). A head with its own judgment or a carry already needs nothing."""
    wt = cr_worktree(c)
    base = head_base(repo, d, c, wt, head)
    wanted = [("gate_from", "pass", judged_gate(events), gate_passed(events, head))]
    if c.kind != "release":
        own = last_verdict(events, head) == "VERIFIED"
        wanted.append(("verdict_from", "verdict", judged_verdict(events), own))
    keys: dict[str, str] = {}
    off: list[str] = []
    for key, what, j, own in wanted:
        if own or j is None or carry_at(events, head, key):
            continue
        why = carry_reason(wt, j, head, base, what)
        if why is None:
            keys[key] = j.origin
        else:
            noun = "pass" if what == "pass" else "verdict VERIFIED"
            off.append(f"the {noun} at {short_head(j.head)} does not carry: {why}")
    if keys:
        keys = {"head": head, "base": base.sha if base else "", **keys}
    return keys, _lines(keys, base, off)


def _lines(keys: dict[str, str], base: Base | None, off: list[str]) -> list[str]:
    gate, verdict = keys.get("gate_from"), keys.get("verdict_from")
    onto = f"(clean rebase onto {base.branch if base else '?'})"
    if gate and verdict and gate == verdict:
        said = f"long gate and verdict from {short_head(gate)}"
    elif gate or verdict:
        said = " and ".join(
            f"{word} from {short_head(sha)}"
            for word, sha in (("long gate", gate), ("verdict", verdict))
            if sha
        )
    else:
        return [f"off: {x}" for x in off]
    return [f"carried: {said} {onto}", *[f"off: {x}" for x in off]]

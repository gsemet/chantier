"""The facts of a CR for any agent: `chantier handoff`."""

from __future__ import annotations

import argparse
from pathlib import Path

from chantier.commands import wait_view
from chantier.commands.carry import carry_reason, head_base
from chantier.commands.crs import (
    batch_cr,
    carry_at,
    cr_events,
    cr_worktree,
    grant_line,
    judged_gate,
    judged_verdict,
    last_verdict,
    short_head,
)
from chantier.commands.forge_base import stacked_read
from chantier.commands.forge_stack_gitlab import GITLAB_LINK
from chantier.core import leases
from chantier.core.heads import gate_passed
from chantier.core.records import BatchRecord, CrEntry, EventRecord, ReleaseGrant, round_limit
from chantier.core.repo import Repo
from chantier.lifecycle.stages import cr_directory
from chantier.playbook.lines import ci_lines, team_lines, timing_lines
from chantier.plugin_files import (
    archive_path,
    cli_command,
    project_instructions,
    recorded_timing,
    skill_dir,
    worker_prompt_lines,
)
from chantier.stacks import (
    chain,
    held_lines,
    off_place,
    stack_base,
    start_base,
    state_word,
    validated_ids,
    validating_cr,
    waived_gate,
)
from chantier.status.gate import pr_number
from chantier.status.views import shown_title


def _ref(repo: Repo, branch: str) -> str:
    return (
        f"{repo.config['remote']}/{branch}" if branch == repo.config["default_branch"] else branch
    )


def _base_of(d: BatchRecord, c: CrEntry, repo: Repo) -> str:
    """The `base <ref>` a CR's `worktree:` line ends with: the ref its branch starts on (the
    remote's default branch, or the branch of its last open dependency); for a stacked CR with a
    PR, the PR's base read from the forge, or `base ? (not read from <link>: …)`."""
    read = stacked_read(d, c)
    if read is not None:
        branch, unread = read
        return f"base {_ref(repo, branch)}" if branch else unread
    return f"base {_ref(repo, start_base(d, c, repo))}"


def _stack_ref(d: BatchRecord, c: CrEntry, repo: Repo) -> str:
    """The ref under the CR's PR in the stack, which the stack driver sets."""
    return _ref(repo, stack_base(d, c, repo, planned=True))


def cr_facts(repo: Repo, batch: str, d: BatchRecord, c: CrEntry) -> list[str]:
    """Everything an agent needs to work on a CR, on one screen: the parent writes its prompt
    from these lines and the role's card."""
    folder = cr_directory(repo, c)
    found = project_instructions(repo)
    skill = skill_dir().as_posix()
    made = Path(c.worktree).is_dir()
    title = shown_title(c.title, folder)
    lines = [
        f'{c.id} "{title}" ({c.kind}) {state_word(d, c, repo)} in batch {batch} ({d.mode})',
        f"cli: {cli_command(repo)} <command> --batch {batch}",
        f"cards: {skill}/references/ (driver.md, concepts.md; each worker's own card, named in "
        "its opening lines); the project's rules rank above them: `rules`",
        f"project instructions: {found.as_posix() if found else 'none'}",
        f"specification: {(folder / c.specification).as_posix()}",
        f"folder: {folder.as_posix()} (work/, evidence/)",
        f"scratch: {(folder / 'work' / 'scratch').as_posix()}",
        f"worktree: {c.worktree} branch {c.branch} {_base_of(d, c, repo)}"
        + ("" if made else "; not created yet: a Driver creates it first"),
        *_external_lines(repo, c),
        f"PR: {_shown_pr(c)}; head {short_head(c.head) or '-'}",
        f"rounds: {c.round} of {round_limit(d, c)}",
    ]
    lines += _status_lines(d, c)
    if wait_text := wait_view.wait_line(repo, d, c):
        lines.append(wait_text)
    if c.kind not in {"release"}:
        lines += _gate_lines(repo, batch, d, c)
    lines += _gate_log(folder)
    return (
        lines
        + team_lines(d.playbook)
        + ci_lines(d.playbook)
        + timing_lines(recorded_timing(d), d.host)
        + worker_prompt_lines(repo.root.as_posix(), (c.id, title), batch, d)
        + [
            "worker writes line (copy it unchanged, without the two leading spaces, into each "
            "worker's prompt):",
            f"  writes: {Path(c.worktree).as_posix()}; {folder.as_posix()}",
        ]
    )


def _external_lines(repo: Repo, c: CrEntry) -> list[str]:
    """The clone and the archive, which only an external planning surface has."""
    if not repo.external:
        return []
    path = archive_path(repo, c)
    return [
        f"clone: {repo.clone.as_posix()} (`git -C` it to create the worktree)",
        f"archive: in the PR at {path}" if path else "archive: not in the PR",
    ]


def _status_lines(d: BatchRecord, c: CrEntry) -> list[str]:
    """What sets the CR apart: blocked, release grant, dependencies, fix, drafts, orders, notes."""
    lines = []
    if c.status == "blocked":
        lines.append(f"blocked: {c.blocked_reason}")
    if c.kind == "release":
        lines.append(
            f"grant: {grant_line(d.release or ReleaseGrant())}; attempts {c.attempts}; "
            f"approvals unused: {'; '.join(c.approvals) or 'none'}"
        )
    if c.after:
        lines.append(
            f"after: {', '.join(c.after)} (a release starts on the top CR's branch "
            "in an ordered batch, on the default branch once the others are merged in a "
            "parallel one)"
            if c.kind == "release"
            else f"after: {', '.join(c.after)} (the base is the branch of the last one still open)"
        )
    if c.kind == "fix":
        lines.append(f"fix for {c.fix_for}: the release starts again once this merges")
    if c.drafts:
        lines.append("drafts: " + "; ".join(c.drafts))
    pending = [o for o in d.orders if not o.done and o.cr == c.id]
    if pending:
        lines.append(
            "orders pending: " + "; ".join(f"{o.id} {o.kind} {o.note}".rstrip() for o in pending)
        )
    lines += ["notes:"] + [f"  {n}" for n in c.notes[-10:]] if c.notes else ["notes: none"]
    return lines


def _waiver_line(d: BatchRecord, c: CrEntry) -> str | None:
    """The one `gate:` line a waiver sets: covered, or the stack's top that validates."""
    w = waived_gate(d, c)
    if w is not None:
        top = validating_cr(d, c)
        by = f"validated by {top.id}" if top else f"follow-up {w.follow_up}"
        return f"gate: waived ({w.order}, {w.scope}): run no long gate; {by}"
    covers = validated_ids(d, c)
    if covers:
        return f"gate: this CR's long gate validates the stack ({', '.join([*covers, c.id])})"
    return None


def _carried_lines(
    repo: Repo, d: BatchRecord, c: CrEntry, events: list[EventRecord]
) -> tuple[str, str]:
    """For the gate box and the verdict box, `carried from <sha7> (clean rebase onto <base>)`
    when the pass or the verdict at an older head carries to this head (proved by git, as the
    hand-back does), else an empty string. Read only."""
    head = c.head
    if not head or not (c.worktree and Path(c.worktree).is_dir()):
        return "", ""
    wt = cr_worktree(c)
    mine = head_base(repo, d, c, wt, head)
    base = mine.branch if mine else stack_base(d, c, repo)
    out = []
    for key, j, have in (
        ("gate_from", judged_gate(events), gate_passed(events, head)),
        ("verdict_from", judged_verdict(events), last_verdict(events, head) == "VERIFIED"),
    ):
        done = carry_at(events, head, key)
        if done and not have:
            out.append(
                f"carried from {short_head(str(getattr(done, key)))} (clean rebase onto {base})"
            )
            continue
        what = "pass" if key == "gate_from" else "verdict"
        ok = j is not None and not have and carry_reason(wt, j, head, mine, what) is None
        out.append(
            f"carried from {short_head(j.origin)} (clean rebase onto {base})" if ok and j else ""
        )
    return out[0], out[1]


def _gate_lines(repo: Repo, batch: str, d: BatchRecord, c: CrEntry) -> list[str]:
    events = cr_events(repo, batch, c.id)
    head = c.head
    verdict = last_verdict(events, head)
    waiver = _waiver_line(d, c)
    waived = waived_gate(d, c) is not None
    long_gate = (
        [
            f"  [{'x' if gate_passed(events, head) else ' '}] long gate passed (gate "
            f'{c.id} "<cmd>" ["<cmd>"...]; none in the project\'s rules: handback '
            f'{c.id} ready --no-gate "<rule>")'
        ]
        if not waived
        else ["  [-] long gate waived (see the gate: line)"]
    )
    carried = _carried_lines(repo, d, c, events)
    if carried[0] and not gate_passed(events, head) and not waived:
        long_gate = [f"  [x] long gate passed {carried[0]}"]
    verdict_box = (
        f"  [x] verdict VERIFIED {carried[1]}"
        if carried[1] and verdict != "VERIFIED"
        else f"  [{'x' if verdict == 'VERIFIED' else ' '}] verdict "
        f"{verdict if verdict == 'NOT VERIFIED' else 'VERIFIED'}"
    )
    return [
        *([waiver] if waiver else []),
        f"gates before handback ready, at the PR's head {head or 'not shipped yet'} "
        "(the full SHA; the gate log's first line names it):",
        *long_gate,
        f'{verdict_box} (the Verifier: verdict {c.id} VERIFIED|"NOT VERIFIED")',
    ]


def _gate_log(folder: Path) -> list[str]:
    gates = folder / "work" / "gates"
    logs = sorted(gates.glob("*.log")) if gates.is_dir() else []
    if not logs:
        return []
    tail = logs[-1].read_text(encoding="utf-8", errors="replace").splitlines()[-5:]
    return [f"last gate log {logs[-1].name}:"] + [f"  {ln}" for ln in tail]


def handoff(args: argparse.Namespace) -> list[str]:
    """The CR's facts, for any agent; changes nothing."""
    repo = Repo.find()
    batch, d, c = batch_cr(repo, args.cr, args.batch)
    lines = cr_facts(repo, batch, d, c)
    if c.lease is not None:
        lines.append(leases.line(repo, c.id, c.lease))
    return lines


def _shown_pr(c: CrEntry) -> str:
    """The CR's PR for an agent: the link, marked `(merged)` when it is the release PR its merge
    recorded, else `none`."""
    shown = c.shown_pr()
    if not shown:
        return "none"
    return shown if c.pr else f"{shown} (merged)"


def stack_lines(repo: Repo, batch: str, d: BatchRecord) -> list[str]:
    """The stack as it stands: the chain line, then one line per CR (what `take stack` and
    `stack` with no CR print)."""
    crs = chain(d)
    return (
        [f"the stack of batch {batch}: {' → '.join(x.id for x in crs)}"]
        + [
            f"{x.id} {stack_label(x)} worktree {x.worktree} branch {x.branch} "
            f"base {_stack_ref(d, x, repo)} PR {_shown_pr(x)} head {short_head(x.head) or '-'} "
            f"{_last_restack(x)}{_off_place_tail(d, x, repo)}"
            for x in crs
        ]
        + held_lines(d, repo)
    )


def stack_label(c: CrEntry) -> str:
    """A stack row's label: the CR's recorded status, then, with a PR, its draft flag as last
    recorded and its number (`ready, PR draft (#251)`)."""
    if not c.pr:
        return c.status
    flag = "draft not read" if c.pr_draft is None else "draft" if c.pr_draft else "out of draft"
    gl = GITLAB_LINK.match(c.pr)
    ref = f"!{gl[3]}" if gl else pr_number(c.pr)
    return f"{c.status}, PR {flag}" + (f" ({ref})" if ref else "")


def _off_place_tail(d: BatchRecord, c: CrEntry, repo: Repo) -> str:
    """The end of a stack row for a working CR whose PR is not on its place: it is to come."""
    off = off_place(d, c, repo)
    if off is None:
        return ""
    return (
        f" not on its place: its PR is on {off[0]}; to come until its Driver rebases "
        f"(note rebase: stacked on {off[1]})"
    )


def _last_restack(c: CrEntry) -> str:
    """The CR's last note that starts with `restack:`, whole; `restack: none` with no such note."""
    found = [n for n in c.notes if n.startswith("restack:")]
    return found[-1] if found else "restack: none"

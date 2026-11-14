"""The facts of a CR for any agent: `chantier handoff`."""

from __future__ import annotations

import argparse
from pathlib import Path

from chantier.commands.crs import (
    batch_cr,
    cr_events,
    gate_passed,
    grant_line,
    last_verdict,
    short_head,
)
from chantier.core.records import BatchRecord, CrEntry, ReleaseGrant, round_limit
from chantier.core.repo import Repo
from chantier.lifecycle.convert import open_repo
from chantier.lifecycle.stages import cr_directory
from chantier.playbook.lines import ci_lines, team_lines
from chantier.plugin_files import archive_path, cli_command, project_instructions, skill_dir
from chantier.stacks import chain, stack_base, start_base, state_word


def _ref(repo: Repo, branch: str) -> str:
    return (
        f"{repo.config['remote']}/{branch}" if branch == repo.config["default_branch"] else branch
    )


def _base_of(d: BatchRecord, c: CrEntry, repo: Repo) -> str:
    """The ref the CR's branch starts on: the remote's default branch, or the branch of its
    last open dependency."""
    return _ref(repo, start_base(d, c, repo))


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
    lines = [
        f'{c.id} "{c.title}" ({c.kind}) {state_word(d, c, repo)} in batch {batch} ({d.mode})',
        f"cli: {cli_command(repo)} <command> --batch {batch}",
        f"cards: {skill}/references/ (driver.md, worker.md, concepts.md); the project's "
        "rules rank above them: `rules`",
        f"project instructions: {found.as_posix() if found else 'none'}",
        f"specification: {(folder / c.specification).as_posix()}",
        f"folder: {folder.as_posix()} (work/, evidence/)",
        f"worktree: {c.worktree} branch {c.branch} base {_base_of(d, c, repo)}"
        + ("" if made else "; not created yet: a Driver creates it first"),
        *(
            [f"clone: {repo.clone.as_posix()} (`git -C` it to create the worktree)"]
            if repo.external
            else []
        ),
        *(
            [
                f"archive: in the PR at {archive_path(repo, c)}"
                if archive_path(repo, c)
                else "archive: not in the PR"
            ]
            if repo.external
            else []
        ),
        f"PR: {c.pr or 'none'}; head {short_head(c.head) or '-'}",
        f"rounds: {c.round} of {round_limit(d, c)}",
    ]
    lines += _status_lines(d, c)
    if c.kind not in {"release"}:
        lines += _gate_lines(repo, batch, c)
    lines += _gate_log(folder)
    return lines + team_lines(d.playbook) + ci_lines(d.playbook)


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


def _gate_lines(repo: Repo, batch: str, c: CrEntry) -> list[str]:
    events = cr_events(repo, batch, c.id)
    head = c.head
    verdict = last_verdict(events, head)
    return [
        f"gates before handback ready, at the PR's head {head or 'not shipped yet'} "
        "(the full SHA; the gate log's first line names it):",
        f"  [{'x' if gate_passed(events, head) else ' '}] long gate passed (gate "
        f'{c.id} "<cmd>" ["<cmd>"...]; none in the project\'s rules: handback '
        f'{c.id} ready --no-gate "<rule>")',
        f"  [{'x' if verdict == 'VERIFIED' else ' '}] verdict "
        f"{verdict if verdict == 'NOT VERIFIED' else 'VERIFIED'} (the Verifier: verdict "
        f'{c.id} VERIFIED|"NOT VERIFIED")',
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
    repo = open_repo()
    batch, d, c = batch_cr(repo, args.cr, args.batch)
    return cr_facts(repo, batch, d, c)


def stack_lines(repo: Repo, batch: str, d: BatchRecord) -> list[str]:
    """The stack as it stands: the chain line, then one line per CR (what `take stack` and
    `stack` with no CR print)."""
    crs = chain(d)
    return [f"the stack of batch {batch}: {' → '.join(x.id for x in crs)}"] + [
        f"{x.id} {state_word(d, x, repo)} worktree {x.worktree} branch {x.branch} "
        f"base {_stack_ref(d, x, repo)} PR {x.pr or 'none'} head {short_head(x.head) or '-'} "
        f"{_last_restack(x)}"
        for x in crs
    ]


def _last_restack(c: CrEntry) -> str:
    """The CR's last note that starts with `restack:`, whole; `restack: none` with no such note."""
    found = [n for n in c.notes if n.startswith("restack:")]
    return found[-1] if found else "restack: none"

"""`chantier forge-stack`: the native stack on the forge."""

from __future__ import annotations

import argparse
import json
from typing import Any

from chantier.commands import forge_stack_apart as off_stack
from chantier.commands import forge_stack_gitlab as gitlab
from chantier.commands.crs import short_head
from chantier.commands.forge_stack_apart import Moved
from chantier.commands.forge_stack_gh import (
    PR_LINK,
    Apart,
    Unreadable,
    gh,
    pr_parts,
    retarget,
    stacks,
    unstack,
    unstack_action,
)
from chantier.commands.forge_stack_gitlab import GITLAB_LINK
from chantier.commands.forge_stack_shared import Where, draft_checks, left, ready_tail
from chantier.core import leases
from chantier.core.batch import read_batch, resolve_batch
from chantier.core.errors import EXIT_EXTERNAL, EXIT_PRECONDITION, ChantierError
from chantier.core.records import BatchRecord, CrEntry
from chantier.core.repo import Repo
from chantier.stacks import chain, off_place, stack_base, state_word, to_come

Rows = list[dict[str, Any]]


def _is_gitlab(rows: list[dict[str, Any]]) -> bool:
    return GITLAB_LINK.match(rows[0]["link"]) is not None


class NoBottom(ChantierError):
    """The stack's first CR has no PR: nothing to stack."""


def _plan(
    args: argparse.Namespace,
) -> tuple[Rows, Rows, Where, dict[int, str], dict[int, str], Moved]:
    """The stack as it stands: the rows (the bottom CRs with a PR on its place, whatever their
    status: cr, status, PR number, link, base, head, release), the CRs to come (those from the
    first with no PR, or a working one off its place or not placed by the stack driver yet, up:
    cr, status, PR number or None), the forge's host, owner and repository, read from the PR
    links, the PR numbers of the batch's trashed CRs (to their CR ids), those of its held CRs (to
    their CR ids: a held PR is outside the stack, on the default branch), and those of its CRs
    moved to the inbox or the backlog (to their CR id and folder)."""
    repo = Repo.find()
    data = read_batch(repo, resolve_batch(repo, args.batch))
    if data.mode != "stack":
        raise ChantierError(f"batch {data.id} is not a stack", EXIT_PRECONDITION)
    links = chain(data)
    if not links:
        raise ChantierError(f"batch {data.id} has no open CR in its stack", EXIT_PRECONDITION)
    rows: list[dict[str, Any]] = []
    where = None
    for c in links:
        if not c.pr or to_come(data, c, repo):  # to come: see `to_come`
            break
        host, owner, name, number = pr_parts(c.pr)
        if where not in (None, (host, owner, name)):
            raise ChantierError("the stack's PRs are not all in one repository", EXIT_PRECONDITION)
        where = (host, owner, name)
        rows.append(_row(data, repo, c, number))
    if where is None:
        raise _no_bottom(data, repo, links[0])
    return (
        rows,
        _come(data, repo, links[len(rows) :]),
        where,
        off_stack.dropped(data),
        off_stack.held(data),
        off_stack.moved(data),
    )


def _row(data: BatchRecord, repo: Repo, c: CrEntry, number: str) -> dict[str, Any]:
    """One CR of the stack with a PR on its place: cr, status, word, recorded draft state, PR
    number, link, base, branch, head, release, default branch."""
    return {
        "cr": c.id,
        "status": c.status,
        "word": state_word(data, c, repo),
        "recorded": c.pr_draft,
        "number": int(number),
        "link": c.pr,
        "base": stack_base(data, c, repo, planned=True),
        "branch": c.branch,
        "head": short_head(c.head) or "-",
        "release": c.kind == "release",
        "default": repo.config["default_branch"],
    }


def _no_bottom(data: BatchRecord, repo: Repo, first: CrEntry) -> NoBottom:
    """The refusal when no PR stands at the bottom: none, or a working one off its place."""
    off = off_place(data, first, repo) if first.pr else None
    if first.pr and not off and first.status == "working" and not first.stacked:
        return NoBottom(
            f"no PR placed at the bottom of the stack: {first.id} is working and the stack "
            f"driver has not placed its PR {first.pr} yet",
            EXIT_PRECONDITION,
        )
    if off:
        planned = stack_base(data, first, repo, planned=True)
        return NoBottom(
            f"no PR placed at the bottom of the stack: {first.id} is working and its PR "
            f"{first.pr} is on {off[0]}, not on {planned}",
            EXIT_PRECONDITION,
        )
    return NoBottom(
        f"no PR at the bottom of the stack: {first.id} is {first.status}, no PR", EXIT_PRECONDITION
    )


def _come(data: BatchRecord, repo: Repo, rest: list[CrEntry]) -> list[dict[str, Any]]:
    """The CRs to come, from the first with no PR up: cr, status, word, PR number or None."""
    come = []
    for c in rest:
        found = (PR_LINK.match(c.pr) or GITLAB_LINK.match(c.pr)) if c.pr else None
        pending = int(found.groups()[-1]) if found else None
        word = state_word(data, c, repo)
        come.append({"cr": c.id, "status": c.status, "word": word, "number": pending})
    return come


def forge_stack(args: argparse.Namespace) -> tuple[list[str], int]:
    if args.action != "show":  # the stack driver's writing forms hold its lease; `show` reads
        repo = Repo.find()
        leases.renewed_in_session(
            repo,
            resolve_batch(repo, args.batch),
            "stack",
            args.lease,
            what=f"forge-stack {args.action}",
            required=True,
            ended_ok=True,
        )
    if args.action == "create":
        return _create(args)
    if args.action == "rebuild":
        return _rebuild(args)
    if args.action == "unstack":
        return unstack_action(args)
    return _show(args)


def _make(rows: list[dict[str, Any]], host: str, owner: str, name: str) -> tuple[int, str]:
    fields: list[str] = []
    for r in rows:
        fields += ["-F", f"pull_requests[]={r['number']}"]
    made = gh(["-X", "POST", f"repos/{owner}/{name}/stacks", *fields], host)
    number = made.get("number") if isinstance(made, dict) else None
    if number is None:
        raise Unreadable(
            f"gh api: the forge answered no stack number: {json.dumps(made)[:200]}", EXIT_EXTERNAL
        )
    return number, (
        f"stack #{number} {rows[-1]['link']} (PRs bottom to top: "
        f"{' '.join('#' + str(r['number']) for r in rows)})"
    )


def _unstack_all(rows: Rows, where: Where, apart: Apart, done: list[str]) -> list[int]:
    """Unstack each open stack that holds a planned or a held PR; the numbers it unstacked."""
    planned = {r["number"] for r in rows}
    gone = []
    for s in stacks(*where):
        in_it = {p["number"] for p in s.get("pull_requests", [])}
        if s.get("open") and (planned | set(apart.held) | set(apart.moved)) & in_it:
            done.append(unstack(s, planned, where, apart))
            gone.append(s["number"])
    return gone


def _rebuild(args: argparse.Namespace) -> tuple[list[str], int]:
    """Unstack the open stacks that hold the batch's PRs, retarget the bases, stack again. When
    the forge refuses, its exact text comes back (exit 4), and when a stack stays open after its
    unstack tries."""
    rows, come, where, dropped, held_prs, moved = _plan(args)
    if _is_gitlab(rows):
        gitlab.refuse_stack(args)
        apart_rows = off_stack.held_rows(rows, held_prs) + off_stack.moved_rows(rows, moved)
        return gitlab.make(rows, come, where, apart_rows)
    host, owner, name = where
    done: list[str] = []
    gone: list[int] = []  # the stacks this run unstacked
    unstacked = False  # the unstack phase is over
    making = False  # the create call is the phase that raised
    try:
        apart = Apart(left(come), dropped, held_prs, moved)
        gone += _unstack_all(rows, where, apart, done)
        unstacked = True
        retarget(
            off_stack.held_rows(rows, held_prs) + off_stack.moved_rows(rows, moved), where, done
        )
        retarget(rows, where, done)
        making = True
        number, line = _make(rows, host, owner, name)
        done.append(line)
    except ChantierError as e:
        if e.code != EXIT_EXTERNAL:
            raise
        lines = [*done, str(e)]
        if unstacked and making and isinstance(e, Unreadable):
            lines.append(
                "the forge accepted the create call but its reply cannot be read, so the "
                "stack's state is unknown: run `forge-stack show`"
            )
        elif unstacked and gone:
            said = " ".join(f"#{n}" for n in gone)
            lines.append(
                f"stack {said} is dissolved and no stack replaces it yet: run `forge-stack create`"
                if len(gone) == 1
                else f"stacks {said} are dissolved and no stack replaces them yet: "
                "run `forge-stack create`"
            )
        raise ChantierError("\n".join(lines), e.code) from e
    args.stack = number
    lines, code = _show(args)
    drafts = "check 4: still a draft"
    acts = [x for x in lines if x.startswith(drafts)]
    rest = [x for x in lines if not x.startswith(drafts)]
    out = done + rest + [f"{x} (the stack driver turns the PRs ready)" for x in acts]
    return out, (code if rest else 0)


def _create(args: argparse.Namespace) -> tuple[list[str], int]:
    rows, come, where, _, held_prs, moved = _plan(args)
    if _is_gitlab(rows):
        gitlab.refuse_stack(args)
        apart_rows = off_stack.held_rows(rows, held_prs) + off_stack.moved_rows(rows, moved)
        return gitlab.make(rows, come, where, apart_rows)
    done: list[str] = []
    try:
        retarget(
            off_stack.held_rows(rows, held_prs) + off_stack.moved_rows(rows, moved), where, done
        )
        retarget(rows, where, done)
        return [*done, _make(rows, *where)[1]], 0
    except ChantierError as e:
        if e.code != EXIT_EXTERNAL:
            raise
        said = f"{e} (`forge-stack rebuild` replaces a stack)"
        raise ChantierError("\n".join([*done, said]), e.code) from e


def _check_two(
    stack: dict[str, Any], expected: list[int], have: list[int], apart: Apart
) -> list[str]:
    """Check 2: the stack holds the planned PRs and no other, each PR left out named by why."""
    left, dropped, held, moved = apart
    lines = []
    absent = [f"#{n}" for n in expected if n not in have]
    foreign = [
        f"#{n}"
        for n in have
        if n not in expected
        and n not in left
        and n not in dropped
        and n not in held
        and n not in moved
    ]
    out = [f"#{n} ({left[n]})" for n in have if n in left]
    gone = [f"#{n} ({dropped[n]})" for n in have if n in dropped]
    said = (
        f"missing {' '.join(absent)}" if absent else "",
        f"not in the batch's stack {' '.join(foreign)}" if foreign else "",
        f"not in the stack as it stands {' '.join(out)}" if out else "",
        f"dropped {' '.join(gone)}: close it" if gone else "",
    )
    if any(said):
        lines.append("check 2: " + "; ".join(x for x in said if x))
    lines += [
        f"check 2: #{n} of {held[n]} is held out of the stack and still in stack "
        f"#{stack.get('number')}: `forge-stack rebuild`"
        for n in have
        if n in held
    ]
    lines += [
        f"check 2: #{n} of {moved[n][0]}, moved to {moved[n][1]}, is left out of the stack and "
        f"still in stack #{stack.get('number')}: `forge-stack rebuild`"
        for n in have
        if n in moved
    ]
    return lines


def _checks(
    stack: dict[str, Any],
    rows: list[dict[str, Any]],
    apart: Apart,
) -> tuple[list[str], dict[str, Any] | None]:
    """One line per failed check of a stack read back; and the release row, if any."""
    prs = stack.get("pull_requests", [])
    have = [p["number"] for p in prs]
    expected = [r["number"] for r in rows]
    lines = []
    if not stack.get("open"):
        lines.append(f"check 1: stack #{stack.get('number')} is not open")
    lines += _check_two(stack, expected, have, apart)
    common = [n for n in expected if n in have]
    if [n for n in have if n in common] != common:
        lines.append(
            f"check 3: order on the forge {' '.join('#' + str(n) for n in have)}, "
            f"expected {' '.join('#' + str(n) for n in expected)} (bottom first)"
        )
    lines += draft_checks(prs, rows)
    release = next((r for r in rows if r["release"]), None)
    if release and (not have or have[-1] != release["number"]):
        lines.append(
            f"check 5: the release PR #{release['number']} is not on top "
            f"(top is {'#' + str(have[-1]) if have else 'empty'})"
        )
    return lines, release


def _read(args: argparse.Namespace, rows: list[dict[str, Any]], where: Where) -> dict[str, Any]:
    """The forge's stack: the one asked for, else the one that holds the batch's PRs."""
    host, owner, name = where
    if getattr(args, "stack", None):
        one: dict[str, Any] = gh(["-X", "GET", f"repos/{owner}/{name}/stacks/{args.stack}"], host)
        return one
    wanted = {r["number"] for r in rows}
    found = [
        s
        for s in stacks(host, owner, name)
        if {p["number"] for p in s.get("pull_requests", [])} & wanted
    ]
    if not found:
        raise ChantierError(
            "check 1: no stack on the forge holds the batch's PRs "
            f"{' '.join('#' + str(r['number']) for r in rows)}",
            EXIT_PRECONDITION,
        )
    return next((s for s in found if s.get("open")), found[0])


def _show(args: argparse.Namespace) -> tuple[list[str], int]:
    try:
        rows, come, where, dropped, held, moved = _plan(args)
    except NoBottom as e:
        return [f"check 1: {e}"], EXIT_PRECONDITION
    if _is_gitlab(rows):
        gitlab.refuse_stack(args)
        return gitlab.show(rows, come, where)
    try:
        stack = _read(args, rows, where)
    except ChantierError as e:
        if e.code != EXIT_PRECONDITION:
            raise
        return [str(e)], EXIT_PRECONDITION
    lines, release = _checks(stack, rows, Apart(left(come), dropped, held, moved))
    if lines:
        return lines, EXIT_PRECONDITION
    prs = stack.get("pull_requests", [])
    part, tail = ready_tail(rows, come, {p["number"] for p in prs if p.get("draft")}, release)
    return [
        f"stack #{stack.get('number')} ready to merge: open, {len(prs)} PRs in order, {part}",
        *tail,
    ], 0

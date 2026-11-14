"""`chantier forge-stack`: the native stack on the forge."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from typing import Any

from chantier.commands import forge_stack_gitlab as gitlab
from chantier.commands.crs import short_head
from chantier.commands.facts import chain, stack_base
from chantier.commands.forge_stack_gitlab import GITLAB_LINK
from chantier.commands.forge_stack_shared import Where, draft_checks, left, ready_tail
from chantier.commands.registry import BATCH, Subparsers, add_command
from chantier.core.batch import read_batch, resolve_batch
from chantier.core.errors import EXIT_EXTERNAL, EXIT_PRECONDITION, ChantierError
from chantier.lifecycle.convert import open_repo

PR_LINK = re.compile(r"^https?://([^/\s]+)/([^/\s]+)/([^/\s]+)/pull/(\d+)")


UNSTACK_TRIES = 5

NEITHER = "forge-stack reads GitHub pull requests and GitLab merge requests: {what} is neither"


def _gh(args: list[str], host: str) -> Any:
    exe = shutil.which("gh")
    if not exe:
        raise ChantierError(
            "gh: not found on PATH (the user's own `gh` login is needed)", EXIT_EXTERNAL
        )
    cmd = [exe, "api"] + (["--hostname", host] if host != "github.com" else []) + args
    p = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )
    if p.returncode != 0:
        raise ChantierError(
            f"gh api {' '.join(args)}: {p.stderr.strip() or p.stdout.strip()}", EXIT_EXTERNAL
        )
    try:
        return json.loads(p.stdout)
    except ValueError as e:
        raise ChantierError(
            f"gh api {' '.join(args)}: not JSON: {p.stdout.strip()[:200]}", EXIT_EXTERNAL
        ) from e


def _pr_parts(pr: str) -> tuple[str, ...]:
    """The host, owner, repository and number of a GitHub PR link; the host, project path, an
    empty name and the iid of a GitLab MR link; anything else is refused. The forge is read from
    the shape of the link, never from the host."""
    link = PR_LINK.match(pr)
    if link is not None:
        return link.groups()
    mr = GITLAB_LINK.match(pr)
    if mr is None:
        raise ChantierError(NEITHER.format(what=pr), EXIT_PRECONDITION)
    return mr.group(1), mr.group(2), "", mr.group(3)


def _is_gitlab(rows: list[dict[str, Any]]) -> bool:
    return GITLAB_LINK.match(rows[0]["link"]) is not None


class NoBottom(ChantierError):
    """The stack's first CR has no PR: nothing to stack."""


def _plan(
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Where]:
    """The stack as it stands: the rows (the bottom CRs with a PR, whatever their status: cr,
    status, PR number, link, base, head, release), the CRs to come (those from the first with no PR
    up: cr, status, PR number or None), and the forge's host, owner and repository, read from the
    PR links."""
    repo = open_repo()
    data = read_batch(repo, resolve_batch(repo, args.batch))
    if data.mode != "stack":
        raise ChantierError(f"batch {data.id} is not a stack", EXIT_PRECONDITION)
    links = chain(data)
    if not links:
        raise ChantierError(f"batch {data.id} has no open CR in its stack", EXIT_PRECONDITION)
    rows: list[dict[str, Any]] = []
    where = None
    for c in links:
        if not c.pr:
            break
        host, owner, name, number = _pr_parts(c.pr)
        if where not in (None, (host, owner, name)):
            raise ChantierError("the stack's PRs are not all in one repository", EXIT_PRECONDITION)
        where = (host, owner, name)
        rows.append(
            {
                "cr": c.id,
                "status": c.status,
                "number": int(number),
                "link": c.pr,
                "base": stack_base(data, c, repo, planned=True),
                "branch": c.branch,
                "head": short_head(c.head) or "-",
                "release": c.kind == "release",
                "default": repo.config["default_branch"],
            }
        )
    if where is None:
        raise NoBottom(
            f"no PR at the bottom of the stack: {links[0].id} is {links[0].status}, no PR",
            EXIT_PRECONDITION,
        )
    come = []
    for c in links[len(rows) :]:
        found = (PR_LINK.match(c.pr) or GITLAB_LINK.match(c.pr)) if c.pr else None
        pending = int(found.groups()[-1]) if found else None
        come.append({"cr": c.id, "status": c.status, "number": pending})
    return rows, come, where


def forge_stack(args: argparse.Namespace) -> tuple[list[str], int]:
    if args.action == "create":
        return _create(args)
    if args.action == "rebuild":
        return _rebuild(args)
    return _show(args)


def _make(rows: list[dict[str, Any]], host: str, owner: str, name: str) -> tuple[int, str]:
    fields: list[str] = []
    for r in rows:
        fields += ["-F", f"pull_requests[]={r['number']}"]
    made = _gh(["-X", "POST", f"repos/{owner}/{name}/stacks", *fields], host)
    number = made.get("number") if isinstance(made, dict) else None
    if number is None:
        raise ChantierError(
            f"gh api: the forge answered no stack number: {json.dumps(made)[:200]}", EXIT_EXTERNAL
        )
    return number, (
        f"stack #{number} {rows[-1]['link']} (PRs bottom to top: "
        f"{' '.join('#' + str(r['number']) for r in rows)})"
    )


def _stacks(host: str, owner: str, name: str) -> list[dict[str, Any]]:
    stacks: list[dict[str, Any]] = _gh(
        ["-X", "GET", f"repos/{owner}/{name}/stacks", "-F", "per_page=100"], host
    )
    return stacks


def _outside(outside: list[int], left: dict[int, str]) -> str:
    """The PRs an unstacked stack held that are not planned: those of the batch's stack left out
    of the rows, and foreign ones."""
    mine = [n for n in outside if n in left]
    foreign = [n for n in outside if n not in left]
    parts = []
    if mine:
        said = " ".join(f"#{n} of {left[n]}" for n in mine)
        parts.append(f"it also held {said}: a plain PR until it joins again")
    if foreign:
        parts.append(
            f"it also held {' '.join('#' + str(n) for n in foreign)}, not in the batch's "
            "stack: a plain PR now"
        )
    return f" ({'; '.join(parts)})" if parts else ""


def _unstack(s: dict[str, Any], planned: set[int], where: Where, left: dict[int, str]) -> str:
    """Unstack one open stack that holds a planned PR, until the forge reads it back as gone."""
    host, owner, name = where
    held = [p["number"] for p in s.get("pull_requests", [])]
    outside = [n for n in held if n not in planned]
    for _ in range(UNSTACK_TRIES):  # until the forge reads it back as gone or not open
        fields = [x for n in held for x in ("-F", f"pull_requests[]={n}")]
        _gh(["-X", "POST", f"repos/{owner}/{name}/stacks/{s['number']}/unstack", *fields], host)
        now = [
            t
            for t in _stacks(host, owner, name)
            if t.get("number") == s["number"] and t.get("open")
        ]
        if not now:
            break
        held = [p["number"] for p in now[0].get("pull_requests", [])]
    else:
        back = " ".join(f"#{n}" for n in held)
        raise ChantierError(
            f"stack #{s['number']} is still open after {UNSTACK_TRIES} unstack tries (the forge "
            f"reads it back {'with ' + back if back else 'open, with no PR'})",
            EXIT_EXTERNAL,
        )
    return f"unstacked #{s['number']}" + _outside(outside, left)


def _retarget(rows: list[dict[str, Any]], where: Where, done: list[str]) -> None:
    host, owner, name = where
    for r in rows:
        pull = _gh(["-X", "GET", f"repos/{owner}/{name}/pulls/{r['number']}"], host)
        old = (pull.get("base") or {}).get("ref") if isinstance(pull, dict) else None
        if old != r["base"]:
            patch = ["-X", "PATCH", f"repos/{owner}/{name}/pulls/{r['number']}"]
            _gh([*patch, "-f", f"base={r['base']}"], host)
            done.append(f"#{r['number']} base {old} -> {r['base']}")


def _rebuild(args: argparse.Namespace) -> tuple[list[str], int]:
    """Unstack the open stacks that hold the batch's PRs, retarget the bases, stack again. When
    the forge refuses, its exact text comes back (exit 4), and when a stack stays open after its
    unstack tries."""
    rows, come, where = _plan(args)
    if _is_gitlab(rows):
        gitlab.refuse_stack(args)
        return gitlab.make(rows, come, where)
    host, owner, name = where
    done: list[str] = []
    try:
        planned = {r["number"] for r in rows}
        for s in _stacks(host, owner, name):
            held = {p["number"] for p in s.get("pull_requests", [])}
            if s.get("open") and planned & held:
                done.append(_unstack(s, planned, where, left(come)))
        _retarget(rows, where, done)
        number, line = _make(rows, host, owner, name)
        done.append(line)
    except ChantierError as e:
        if e.code != EXIT_EXTERNAL:
            raise
        raise ChantierError("\n".join([*done, str(e)]), e.code) from e
    args.stack = number
    lines, code = _show(args)
    drafts = "check 4: still a draft"
    acts = [x for x in lines if x.startswith(drafts)]
    rest = [x for x in lines if not x.startswith(drafts)]
    out = done + rest + [f"{x} (the stack driver turns the PRs ready)" for x in acts]
    return out, (code if rest else 0)


def _create(args: argparse.Namespace) -> tuple[list[str], int]:
    rows, come, where = _plan(args)
    if _is_gitlab(rows):
        gitlab.refuse_stack(args)
        return gitlab.make(rows, come, where)
    try:
        return [_make(rows, *where)[1]], 0
    except ChantierError as e:
        if e.code != EXIT_EXTERNAL:
            raise
        raise ChantierError(f"{e} (`forge-stack rebuild` replaces a stack)", e.code) from e


def _checks(
    stack: dict[str, Any], rows: list[dict[str, Any]], left: dict[int, str]
) -> tuple[list[str], dict[str, Any] | None]:
    """One line per failed check of a stack read back; and the release row, if any."""
    prs = stack.get("pull_requests", [])
    have = [p["number"] for p in prs]
    expected = [r["number"] for r in rows]
    lines = []
    if not stack.get("open"):
        lines.append(f"check 1: stack #{stack.get('number')} is not open")
    absent = [f"#{n}" for n in expected if n not in have]
    foreign = [f"#{n}" for n in have if n not in expected and n not in left]
    out = [f"#{n} ({left[n]})" for n in have if n in left]
    said = (
        f"missing {' '.join(absent)}" if absent else "",
        f"not in the batch's stack {' '.join(foreign)}" if foreign else "",
        f"not in the stack as it stands {' '.join(out)}" if out else "",
    )
    if any(said):
        lines.append("check 2: " + "; ".join(x for x in said if x))
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
        one: dict[str, Any] = _gh(["-X", "GET", f"repos/{owner}/{name}/stacks/{args.stack}"], host)
        return one
    wanted = {r["number"] for r in rows}
    found = [
        s
        for s in _stacks(host, owner, name)
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
        rows, come, where = _plan(args)
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
    lines, release = _checks(stack, rows, left(come))
    if lines:
        return lines, EXIT_PRECONDITION
    prs = stack.get("pull_requests", [])
    part, tail = ready_tail(rows, come, {p["number"] for p in prs if p.get("draft")}, release)
    return [f"stack #{stack.get('number')} ready: open, {len(prs)} PRs in order, {part}", *tail], 0


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "forge-stack",
        forge_stack,
        "create: the stack batch's stack as it stands (the bottom CRs with a PR, drafts on top), "
        "on GitHub its native stack, on GitLab the chain of MRs each targeting the one below, "
        "bottom to top, the release last; "
        "show: read it back, one line per failed check (exit 2); rebuild: make the forge's "
        "stack match the record (GitHub unstacks, retargets and creates again, GitLab retargets)",
        BATCH,
    )
    s.add_argument("action", choices=["create", "show", "rebuild"])
    s.add_argument(
        "--stack",
        type=int,
        metavar="N",
        help="show: the stack's number (default: the one that holds the batch's PRs); GitHub only",
    )

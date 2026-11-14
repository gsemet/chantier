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
from chantier.commands.forge_stack_gitlab import GITLAB_LINK
from chantier.commands.forge_stack_shared import Where, draft_checks, left, ready_tail
from chantier.core.batch import read_batch, resolve_batch
from chantier.core.errors import EXIT_EXTERNAL, EXIT_PRECONDITION, ChantierError
from chantier.core.records import BatchRecord, CrEntry
from chantier.core.repo import Repo
from chantier.lifecycle.convert import open_repo
from chantier.stacks import chain, stack_base, state_word

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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Where, dict[int, str]]:
    """The stack as it stands: the rows (the bottom CRs with a PR, whatever their status: cr,
    status, PR number, link, base, head, release), the CRs to come (those from the first with no PR
    up: cr, status, PR number or None), the forge's host, owner and repository, read from the
    PR links, and the PR numbers of the batch's dropped CRs (to their CR ids)."""
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
        )
    if where is None:
        raise NoBottom(
            f"no PR at the bottom of the stack: {links[0].id} is {links[0].status}, no PR",
            EXIT_PRECONDITION,
        )
    return rows, _come(data, repo, links[len(rows) :]), where, _dropped(data)


def _come(data: BatchRecord, repo: Repo, rest: list[CrEntry]) -> list[dict[str, Any]]:
    """The CRs to come, from the first with no PR up: cr, status, word, PR number or None."""
    come = []
    for c in rest:
        found = (PR_LINK.match(c.pr) or GITLAB_LINK.match(c.pr)) if c.pr else None
        pending = int(found.groups()[-1]) if found else None
        word = state_word(data, c, repo)
        come.append({"cr": c.id, "status": c.status, "word": word, "number": pending})
    return come


def _dropped(data: BatchRecord) -> dict[int, str]:
    """The PR numbers (to their CR ids) of the batch's cancelled CRs that have a PR, a fix CR
    apart: a dropped CR's PR is named apart from a foreign one."""
    found = {}
    for c in data.crs:
        link = PR_LINK.match(c.pr) if c.pr else None
        if c.status == "cancelled" and c.kind != "fix" and link:
            found[int(link.group(4))] = c.id
    return found


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


def _outside(outside: list[int], left: dict[int, str], dropped: dict[int, str]) -> str:
    """The PRs an unstacked stack held that are not planned: those of the batch's stack left out
    of the rows, those of dropped CRs, and foreign ones."""
    mine = [n for n in outside if n in left]
    gone = [n for n in outside if n in dropped]
    foreign = [n for n in outside if n not in left and n not in dropped]
    parts = []
    if mine:
        said = " ".join(f"#{n} of {left[n]}" for n in mine)
        parts.append(f"it also held {said}: a plain PR until it joins again")
    if gone:
        said = " ".join(f"#{n} of {dropped[n]}" for n in gone)
        parts.append(f"it also held {said}, dropped: close it")
    if foreign:
        parts.append(
            f"it also held {' '.join('#' + str(n) for n in foreign)}, not in the batch's "
            "stack: a plain PR now"
        )
    return f" ({'; '.join(parts)})" if parts else ""


def _unstack(
    s: dict[str, Any],
    planned: set[int],
    where: Where,
    left: dict[int, str],
    dropped: dict[int, str],
) -> str:
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
    return f"unstacked #{s['number']}" + _outside(outside, left, dropped)


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
    rows, come, where, dropped = _plan(args)
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
                done.append(_unstack(s, planned, where, left(come), dropped))
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
    rows, come, where, _ = _plan(args)
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
    stack: dict[str, Any],
    rows: list[dict[str, Any]],
    left: dict[int, str],
    dropped: dict[int, str],
) -> tuple[list[str], dict[str, Any] | None]:
    """One line per failed check of a stack read back; and the release row, if any."""
    prs = stack.get("pull_requests", [])
    have = [p["number"] for p in prs]
    expected = [r["number"] for r in rows]
    lines = []
    if not stack.get("open"):
        lines.append(f"check 1: stack #{stack.get('number')} is not open")
    absent = [f"#{n}" for n in expected if n not in have]
    foreign = [f"#{n}" for n in have if n not in expected and n not in left and n not in dropped]
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
        rows, come, where, dropped = _plan(args)
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
    lines, release = _checks(stack, rows, left(come), dropped)
    if lines:
        return lines, EXIT_PRECONDITION
    prs = stack.get("pull_requests", [])
    part, tail = ready_tail(rows, come, {p["number"] for p in prs if p.get("draft")}, release)
    return [
        f"stack #{stack.get('number')} ready to merge: open, {len(prs)} PRs in order, {part}",
        *tail,
    ], 0

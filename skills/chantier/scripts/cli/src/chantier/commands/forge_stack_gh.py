"""`chantier forge-stack` on GitHub: the API calls, the unstack of a stack and the retarget of a
PR, and `unstack`, the action that leaves a stack (any mode)."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from typing import Any, NamedTuple

from chantier.commands import forge_stack_gitlab as gitlab
from chantier.commands.forge_stack_gitlab import GITLAB_LINK
from chantier.commands.forge_stack_shared import NOT_ONE_REPOSITORY, Where
from chantier.core.batch import read_batch, resolve_batch
from chantier.core.errors import EXIT_EXTERNAL, EXIT_PRECONDITION, ChantierError
from chantier.core.repo import Repo
from chantier.rails import ENDED
from chantier.stacks import stack_base

PR_LINK = re.compile(r"^https?://([^/\s]+)/([^/\s]+)/([^/\s]+)/pull/(\d+)")


UNSTACK_TRIES = 5

NEITHER = "forge-stack reads GitHub pull requests and GitLab merge requests: {what} is neither"


class Unreadable(ChantierError):
    """The forge accepted a call (`gh api` exit 0) but its reply cannot be read."""


def gh(args: list[str], host: str, *, empty_ok: bool = False) -> Any:
    """One `gh api` call, its reply read as JSON. With `empty_ok`, an empty reply of an accepted
    call (a 2xx) is `None`, not an error."""
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
    if empty_ok and not p.stdout.strip():
        return None
    try:
        return json.loads(p.stdout)
    except ValueError as e:
        raise Unreadable(
            f"gh api {' '.join(args)}: not JSON: {p.stdout.strip()[:200]}", EXIT_EXTERNAL
        ) from e


def pr_parts(pr: str) -> tuple[str, ...]:
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


def stacks(host: str, owner: str, name: str) -> list[dict[str, Any]]:
    stacks: list[dict[str, Any]] = gh(
        ["-X", "GET", f"repos/{owner}/{name}/stacks", "-F", "per_page=100"], host
    )
    return stacks


class Apart(NamedTuple):
    """The PRs of a stack that are not planned, to their CR ids: the batch's stack left out of
    the rows (`left`), dropped CRs, held CRs."""

    left: dict[int, str]
    dropped: dict[int, str]
    held: dict[int, tuple[str, str]]  # to (CR id, `held` or `parked`)
    moved: dict[int, tuple[str, str]]  # to (CR id, the folder it moved to)
    waiting: dict[int, tuple[str, str]]  # to (CR id, `parked <p>` / `held <p> (order …)`)


def held_outside(outside: list[int], apart: Apart) -> str:
    """The PRs an unstacked stack held that are not planned: those of the batch's stack left out
    of the rows, those of dropped CRs, those of held CRs, those of CRs moved to the backlog or the
    next batch (`3-ready`), and foreign ones."""
    left, dropped, held, moved, waiting = apart
    mine = [n for n in outside if n in left]
    gone = [n for n in outside if n in dropped]
    kept = [n for n in outside if n in held]
    away = [n for n in outside if n in moved]
    known = {*left, *dropped, *held, *moved, *waiting}
    foreign = [n for n in outside if n not in known]
    parts = []
    for n in away:
        parts.append(
            f"it also held #{n} of {moved[n][0]}, moved to {moved[n][1]}: left out, on main"
        )
    for kind in ("held", "parked"):
        said = " ".join(f"#{n} of {held[n][0]}" for n in kept if held[n][1] == kind)
        if said:
            parts.append(f"it also held {said}, {kind} out of the stack: left out")
    for n in [n for n in outside if n in waiting]:
        parts.append(f"it also held #{n} of {waiting[n][0]}, waits with {waiting[n][1]}: left out")
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


def unstack(
    s: dict[str, Any],
    planned: set[int],
    where: Where,
    apart: Apart,
) -> str:
    """Unstack one open stack that holds a planned PR, until the forge reads it back as gone."""
    host, owner, name = where
    held = [p["number"] for p in s.get("pull_requests", [])]
    outside = [n for n in held if n not in planned]
    for _ in range(UNSTACK_TRIES):  # until the forge reads it back as gone or not open
        fields = [x for n in held for x in ("-F", f"pull_requests[]={n}")]
        post = ["-X", "POST", f"repos/{owner}/{name}/stacks/{s['number']}/unstack", *fields]
        gh(post, host, empty_ok=True)
        now = [
            t for t in stacks(host, owner, name) if t.get("number") == s["number"] and t.get("open")
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
    return f"unstacked #{s['number']}" + held_outside(outside, apart)


def retarget(rows: list[dict[str, Any]], where: Where, done: list[str], why: str = "") -> None:
    host, owner, name = where
    for r in rows:
        pull = gh(["-X", "GET", f"repos/{owner}/{name}/pulls/{r['number']}"], host)
        old = (pull.get("base") or {}).get("ref") if isinstance(pull, dict) else None
        if old != r["base"]:
            patch = ["-X", "PATCH", f"repos/{owner}/{name}/pulls/{r['number']}"]
            gh([*patch, "-f", f"base={r['base']}"], host)
            done.append(f"#{r['number']} base {old} -> {r['base']}{r.get('why', why)}")


def unstack_rows(args: argparse.Namespace) -> tuple[list[dict[str, Any]], Where | None, str, str]:
    """The open CRs with a PR, in any mode: number, link and the base the record gives now."""
    repo = Repo.find()
    data = read_batch(repo, resolve_batch(repo, args.batch))
    rows: list[dict[str, Any]] = []
    where = None
    for c in sorted(data.crs, key=lambda x: (x.kind == "release", x.order)):
        if c.status in ENDED or not c.pr:
            continue
        host, owner, name, number = pr_parts(c.pr)
        if where not in (None, (host, owner, name)):
            raise ChantierError(NOT_ONE_REPOSITORY, EXIT_PRECONDITION)
        where = (host, owner, name)
        rows.append(
            {
                "cr": c.id,
                "number": int(number),
                "link": c.pr,
                "base": stack_base(data, c, repo),
            }
        )
    return rows, where, data.id, repo.config["default_branch"]


def unstack_action(args: argparse.Namespace) -> tuple[list[str], int]:
    """Leaving a stack: dissolve the forge's open stacks that hold the batch's open PRs, then
    retarget each open PR to the base the record gives in the batch's mode; no new stack."""
    rows, where, batch, _ = unstack_rows(args)
    if not rows or where is None:
        return [f"no open PR in {batch}"], 0
    if GITLAB_LINK.match(rows[0]["link"]):
        return gitlab.retarget(rows, where), 0
    host, owner, name = where
    done: list[str] = []
    try:
        planned = {r["number"] for r in rows}
        for s in stacks(host, owner, name):
            held = {p["number"] for p in s.get("pull_requests", [])}
            if s.get("open") and planned & held:
                done.append(unstack(s, planned, where, Apart({}, {}, {}, {}, {})))
        if not done:
            done.append("no stack holds the batch's PRs")
        retarget(rows, where, done)
    except ChantierError as e:
        if e.code != EXIT_EXTERNAL:
            raise
        raise ChantierError("\n".join([*done, str(e)]), e.code) from e
    return done, 0

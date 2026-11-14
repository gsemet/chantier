"""`chantier forge-stack` on GitLab: a stack is the chain of merge requests, each targeting the one
below, the first on the default branch. Written from GitLab's public API documentation and tried
only against the scenario's fake `glab` (unproved on a real GitLab)."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from typing import Any
from urllib.parse import quote

from chantier.commands.forge_stack_shared import Where, draft_checks, left, ready_tail
from chantier.core.errors import EXIT_EXTERNAL, EXIT_PRECONDITION, ChantierError
from chantier.lifecycle.convert import open_repo

GITLAB_LINK = re.compile(r"^https?://([^/\s]+)/(.+?)/-/merge_requests/(\d+)")
STACK_FLAG = "--stack is GitHub only: a GitLab stack is the chain of its MRs"
Rows = list[dict[str, Any]]


def glab(path: str, host: str, method: str = "GET", fields: dict[str, str] | None = None) -> Any:
    """One `glab api` call, answered as JSON; a refusal comes back with the forge's exact text."""
    exe = shutil.which("glab")
    if not exe:
        raise ChantierError(
            "glab: not found on PATH (the user's own glab login is needed)", EXIT_EXTERNAL
        )
    cmd = [exe, "api", path]
    if method != "GET" or fields:  # glab sends a POST when fields come with no method
        cmd += ["--method", method]
    for k, v in (fields or {}).items():
        cmd += ["-f", f"{k}={v}"]
    if host != "gitlab.com":
        cmd += ["--hostname", host]
    p = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )
    shown = f"glab api {path}"
    if p.returncode != 0:
        raise ChantierError(f"{shown}: {p.stderr.strip() or p.stdout.strip()}", EXIT_EXTERNAL)
    try:
        return json.loads(p.stdout)
    except ValueError as e:
        raise ChantierError(f"{shown}: not JSON: {p.stdout.strip()[:200]}", EXIT_EXTERNAL) from e


PAGE = 100


def _base(where: Where) -> str:
    return f"projects/{quote(where[1], safe='')}/merge_requests"


def _read(where: Where, rows: Rows) -> list[dict[str, Any]]:
    """Each MR of the rows, bottom first (one read each)."""
    return [glab(f"{_base(where)}/{r['number']}", where[0]) for r in rows]


def _on(where: Where, branch: str) -> list[dict[str, Any]]:
    """The open MRs that target a branch, every page (a short page is the last)."""
    found: list[dict[str, Any]] = []
    page = 1
    while True:
        query = {
            "state": "opened",
            "per_page": str(PAGE),
            "page": str(page),
            "target_branch": branch,
        }
        got: list[dict[str, Any]] = glab(_base(where), where[0], "GET", query)
        found += got
        if len(got) < PAGE:
            return found
        page += 1


def _check_1(rows: Rows, mrs: list[dict[str, Any]], default: str) -> list[str]:
    lines = []
    for m in mrs:
        if m.get("state") == "opened":
            continue
        target = m.get("target_branch")
        if m.get("state") == "merged" and target != default:
            below = next((r["cr"] for r in rows if r["branch"] == target), target)
            lines.append(
                f"check 1: !{m['iid']} merged into {target}, not {default}: folded into {below}"
            )
        else:
            lines.append(f"check 1: !{m['iid']} is {m.get('state')}")
    return lines


def _check_2(
    mrs: list[dict[str, Any]], lefts: dict[int, str], seen: dict[str, list[dict[str, Any]]]
) -> list[str]:
    """No open MR outside the rows on a branch of the stack (the release's branch is check 5's)."""
    mine = {m["iid"] for m in mrs}
    others = [(b, x) for b, found in seen.items() for x in found if x["iid"] not in mine]
    lines = []
    for branch, x in others:
        if x["iid"] not in lefts:
            lines.append(f"check 2: not in the batch's stack !{x['iid']} (on {branch})")
        elif not x.get("draft"):
            lines.append(f"check 2: not in the stack as it stands !{x['iid']} ({lefts[x['iid']]})")
    return lines


def _check_3(rows: Rows, mrs: list[dict[str, Any]]) -> list[str]:
    return [
        f"check 3: !{m['iid']} targets {m.get('target_branch')}, expected {r['base']} "
        "(bottom first)"
        for r, m in zip(rows, mrs, strict=True)
        if m.get("state") == "opened" and m.get("target_branch") != r["base"]
    ]


def _check_5(release: Any, found: list[dict[str, Any]]) -> list[str]:
    return [
        f"check 5: the release MR !{release['number']} is not on top (!{x['iid']} targets it)"
        for x in found
    ]


def _lines(
    rows: Rows, come: Rows, where: Where, default: str, mrs: list[dict[str, Any]]
) -> tuple[list[str], Any]:
    """One line per failed check of the chain read back; and the release row, if any."""
    release = next((r for r in rows if r["release"]), None)
    rel_branch = next(
        (m["source_branch"] for r, m in zip(rows, mrs, strict=True) if r is release), ""
    )
    seen = {b: _on(where, b) for b in dict.fromkeys(m["source_branch"] for m in mrs)}
    lines = _check_1(rows, mrs, default)
    lines += _check_2(mrs, left(come), {b: v for b, v in seen.items() if b != rel_branch})
    lines += _check_3(rows, mrs)
    opened = [(r, m) for r, m in zip(rows, mrs, strict=True) if m.get("state") == "opened"]
    prs = [{"number": m["iid"], "draft": bool(m.get("draft"))} for _, m in opened]
    lines += draft_checks(prs, [r for r, _ in opened], "!", "MR")
    if release:
        lines += _check_5(release, seen.get(rel_branch, []))
    return lines, release


def refuse_stack(args: argparse.Namespace) -> None:
    if getattr(args, "stack", None):
        raise ChantierError(STACK_FLAG, EXIT_PRECONDITION)


def show(
    rows: Rows, come: Rows, where: Where, mrs: list[dict[str, Any]] | None = None
) -> tuple[list[str], int]:
    """The five checks read on the chain; the success line when they all hold."""
    default = open_repo().config["default_branch"]
    mrs = mrs if mrs is not None else _read(where, rows)
    lines, release = _lines(rows, come, where, default, mrs)
    if lines:
        return lines, EXIT_PRECONDITION
    drafts = {m["iid"] for m in mrs if m.get("draft")}
    part, tail = ready_tail(rows, come, drafts, release, "!")
    top = rows[-1]["link"]
    return [f"chain {top} ready: open, {len(rows)} MRs in order, {part}", *tail], 0


def make(rows: Rows, come: Rows, where: Where) -> tuple[list[str], int]:
    """`create` and `rebuild`: retarget, bottom first, each MR off the record's base, then read
    the chain back. A `still a draft` line is the stack driver's to act on, no failure."""
    mrs = _read(where, rows)
    done: list[str] = []
    try:
        for r, m in zip(rows, mrs, strict=True):
            old = m.get("target_branch")
            if m.get("state") == "opened" and old != r["base"]:
                glab(f"{_base(where)}/{r['number']}", where[0], "PUT", {"target_branch": r["base"]})
                m["target_branch"] = r["base"]
                done.append(f"!{r['number']} target {old} -> {r['base']}")
    except ChantierError as e:
        if e.code != EXIT_EXTERNAL:
            raise
        raise ChantierError("\n".join([*done, str(e)]), e.code) from e
    order = " ".join(f"!{r['number']}" for r in rows)
    first = f"chain {rows[-1]['link']} (MRs bottom to top: {order})"
    lines, code = show(rows, come, where, mrs)
    drafts = "check 4: still a draft"
    acts = [x for x in lines if x.startswith(drafts)]
    rest = [x for x in lines if not x.startswith(drafts)]
    out = [first, *done, *rest, *[f"{x} (the stack driver turns the MRs ready)" for x in acts]]
    return out, (code if rest else 0)

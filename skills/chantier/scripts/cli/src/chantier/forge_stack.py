"""`chantier forge-stack create|show`: the batch's native stack on GitHub, made and read back with
the user's own `gh` login. It knows no role; a card says who runs it and when. GitHub only.

`create` makes the stack from the record (each open CR's recorded PR, in `take stack` order, the
release PR last). `show` reads the stack on the forge and prints one line per failed check; it
writes nothing. The API (`POST /repos/{o}/{r}/stacks`, `GET /repos/{o}/{r}/stacks[/{n}]`) offers
no way to add a PR to a stack or to dissolve one: when the forge refuses a second stack over PRs
already stacked, its exact text comes back (exit 4)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess

from .commands import _chain
from .state import (EXIT_EXTERNAL, EXIT_PRECONDITION, ChantierError, Repo, read_batch, resolve_batch)

PR_LINK = re.compile(r"^https?://([^/\s]+)/([^/\s]+)/([^/\s]+)/pull/(\d+)")
GITHUB_ONLY = "forge-stack is GitHub only: {what} is not a GitHub pull request link"


def _gh(args: list[str], host: str) -> object:
    exe = shutil.which("gh")
    if not exe:
        raise ChantierError("gh: not found on PATH (the user's own `gh` login is needed)", EXIT_EXTERNAL)
    cmd = [exe, "api"] + (["--hostname", host] if host != "github.com" else []) + args
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise ChantierError(f"gh api {' '.join(args)}: {p.stderr.strip() or p.stdout.strip()}",
                            EXIT_EXTERNAL)
    try:
        return json.loads(p.stdout)
    except ValueError as e:
        raise ChantierError(f"gh api {' '.join(args)}: not JSON: {p.stdout.strip()[:200]}",
                            EXIT_EXTERNAL) from e


def _plan(args) -> tuple[list[dict], str, str, str]:
    """The open stack of the record, bottom first: {cr, pr number, link, release}; and the forge's
    host, owner and repository, read from the PR links."""
    repo = Repo.find()
    data = read_batch(repo, resolve_batch(repo, args.batch))
    if data["mode"] != "stack":
        raise ChantierError(f"batch {data['id']} is not a stack", EXIT_PRECONDITION)
    chain = _chain(data)
    if not chain:
        raise ChantierError(f"batch {data['id']} has no open CR in its stack", EXIT_PRECONDITION)
    for c in chain:
        if c.get("pr") and not PR_LINK.match(c["pr"]):
            raise ChantierError(GITHUB_ONLY.format(what=c["pr"]), EXIT_PRECONDITION)
    missing = [c["id"] for c in chain if not c.get("pr")]
    if missing and args.action == "create":
        raise ChantierError(f"{', '.join(missing)} {'has' if len(missing) == 1 else 'have'} no PR "
                            "recorded (`ship`): the stack is made once every PR is recorded",
                            EXIT_PRECONDITION)
    rows, where = [], None
    for c in chain:
        if not c.get("pr"):
            rows.append({"cr": c["id"], "number": None, "link": None,
                         "release": c.get("kind") == "release"})
            continue
        host, owner, name, number = PR_LINK.match(c["pr"]).groups()
        if where not in (None, (host, owner, name)):
            raise ChantierError("the stack's PRs are not all in one repository", EXIT_PRECONDITION)
        where = (host, owner, name)
        rows.append({"cr": c["id"], "number": int(number), "link": c["pr"],
                     "release": c.get("kind") == "release"})
    if where is None:
        raise ChantierError("no PR recorded in the stack", EXIT_PRECONDITION)
    host, owner, name = where
    return rows, host, owner, name


def forge_stack(args) -> tuple[list[str], int]:
    if args.action == "create":
        return _create(args)
    return _show(args)


def _create(args) -> tuple[list[str], int]:
    rows, host, owner, name = _plan(args)
    fields: list[str] = []
    for r in rows:
        fields += ["-F", f"pull_requests[]={r['number']}"]
    made = _gh(["-X", "POST", f"repos/{owner}/{name}/stacks"] + fields, host)
    number = made.get("number") if isinstance(made, dict) else None
    if number is None:
        raise ChantierError(f"gh api: the forge answered no stack number: {json.dumps(made)[:200]}",
                            EXIT_EXTERNAL)
    top = rows[-1]["link"]
    return [f"stack #{number} {top} (PRs bottom to top: "
            f"{' '.join('#' + str(r['number']) for r in rows)})"], 0


def _show(args) -> tuple[list[str], int]:
    rows, host, owner, name = _plan(args)
    want = [r for r in rows if r["number"] is not None]
    if getattr(args, "stack", None):
        stack = _gh(["-X", "GET", f"repos/{owner}/{name}/stacks/{args.stack}"], host)
    else:
        found = [s for s in _gh(["-X", "GET", f"repos/{owner}/{name}/stacks", "-F", "per_page=100"], host)
                 if {p["number"] for p in s.get("pull_requests", [])} & {r["number"] for r in want}]
        if not found:
            return [f"check 1: no stack on the forge holds the batch's PRs "
                    f"{' '.join('#' + str(r['number']) for r in want)}"], EXIT_PRECONDITION
        stack = next((s for s in found if s.get("open")), found[0])
    prs = stack.get("pull_requests", [])
    have = [p["number"] for p in prs]
    expected = [r["number"] for r in want]
    lines = []
    if not stack.get("open"):
        lines.append(f"check 1: stack #{stack.get('number')} is not open")
    absent = [f"#{n}" for n in expected if n not in have]
    extra = [f"#{n}" for n in have if n not in expected]
    for r in rows:
        if r["number"] is None:
            absent.append(f"{r['cr']} (no PR recorded)")
    if absent or extra:
        lines.append("check 2: " + "; ".join(x for x in (
            f"missing {' '.join(absent)}" if absent else "",
            f"not in the batch's stack {' '.join(extra)}" if extra else "") if x))
    common = [n for n in expected if n in have]
    if [n for n in have if n in common] != common:
        lines.append(f"check 3: order on the forge {' '.join('#' + str(n) for n in have)}, "
                     f"expected {' '.join('#' + str(n) for n in expected)} (bottom first)")
    drafts = [f"#{p['number']}" for p in prs if p.get("draft")]
    if drafts:
        lines.append(f"check 4: still a draft {' '.join(drafts)}")
    release = next((r for r in want if r["release"]), None)
    if release and (not have or have[-1] != release["number"]):
        lines.append(f"check 5: the release PR #{release['number']} is not on top "
                     f"(top is {'#' + str(have[-1]) if have else 'empty'})")
    if lines:
        return lines, EXIT_PRECONDITION
    return [f"stack #{stack.get('number')} ready: open, {len(have)} PRs in order, none a draft"
            + (", the release on top" if release else "")], 0

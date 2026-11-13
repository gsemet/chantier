"""`chantier forge-stack`: the native stack on the forge."""

from __future__ import annotations

import json
import re
import shutil
import subprocess

from chantier.commands.facts import chain, stack_base
from chantier.commands.registry import BATCH, Subparsers, add_command
from chantier.core.batch import read_batch, resolve_batch
from chantier.core.errors import EXIT_EXTERNAL, EXIT_PRECONDITION, ChantierError
from chantier.lifecycle.convert import open_repo

PR_LINK = re.compile(r"^https?://([^/\s]+)/([^/\s]+)/([^/\s]+)/pull/(\d+)")


GITHUB_ONLY = "forge-stack is GitHub only: {what} is not a GitHub pull request link"


def _gh(args: list[str], host: str) -> object:
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


def _plan(args) -> tuple[list[dict], str, str, str]:
    """The open stack of the record, bottom first: {cr, pr number, link, release}; and the forge's
    host, owner and repository, read from the PR links."""
    repo = open_repo()
    data = read_batch(repo, resolve_batch(repo, args.batch))
    if data["mode"] != "stack":
        raise ChantierError(f"batch {data['id']} is not a stack", EXIT_PRECONDITION)
    links = chain(data)
    if not links:
        raise ChantierError(f"batch {data['id']} has no open CR in its stack", EXIT_PRECONDITION)
    for c in links:
        if c.get("pr") and not PR_LINK.match(c["pr"]):
            raise ChantierError(GITHUB_ONLY.format(what=c["pr"]), EXIT_PRECONDITION)
    missing = [c["id"] for c in links if not c.get("pr")]
    if missing and args.action in {"create", "rebuild"}:
        raise ChantierError(
            f"{', '.join(missing)} {'has' if len(missing) == 1 else 'have'} no PR "
            "recorded (`ship`): the stack is made once every PR is recorded",
            EXIT_PRECONDITION,
        )
    rows, where = [], None
    for c in links:
        if not c.get("pr"):
            rows.append(
                {
                    "cr": c["id"],
                    "number": None,
                    "link": None,
                    "base": None,
                    "release": c.get("kind") == "release",
                }
            )
            continue
        host, owner, name, number = PR_LINK.match(c["pr"]).groups()
        if where not in (None, (host, owner, name)):
            raise ChantierError("the stack's PRs are not all in one repository", EXIT_PRECONDITION)
        where = (host, owner, name)
        rows.append(
            {
                "cr": c["id"],
                "number": int(number),
                "link": c["pr"],
                "base": stack_base(data, c, repo, planned=True),
                "release": c.get("kind") == "release",
            }
        )
    if where is None:
        raise ChantierError("no PR recorded in the stack", EXIT_PRECONDITION)
    host, owner, name = where
    return rows, host, owner, name


def forge_stack(args) -> tuple[list[str], int]:
    if args.action == "create":
        try:
            return _create(args)
        except ChantierError as e:
            if e.code != EXIT_EXTERNAL:
                raise
            raise ChantierError(f"{e} (`forge-stack rebuild` replaces a stack)", e.code) from e
    if args.action == "rebuild":
        return _rebuild(args)
    return _show(args)


def _make(rows: list[dict], host: str, owner: str, name: str) -> tuple[int, str]:
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


def _rebuild(args) -> tuple[list[str], int]:
    rows, host, owner, name = _plan(args)
    done: list[str] = []
    try:
        planned = {r["number"] for r in rows}
        listing = _gh(["-X", "GET", f"repos/{owner}/{name}/stacks", "-F", "per_page=100"], host)
        for s in listing:
            held = [p["number"] for p in s.get("pull_requests", [])]
            if not s.get("open") or not planned & set(held):
                continue
            outside = [n for n in held if n not in planned]
            for _ in range(5):  # until the forge reads it back as gone or not open
                fields = [x for n in held for x in ("-F", f"pull_requests[]={n}")]
                _gh(
                    ["-X", "POST", f"repos/{owner}/{name}/stacks/{s['number']}/unstack", *fields],
                    host,
                )
                now = [
                    t
                    for t in _gh(
                        ["-X", "GET", f"repos/{owner}/{name}/stacks", "-F", "per_page=100"], host
                    )
                    if t.get("number") == s["number"] and t.get("open")
                ]
                if not now:
                    break
                held = [p["number"] for p in now[0].get("pull_requests", [])]
            else:
                raise ChantierError(f"stack #{s['number']} is still open after unstack")
            done.append(
                f"unstacked #{s['number']}"
                + (
                    f" (it also held {' '.join('#' + str(n) for n in outside)}, not in the batch's "
                    "stack: a plain PR now)"
                    if outside
                    else ""
                )
            )
        for r in rows:
            pull = _gh(["-X", "GET", f"repos/{owner}/{name}/pulls/{r['number']}"], host)
            old = (pull.get("base") or {}).get("ref") if isinstance(pull, dict) else None
            if old != r["base"]:
                _gh(
                    [
                        "-X",
                        "PATCH",
                        f"repos/{owner}/{name}/pulls/{r['number']}",
                        "-f",
                        f"base={r['base']}",
                    ],
                    host,
                )
                done.append(f"#{r['number']} base {old} -> {r['base']}")
        number, line = _make(rows, host, owner, name)
        done.append(line)
    except ChantierError as e:
        if e.code != EXIT_EXTERNAL:
            raise
        raise ChantierError("\n".join([*done, str(e)]), e.code) from e
    args.stack = number
    lines, code = _show(args)
    acts = [x for x in lines if x.startswith("check 4:")]
    rest = [x for x in lines if not x.startswith("check 4:")]
    out = done + rest + [f"{x} (the stack driver turns the PRs ready)" for x in acts]
    return out, (code if rest else 0)


def _create(args) -> tuple[list[str], int]:
    rows, host, owner, name = _plan(args)
    return [_make(rows, host, owner, name)[1]], 0


def _show(args) -> tuple[list[str], int]:
    rows, host, owner, name = _plan(args)
    want = [r for r in rows if r["number"] is not None]
    if getattr(args, "stack", None):
        stack = _gh(["-X", "GET", f"repos/{owner}/{name}/stacks/{args.stack}"], host)
    else:
        found = [
            s
            for s in _gh(["-X", "GET", f"repos/{owner}/{name}/stacks", "-F", "per_page=100"], host)
            if {p["number"] for p in s.get("pull_requests", [])} & {r["number"] for r in want}
        ]
        if not found:
            return [
                f"check 1: no stack on the forge holds the batch's PRs "
                f"{' '.join('#' + str(r['number']) for r in want)}"
            ], EXIT_PRECONDITION
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
        lines.append(
            "check 2: "
            + "; ".join(
                x
                for x in (
                    f"missing {' '.join(absent)}" if absent else "",
                    f"not in the batch's stack {' '.join(extra)}" if extra else "",
                )
                if x
            )
        )
    common = [n for n in expected if n in have]
    if [n for n in have if n in common] != common:
        lines.append(
            f"check 3: order on the forge {' '.join('#' + str(n) for n in have)}, "
            f"expected {' '.join('#' + str(n) for n in expected)} (bottom first)"
        )
    drafts = [f"#{p['number']}" for p in prs if p.get("draft")]
    if drafts:
        lines.append(f"check 4: still a draft {' '.join(drafts)}")
    release = next((r for r in want if r["release"]), None)
    if release and (not have or have[-1] != release["number"]):
        lines.append(
            f"check 5: the release PR #{release['number']} is not on top "
            f"(top is {'#' + str(have[-1]) if have else 'empty'})"
        )
    if lines:
        return lines, EXIT_PRECONDITION
    return [
        f"stack #{stack.get('number')} ready: open, {len(have)} PRs in order, none a draft"
        + (", the release on top" if release else "")
    ], 0


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "forge-stack",
        forge_stack,
        "create: the stack batch's native stack on GitHub, PRs bottom to top, the release last; "
        "show: read it back, one line per failed check (exit 2); rebuild: make the forge's "
        "stack match the record (unstack, retarget, create again); GitHub only",
        BATCH,
    )
    s.add_argument("action", choices=["create", "show", "rebuild"])
    s.add_argument(
        "--stack",
        type=int,
        metavar="N",
        help="show: the stack's number (default: the one that holds the batch's PRs)",
    )

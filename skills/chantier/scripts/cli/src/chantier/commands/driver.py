"""The Driver's commands: `take`, `round`, `handback`, `note` and `log`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from chantier.commands.cost.sessions import foreman_uuid
from chantier.commands.crs import (
    batch_cr,
    cr_events,
    work,
)
from chantier.commands.driver_checks import (
    check_release_branch,
    handback_args,
    handback_blocked,
    handback_refusals,
    live_cr,
)
from chantier.commands.facts import cr_facts, stack_lines
from chantier.commands.registry import BATCH, BATCH_EPOCH, Subparsers, add_command
from chantier.core.batch import Batch, check_epoch, find_cr_batch, resolve_batch
from chantier.core.clock import stamp
from chantier.core.errors import EXIT_USAGE, ChantierError
from chantier.core.records import LIVE
from chantier.core.repo import Repo
from chantier.costs.sessions import agent_context
from chantier.lifecycle.convert import open_repo
from chantier.lifecycle.session import RenderedBatch
from chantier.lifecycle.stages import changes_lock, done_cr, start_cr
from chantier.rails import (
    all_merged,
    check_budget,
    check_round,
    check_stray_round,
    check_take,
    held,
    worktree_print,
)


def _reopen(b: Batch) -> list[str]:
    """A take on a paused batch sets it running again: its pause and cost to date are void."""
    if b.data["status"] != "paused":
        return []
    b.data["status"] = "running"
    b.data.pop("paused", None)
    b.data.pop("summary", None)
    b.log("reopen", None)
    return [f"{b.id} was paused: running again; `pause` runs again at the end"]


def take(args) -> list[str]:
    """The Foreman gives a CR to a Driver (or the stack to its driver): the rails refuse what the
    batch does not allow (a slot, the budget, a CR that has nothing to do), the state records
    it, and the CR's facts are printed for the prompt. The Foreman chooses the agent."""
    repo = open_repo()
    if args.cr == "stack":
        batch = resolve_batch(repo, args.batch)
    else:
        batch = find_cr_batch(repo, args.cr, args.batch)
    with changes_lock(repo), RenderedBatch(repo, batch, actor="foreman") as b:
        check_epoch(b, args.epoch)
        d = b.data
        if args.cr == "stack":
            if d["mode"] != "stack":
                raise ChantierError(f"batch {batch} is not a stack")
            if d.get("stack_agent"):
                raise ChantierError(
                    f"a stack driver is recorded ({d['stack_agent']}); one "
                    "that ended: `agents set stack -` first (a stack driver "
                    "reads the stack with `stack`, which changes nothing)"
                )
            check_budget(b)
            reopened = _reopen(b)
            b.log("take", None, note=args.note)
            head, *rows = stack_lines(repo, batch, d)
            return [head, *reopened, *rows]
        c = b.cr(args.cr)
        check_take(b, c, args.note)
        if c["status"] != "working":
            check_release_branch(repo, d, c)
        reopened = _reopen(b)
        restart = c["status"] == "working"  # a new Driver on a CR already working
        if c["status"] in {"ready", "blocked", "working"}:
            c.setdefault("notes", []).append(f"back to a Driver: {args.note}")
        b.touch(c, status="working", blocked_reason=None)
        b.log("take", c["id"], note=args.note, **({"restart": True} if restart else {}))
        start_cr(b, c)  # `1-pending` to `2-actives`, before the Driver gets its facts
        if repo.external:
            c.setdefault("archive_stamp", stamp())  # the archive's name, kept from the first take
        work(repo, c).mkdir(parents=True, exist_ok=True)
        facts = cr_facts(repo, batch, d, c)
    return [f"took {c['id']} ({len(held(b))} of {d['slots']} slots held)", *reopened, *facts]


def round_(args) -> list[str]:
    """A Driver counts a round before it starts the round's Coder; once the budget is spent, or
    past the batch's limit or the one the user granted the CR, it is refused (exit 5), the
    budget first (its own message), the round count unchanged and nothing logged. A round on
    which nothing happened since the last one is refused too (exit 2). Prints the Driver's
    context size. The round event keeps the worktree's head and a fingerprint of its content."""
    repo = open_repo()
    batch = find_cr_batch(repo, args.cr, args.batch)
    with changes_lock(repo), RenderedBatch(repo, batch, actor="driver") as b:
        c = b.cr(args.cr)
        if c["status"] not in LIVE:
            raise ChantierError(f"{args.cr} is {c['status']}: no Driver to run a round")
        limit = check_round(b, c)  # the budget first, then the limit
        wt = Path(c["worktree"]) if c.get("worktree") else None
        seen = worktree_print(wt)
        check_stray_round(cr_events(repo, batch, c["id"]), c, seen)  # then a stray round
        b.touch(c, round=c.get("round", 0) + 1)
        b.log("round", c["id"], round=c["round"], note=args.note, **seen)
        work(repo, c).mkdir(parents=True, exist_ok=True)
        facts = cr_facts(repo, batch, b.data, c)
        context = _context_line(repo, b.data, c)
    return [f"round {c['round']} of {limit} for {c['id']}", *facts, context]


def _context_line(repo: Repo, d: dict[str, Any], c: dict[str, Any]) -> str:
    """The context size of the agent recorded on the CR, its Driver: the last call's prompt, read
    from the end of its transcript. Not an error when it cannot be measured."""
    agent = c.get("agent")
    if not agent:
        return "context: not measured (no agent recorded)"
    if d.get("host") == "copilot":
        return "context: not measured (Copilot gives no per-agent record)"
    try:
        sessions = foreman_uuid(d)
    except ChantierError:
        return "context: not measured (no steering transcript recorded)"
    n = agent_context(repo.session_root, sessions, agent)
    if n is None:
        return f"context: not measured (no transcript found for agent {agent})"
    return f"context: {n} tokens (agent {agent})"


def handback(args) -> list[str]:
    """A Driver's end, in the state first: `ready <link>` or `blocked <reason>`. Prints the line
    to send the Foreman, and what the state did with it."""
    repo = open_repo()
    note = " ".join(args.note).strip()
    no_gate = handback_args(args, note)
    with (
        changes_lock(repo),
        RenderedBatch(repo, find_cr_batch(repo, args.cr, args.batch), actor="driver") as b,
    ):
        c = live_cr(b, args.cr)
        line = f"[driver {args.cr}→foreman] hand-back {args.result} {note}"
        if args.result == "blocked":
            return handback_blocked(b, c, note, line)
        # a release with an unmerged PR recorded: the release PR is prepared and waits for
        # its merge (the checks of a CR, no verdict); with none, it is released
        prepared = c.get("kind") == "release" and bool(c.get("pr"))
        if c.get("kind") == "release" and not prepared:  # released: nothing is left to merge
            c["released"] = note.split()[0]
            b.log("handback", args.cr, result=args.result, note=note)
            done_cr(b, c)
            b.touch(c, status="merged")
            return [
                line,
                f"{args.cr} released, in 3-done"
                + ("; every CR is merged or cancelled: `chantier pause`" if all_merged(b) else ""),
            ]
        if not c.get("pr"):
            raise ChantierError(f"{args.cr}: ready means a PR recorded (`chantier ship`)")
        handback_refusals(repo, b, c, no_gate, prepared)
        if no_gate is not None:
            line = f"[driver {args.cr}→foreman] hand-back ready, no long gate: {no_gate} {note}"
        b.log(
            "handback",
            args.cr,
            result=args.result,
            note=note,
            **({"no_gate": no_gate} if no_gate is not None else {}),
        )
        b.touch(c, status="ready")
        if prepared:
            return [line, f"{args.cr} ready: the release PR {c['pr']} waits for its merge"]
        return [line, f"{args.cr} ready"]


def note(args) -> list[str]:
    """A Driver's or worker's line in the CR's state: what was done or found, shown in its
    STATUS.md. `--draft <path>` names a file the user reviews and edits in place."""
    repo = open_repo()
    text = " ".join(args.text).strip()
    if not text and not args.draft:
        raise ChantierError("note <cr> <text> | note <cr> --draft <path>", EXIT_USAGE)
    with RenderedBatch(repo, find_cr_batch(repo, args.cr, args.batch), actor="driver") as b:
        c = b.cr(args.cr)
        if args.draft:
            path = Path(args.draft).expanduser()
            if not path.is_file():
                raise ChantierError(
                    f"note --draft <path of an existing file>, not {args.draft!r}", EXIT_USAGE
                )
            draft = path.resolve().as_posix()
            if draft not in c.setdefault("drafts", []):
                c["drafts"].append(draft)
            text = text or f"draft: {draft}"
        c.setdefault("notes", []).append(text)
        b.touch(c)
        b.log("note", args.cr, note=text)
        context = _context_line(repo, b.data, c)
    return ["ok", context]


def log(args) -> list[str]:
    """The CR's events, readable: what happened and when."""
    repo = open_repo()
    batch, _, c = batch_cr(repo, args.cr, args.batch)
    lines = []
    for e in cr_events(repo, batch, c["id"]):
        rest = {
            k: v
            for k, v in e.items()
            if k not in {"t", "actor", "kind", "cr"} and v not in (None, "", [])
        }
        lines.append(
            f"{e['t']} {e['actor']} {e['kind']}"
            + (" " + " ".join(f"{k}={v}" for k, v in rest.items()) if rest else "")
        )
    return lines or [f"no event for {c['id']}"]


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "take",
        take,
        "a Driver takes the CR (or `stack`): the slot, then its facts",
        BATCH_EPOCH,
    )
    s.add_argument("cr", help="the CR, or `stack` for the stack driver")
    s.add_argument(
        "--note",
        help="why a ready or blocked CR goes back to a Driver, or a working CR "
        "restarts (needs `agents set <cr> -` first)",
    )

    s = add_command(
        sub,
        "round",
        round_,
        "count a round of the CR (exit 5 past the budget or the limit); its facts",
        BATCH,
    )
    s.add_argument("cr")
    s.add_argument("--note", help="the round's brief, kept in the log")

    s = add_command(
        sub, "handback", handback, "a Driver's end: ready <link> or blocked <reason>", BATCH
    )
    s.add_argument("cr")
    s.add_argument("result", choices=["ready", "blocked"])
    s.add_argument("note", nargs="*")
    s.add_argument(
        "--no-gate",
        metavar="REASON",
        help="ready: the project's rule that declares no long gate or exempts this CR "
        "from it; the steering session checks it",
    )

    s = add_command(sub, "note", note, "a line in the CR's record, shown in its STATUS.md", BATCH)
    s.add_argument("cr")
    s.add_argument("text", nargs="*")
    s.add_argument("--draft", help="a file the user reviews and edits in place")

    s = add_command(sub, "log", log, "the CR's events", BATCH)
    s.add_argument("cr")

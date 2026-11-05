"""`chantier` entry point: argparse, at most ten output lines, exit codes from ChantierError."""
from __future__ import annotations

import argparse
import sys

from . import __version__, commands
from .state import ChantierError

MAX_LINES = 10
# The facts of a CR, a list of files, the whole batch, or what the user approves, is useless cut short.
FULL_OUTPUT = {"take", "round", "handoff", "asks", "close", "rules", "log", "status"}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="chantier", description="The chantier team's CLI.")
    p.add_argument("--version", action="version", version=f"chantier {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def cmd(name, fn, help_, batch=True, epoch=False):
        s = sub.add_parser(name, help=help_)
        s.set_defaults(fn=fn)
        if batch:
            s.add_argument("--batch", help="batch id (default: $CHANTIER_BATCH, else the only open one)")
        if epoch:
            s.add_argument("--epoch", type=int, help="the Foreman's epoch; stale ones exit 3")
        return s

    cmd("preflight", commands.preflight, "check P1 and P4–P8; exit 2 if any fails", False)

    s = cmd("file", commands.file_cr, "file a request in the inbox", False)
    s.add_argument("item", help="request text, or @path to the raw request")
    s.add_argument("--slug", help="folder name when the inferred slug is already used")

    s = cmd("triage", commands.triage, "move an inbox CR to the priority backlog", False)
    s.add_argument("item", help="path to the inbox CR folder")
    s.add_argument("--priority", required=True, choices=["P1", "P2", "P3", "P4"])

    s = cmd("abandon", commands.abandon, "move an explicitly abandoned CR to trash", False)
    s.add_argument("item", help="path to the unclaimed CR folder")

    s = cmd("open", commands.open_batch,
            "open a batch: each prepared CR gets its folder, and a branch and worktree name", False)
    s.add_argument("batch")
    s.add_argument("items", nargs="+", help="@path to a prepared CR folder or specification")
    s.add_argument("--slots", type=int, default=2)
    s.add_argument("--budget", type=float, help="USD; no Driver starts past it")
    s.add_argument("--stack", action="store_true", help="stacked PRs")
    s.add_argument("--qa", help="'all' or 1-based item numbers, e.g. 1,3")
    s.add_argument("--release", type=int, metavar="N",
                   help="the item number of the release CR; it starts once the others are merged")
    s.add_argument("--autonomous-releases", type=int, default=0, metavar="N",
                   help="releases the user allows without asking (needs --budget)")
    s.add_argument("--auto-merge-fixes", action="store_true",
                   help="the Foreman merges the release's ready fixes (needs --budget)")
    s.add_argument("--default-branch", help="default: the remote's HEAD")
    s.add_argument("--remote", default="origin")

    s = cmd("order", commands.order,
            "the user's word, recorded at once; the Foreman does what needs its hands",
            epoch=True)
    s.add_argument("kind", help="add, drop, merged, note, rounds, slots, budget; for the release "
                   "CR: approve, grant; the Foreman: done <O-k>, merged --epoch")
    s.add_argument("cr", nargs="?", default="-", help="the CR, or the order id for `done`")
    s.add_argument("--note", help="add: @<folder>; note: the line; rounds, slots, budget: the "
                   "number; approve: the action; grant: releases=N auto-merge=on|off budget=N")
    s.add_argument("--fix-for", help="add: the release CR this fix is for")

    s = cmd("foreman", commands.foreman,
            "the Foreman claims its epoch (set) and records its transcript", epoch=True)
    s.add_argument("action", choices=["set", "get", "transcript"])
    s.add_argument("value", nargs="?")

    s = cmd("status", commands.status,
            "one line per CR, the pending orders, the unread asks; --refresh: the live facts",
            epoch=True)
    s.add_argument("--notes", action="store_true", help="each CR's last note")
    s.add_argument("--refresh", action="store_true",
                   help="the silent Drivers and the spend (recorded); with --epoch, the "
                        "Foreman's wake")

    s = cmd("asks", commands.asks, "the Foreman's asks still unread; with text, record one")
    s.add_argument("text", nargs="*", help="the Foreman's own ask")
    s.add_argument("--read", metavar="A-k|all", help="mark heard")

    s = cmd("agents", commands.agents, "map a CR (or stack, qa:<cr>) to its agent id", epoch=True)
    s.add_argument("action", choices=["set"])
    s.add_argument("cr")
    s.add_argument("agent", help="the agent id; `-` clears it")

    s = cmd("take", commands.take,
            "a Driver takes the CR (or `stack`, or a CR in qa): the slot, then its facts",
            epoch=True)
    s.add_argument("cr", help="the CR, or `stack` for the stack driver")
    s.add_argument("--note", help="why a ready or blocked CR goes back to a Driver")

    s = cmd("round", commands.round_, "count a round of the CR (exit 5 past the limit); its facts")
    s.add_argument("cr")
    s.add_argument("--note", help="the round's brief, kept in the log")

    s = cmd("handback", commands.handback, "a Driver's end: ready <link> or blocked <reason>")
    s.add_argument("cr")
    s.add_argument("result", choices=["ready", "blocked"])
    s.add_argument("note", nargs="*")

    s = cmd("note", commands.note, "a line in the CR's record, shown in its STATUS.md")
    s.add_argument("cr")
    s.add_argument("text", nargs="*")
    s.add_argument("--draft", help="a file the user reviews and edits in place")

    s = cmd("log", commands.log, "the CR's events")
    s.add_argument("cr")

    cmd("rules", commands.rules, "the project's instruction file and the files it links")

    s = cmd("handoff", commands.handoff, "the CR's facts, for any agent; changes nothing")
    s.add_argument("cr")

    s = cmd("gate", commands.gate, "run the long gate in the CR worktree, alone in the repository")
    s.add_argument("cr")
    s.add_argument("command", help="the command, from the project's rules")

    s = cmd("ship", commands.ship, "record the PR the Driver opened or updated; say what is off")
    s.add_argument("cr")
    s.add_argument("pr", help="the PR link")

    s = cmd("stack", commands.stack, "the stack's order, as its driver set it")
    s.add_argument("crs", nargs="+", help="the CRs, bottom first")

    s = cmd("qa", commands.qa, "the QA driver's end: its findings, with proof in evidence/")
    s.add_argument("cr")
    s.add_argument("--findings", required=True, help="markdown file, one finding per bullet")

    s = cmd("release", commands.release,
            "release driver: start an attempt, go for an irreversible action, published")
    s.add_argument("action", choices=["start", "go", "published"])
    s.add_argument("cr")
    s.add_argument("--note", help="go: the irreversible action; published: version and link")

    s = cmd("cancel", commands.cancel, "stop a CR's processes and mark it cancelled", epoch=True)
    s.add_argument("cr")

    cmd("land", commands.land, "finish the batch: refused while anything is live", epoch=True)

    s = cmd("close", commands.close, "what deleting a landed batch would remove; --yes deletes it")
    s.add_argument("--yes", action="store_true", help="on the user's word")

    s = cmd("cost", commands.cost, "price the Foreman's transcript and its subagents")
    s.add_argument("--by", choices=["role", "cr"], default="role")
    s.add_argument("--summary", action="store_true",
                   help="total, budget, orchestration against work, the costliest CRs")
    return p


def main(argv: list[str] | None = None) -> int:
    # Output holds `→` and paths: UTF-8 everywhere, not the Windows code page of a pipe.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    try:
        result = args.fn(args)
    except ChantierError as e:
        print(f"error: {e}", file=sys.stderr)
        return e.code
    lines, code = result if isinstance(result, tuple) else (result, 0)
    if args.cmd not in FULL_OUTPUT and len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES - 1] + [f"… {len(lines) - MAX_LINES + 1} more lines"]
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())

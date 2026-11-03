"""`chantier` entry point: argparse, at most ten output lines, exit codes from ChantierError."""
from __future__ import annotations

import argparse
import sys

from . import __version__, commands
from .state import EXIT_USAGE, ChantierError

MAX_LINES = 10
# A prompt is useless cut short: it prints every line.
FULL_OUTPUT = {"spawn"}


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

    cmd("preflight", commands.preflight, "check P1 and P4–P9; exit 2 if any fails", False)

    s = cmd("file", commands.file_cr, "file a request in the inbox", False)
    s.add_argument("item", help="request text, or @path to the raw request")
    s.add_argument("--slug", help="folder name when the inferred slug is already used")

    s = cmd("triage", commands.triage, "move an inbox CR to the priority backlog", False)
    s.add_argument("item", help="path to the inbox CR folder")
    s.add_argument("--priority", required=True, choices=["P1", "P2", "P3", "P4"])

    s = cmd("abandon", commands.abandon, "move an explicitly abandoned CR to trash", False)
    s.add_argument("item", help="path to the unclaimed CR folder")

    s = cmd("open", commands.open_batch, "open a batch of prepared CR folders", False)
    s.add_argument("batch")
    s.add_argument("items", nargs="+", help="@path to a prepared CR folder or specification")
    s.add_argument("--slots", type=int, default=2)
    s.add_argument("--budget", type=float, help="USD; the Foreman stops spawning past it")
    s.add_argument("--stack", action="store_true", help="stacked PRs")
    s.add_argument("--qa", help="'all' or 1-based item numbers, e.g. 1,3")
    s.add_argument("--release", type=int, metavar="N",
                   help="the item number of the release CR; it starts once the others are merged")
    s.add_argument("--autonomous-releases", type=int, default=0, metavar="N",
                   help="releases the user allows without asking (needs --budget)")
    s.add_argument("--auto-merge-fixes", choices=["rebase", "squash", "merge"],
                   help="the CLI merges the release's ready fixes, by this method (needs --budget)")
    s.add_argument("--no-worktrees", action="store_true")
    s.add_argument("--chief-of-staff", help="the Chief of Staff's session id")
    s.add_argument("--fast-gate", action="append", help="from AGENTS.md; repeat for several")
    s.add_argument("--long-gate", action="append", help="from AGENTS.md; repeat for several")
    s.add_argument("--default-branch", help="default: the remote's HEAD")
    s.add_argument("--remote", default="origin")
    s.add_argument("--agent", action="append", metavar="ROLE=AGENT",
                   help="a role runs this agent (from AGENTS.md); repeatable")
    s.add_argument("--review", action="append", metavar="NAME=AGENT:TASK",
                   help="an extra review step after the Inspector; repeatable")
    s.add_argument("--claude-projects-dir", help="Claude transcripts (default: ~/.claude/projects)")

    s = cmd("order", commands.order, "record an order for the Foreman; prints the message")
    s.add_argument("kind", help="add, drop, first, change, merged, pause, resume; for the release "
                   "CR: fix, approve, grant")
    s.add_argument("cr", nargs="?", default="-")
    s.add_argument("--note")

    s = cmd("foreman", commands.foreman,
            "the Foreman's session, or its transcript", epoch=True)
    s.add_argument("action", choices=["set", "get", "transcript"])
    s.add_argument("value", nargs="?")

    s = cmd("status", commands.status, "one line per CR")
    s.add_argument("--json", action="store_true")
    s.add_argument("--notes", action="store_true")

    s = cmd("agents", commands.agents, "map a CR (or stack, qa:<cr>) to its agent id", epoch=True)
    s.add_argument("action", choices=["get", "set"])
    s.add_argument("cr")
    s.add_argument("agent", nargs="?")

    s = cmd("spawn", commands.spawn, "the agent and the whole prompt for one spawn")
    s.add_argument("role")
    s.add_argument("cr", help="the CR, or `stack` for the stack driver")
    s.add_argument("--note", help="the rest of the Foreman's action line, or the round's brief")

    s = cmd("event", commands.event, "feed one event to the decision table; prints actions",
            epoch=True)
    s.add_argument("kind", nargs="?", help="event kind (omit with --order)")
    s.add_argument("cr", nargs="?", default="-")
    s.add_argument("note", nargs="*")
    s.add_argument("--order", help="an order id from `chantier order`")

    s = cmd("report", commands.report, "a Driver's progress report")
    s.add_argument("cr")
    s.add_argument("kind")
    s.add_argument("note", nargs="*")
    s.add_argument("--note", dest="note_opt", help="same as the trailing words")

    cmd("heartbeat", commands.heartbeat, "the Foreman's wake: liveness and spend", epoch=True)

    s = cmd("gate", commands.gate, "run the recorded gates in the CR worktree")
    s.add_argument("cr")
    s.add_argument("--long", action="store_true")

    s = cmd("wait", commands.wait, "block until the PR's checks finish")
    s.add_argument("what", choices=["ci"])
    s.add_argument("cr")
    s.add_argument("--max", type=float, default=3600, help="seconds")

    s = cmd("ci", commands.ci_classify, "classify a red PR: product, infra, known-red-on-main")
    s.add_argument("action", choices=["classify"])
    s.add_argument("cr")

    s = cmd("ship", commands.ship, "rebase, push, open or update the PR")
    s.add_argument("cr")
    s.add_argument("--title")

    s = cmd("stack", commands.stack, "stack order or restack")
    s.add_argument("action", choices=["order", "restack"])
    s.add_argument("crs", nargs="*")

    s = cmd("qa", commands.qa, "QA driver: start or done")
    s.add_argument("action", choices=["start", "done"])
    s.add_argument("cr")
    s.add_argument("--findings", help="markdown file, one finding per bullet")

    s = cmd("release", commands.release,
            "release driver: start an attempt, go for an irreversible action, published")
    s.add_argument("action", choices=["start", "go", "published"])
    s.add_argument("cr")
    s.add_argument("--note", help="go: the irreversible action; published: version and link")

    s = cmd("merge", commands.merge, "merge a release's fix (grant) or the release PR (after go)",
            epoch=True)
    s.add_argument("cr")
    s.add_argument("--method", choices=["rebase", "squash", "merge"], help="the release PR's")

    s = cmd("cancel", commands.cancel, "stop a CR's processes and mark it cancelled", epoch=True)
    s.add_argument("cr")

    cmd("land", commands.land, "close the batch: refused while anything is live", epoch=True)

    s = cmd("cost", commands.cost, "price the Foreman's transcript and its subagents")
    s.add_argument("--by", choices=["role", "cr"], default="role")
    s.add_argument("--update", action="store_true", help="store the total as spent_usd")
    s.add_argument("--transcript", help="session uuid (default: the recorded one)")
    s.add_argument("--host", choices=["claude", "copilot"],
                   help="default: the batch's; Copilot prices through copilot-session-usage (run by uv)")
    return p


def main(argv: list[str] | None = None) -> int:
    # Output holds `→` and paths: UTF-8 everywhere, not the Windows code page of a pipe.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    if isinstance(getattr(args, "note", None), list):
        args.note = " ".join(args.note) or getattr(args, "note_opt", None)
    if args.cmd == "event" and not args.order and not args.kind:
        print("error: event needs a kind, or --order", file=sys.stderr)
        return EXIT_USAGE
    if args.cmd == "agents" and args.action == "set" and not args.agent:
        print("error: agents set <cr> <agent-id>", file=sys.stderr)
        return EXIT_USAGE
    try:
        result = args.fn(args)
    except ChantierError as e:
        print(f"error: {e}", file=sys.stderr)
        return e.code
    lines, code = result if isinstance(result, tuple) else (result, 0)
    if args.cmd not in FULL_OUTPUT and not getattr(args, "json", False) and len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES - 1] + [f"… {len(lines) - MAX_LINES + 1} more lines"]
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())

"""`chantier` entry point: argparse, at most ten output lines, exit codes from ChantierError."""
from __future__ import annotations

import argparse
import sys

from . import __version__, commands
from .state import EXIT_USAGE, ChantierError

MAX_LINES = 10


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="chantier", description="Chief of Staff CLI (design 5).")
    p.add_argument("--version", action="version", version=f"chantier {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def cmd(name, fn, help_, batch=True, epoch=False):
        s = sub.add_parser(name, help=help_)
        s.set_defaults(fn=fn)
        if batch:
            s.add_argument("--batch", help="batch id (default: $CHANTIER_BATCH, else the latest open)")
        if epoch:
            s.add_argument("--epoch", type=int, help="the Foreman's epoch; stale ones exit 3")
        return s

    s = cmd("setup", commands.setup, "write .agents/chantier.json and install the agent files", False)
    s.add_argument("--force", action="store_true", help="replace locally edited agent files")
    s.add_argument("--host", choices=["claude", "copilot"], help="default: detected")
    cmd("preflight", commands.preflight, "check P1 and P4–P8; exit 2 if any fails", False)

    s = cmd("models", commands.models_cmd, "show, check, get or audit the models of each role")
    s.add_argument("action", nargs="?", default="show", choices=["show", "check", "get", "audit"])
    s.add_argument("role", nargs="?", help="for get: the role to spawn")
    s.add_argument("--cr", help="for get: the CR the spawn works on")
    s.add_argument("--host", choices=["claude", "copilot"], help="default: detected")
    s.add_argument("--session", help="for audit: the Copilot session id (default: this one)")

    s = cmd("open", commands.open_batch, "open a batch: CRs, branches, worktrees, brief", False)
    s.add_argument("batch")
    s.add_argument("items", nargs="+", help="a title, or @path to a backlog item")
    s.add_argument("--slots", type=int, default=2)
    s.add_argument("--budget", type=float, help="USD; the Foreman stops spawning past it")
    s.add_argument("--stack", action="store_true", help="stacked PRs")
    s.add_argument("--qa", help="'all' or 1-based item numbers, e.g. 1,3")
    s.add_argument("--no-worktrees", action="store_true")
    s.add_argument("--chief-of-staff", help="the Chief of Staff's session id")

    s = cmd("add", commands.add, "add a queued CR to a batch (the Foreman's order-add)")
    s.add_argument("item")
    s.add_argument("--qa", action="store_true")

    s = cmd("order", commands.order, "record an order for the Foreman; prints the message")
    s.add_argument("kind", help="add, drop, first, change, merged, pause, resume")
    s.add_argument("cr", nargs="?", default="-")
    s.add_argument("--note")

    s = cmd("foreman", commands.foreman, "set, get, or record the Foreman's transcript", epoch=True)
    s.add_argument("action", choices=["set", "get", "transcript"])
    s.add_argument("value", nargs="?")

    s = cmd("status", commands.status, "one line per CR")
    s.add_argument("--json", action="store_true")
    s.add_argument("--notes", action="store_true")

    s = cmd("agents", commands.agents, "map a CR (or stack, qa:<cr>) to its agent id", epoch=True)
    s.add_argument("action", choices=["get", "set"])
    s.add_argument("cr")
    s.add_argument("agent", nargs="?")

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

    cmd("heartbeat", commands.heartbeat, "the Foreman's /loop wake", epoch=True)

    s = cmd("gate", commands.gate, "run the configured gates in the CR worktree")
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

    s = cmd("cancel", commands.cancel, "stop a CR's processes and mark it cancelled", epoch=True)
    s.add_argument("cr")

    cmd("land", commands.land, "close the batch: refused while anything is live", epoch=True)

    s = cmd("cost", commands.cost, "price the Foreman's transcript and its subagents")
    s.add_argument("--by", choices=["role", "cr"], default="role")
    s.add_argument("--update", action="store_true", help="store the total as spent_usd")
    s.add_argument("--transcript", help="session uuid (default: the recorded one)")
    s.add_argument("--host", choices=["claude", "copilot"],
                   help="default: detected; Copilot needs copilot-session-usage >= 1.0")
    return p


def main(argv: list[str] | None = None) -> int:
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
    if not getattr(args, "json", False) and len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES - 1] + [f"… {len(lines) - MAX_LINES + 1} more lines"]
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())

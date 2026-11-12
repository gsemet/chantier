"""`chantier` entry point: argparse, at most ten output lines, exit codes from ChantierError."""
from __future__ import annotations

import argparse
import sys

from . import __version__, board, commands
from . import state
from .state import ChantierError

MAX_LINES = 10
# The facts of a CR, a list of files, the whole batch, or what the user approves, is useless cut short.
FULL_OUTPUT = {"take", "round", "handoff", "asks", "close", "pause", "rules", "log", "status", "cost",
               "playbook", "preflight"}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="chantier", description="The chantier team's CLI.")
    p.add_argument("--version", action="version", version=f"chantier {__version__}")
    p.add_argument("--project", help="the project's folder in a planning surface "
                   "(`<surface>/projects/<name>`, or the bare name); omitted: the project's own "
                   ".agents/changes/, or the surface's only project")
    sub = p.add_subparsers(dest="cmd", required=True)

    def cmd(name, fn, help_, batch=True, epoch=False):
        s = sub.add_parser(name, help=help_)
        s.set_defaults(fn=fn)
        s.add_argument("--project", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        if batch:
            s.add_argument("--batch", help="batch number, 4 or batch-04 (default: $CHANTIER_BATCH, else the only running one)")
        if epoch:
            s.add_argument("--epoch", type=int, help="the Foreman's epoch; stale ones exit 3")
        return s

    s = cmd("preflight", commands.preflight, "check P1, P4–P8, P10 and P12; exit 2 if any fails (P10 only warns)", False)
    s.add_argument("--direct", action="store_true",
                   help="the Chief of Staff steers the batch: P1 passes on any Claude Code entry point")

    cmd("init", commands.init, "create the empty stage folders of the planning folder and its .gitignore; changes nothing else", False)

    s = cmd("file", commands.file_cr, "file a request in the inbox", False)
    s.add_argument("item", help="request text, or @path to the raw request")
    s.add_argument("--slug", help="folder name when the inferred slug is already used")

    s = cmd("triage", commands.triage, "move an inbox, backlog or 3-ready CR to a priority of the backlog, or to 3-ready", False)
    s.add_argument("item", help="path to the CR folder: 1-inbox/<item>, 2-backlog/P<n>/<item> or 3-ready/<item>")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--priority", choices=["P1", "P2", "P3", "P4"])
    g.add_argument("--ready", action="store_true", help="the CR waits in 3-ready for the next batch")

    s = cmd("abandon", commands.abandon, "move an explicitly abandoned CR to trash", False)
    s.add_argument("item", help="path to the unclaimed CR folder")

    s = cmd("restore", commands.restore, "bring a trashed CR back to the inbox", False)
    s.add_argument("item", help="path to the folder directly under 6-trash")
    s.add_argument("--slug", help="the inbox name, when the old one is taken or to rename")

    s = cmd("open", commands.open_batch,
            "open a batch: each prepared CR gets its folder, and a branch and worktree name", False)
    s.add_argument("items", nargs="+", help="path to a prepared CR folder or specification")
    s.add_argument("--slots", type=int, default=4)
    s.add_argument("--budget", type=float, help="USD; no Driver starts past it")
    s.add_argument("--mode", choices=["parallel", "series", "stack"], default="parallel",
                   help="parallel (default): independent CRs, each on the default branch; series: "
                        "one after the other, in the order given, each on the previous one's "
                        "branch; stack: independent CRs, then a stack driver stacks the PRs")
    s.add_argument("--release", type=int, metavar="N",
                   help="the item number of the release CR; it waits for every other CR: prepared on top of a stack or a series once they are ready, after the merges in a parallel batch; its PR is the user's to merge")
    s.add_argument("--autonomous-releases", type=int, default=0, metavar="N",
                   help="releases the user allows without asking (needs --budget)")
    s.add_argument("--grant-fixes", action="store_true",
                   help="the Foreman starts and merges the release's fixes (needs --budget)")
    s.add_argument("--direct", action="store_true",
                   help="no Foreman session: the Chief of Staff steers the batch itself")
    s.add_argument("--default-branch", help="default: the remote's HEAD")
    s.add_argument("--remote", default="origin")

    s = cmd("order", commands.order,
            "the user's word, recorded at once; the Foreman does what needs its hands",
            epoch=True)
    s.add_argument("kind", help="add [--release], after, drop, merged, note, rounds, slots, budget, qa, mode (series to stack); "
                   "for the release CR: approve, grant, confirm; the Foreman: done <O-k>, merged "
                   "--epoch, add --fix-for --epoch")
    s.add_argument("cr", nargs="?", default="-", help="the CR, or the order id for `done`")
    s.add_argument("--note", help="add: <folder>, or a release's fix file; after: the CR ids it waits "
                   "for, comma separated, or - for none; note: the line; rounds, "
                   "slots, budget: the number; qa: what to test; approve: the action; grant: "
                   "releases=N fixes=on|off budget=N; confirm: the user's word to run the "
                   "release procedure, once the other CRs are merged")
    s.add_argument("--fix-for", help="add: the release CR this fix is for")
    s.add_argument("--release", action="store_true",
                   help="add: the folder is the batch's release CR, which waits for every other CR (refused once it has started)")

    s = cmd("foreman", commands.foreman,
            "the Foreman claims its epoch (set) and records its transcript", epoch=True)
    s.add_argument("action", choices=["set", "get", "transcript"])
    s.add_argument("value", nargs="?")

    s = cmd("seat", commands.seat,
            "the repository's Chief of Staff session: show, take or leave the seat", False)
    s.add_argument("action", nargs="?", choices=["get", "take", "leave"], default="get")
    s.add_argument("session", nargs="?", help="the session id, for take and leave")
    s.add_argument("--env", help="take: the machine's name, or Remote")
    s.add_argument("--title", help="take: the session's current title")
    s.add_argument("--link", help="take: the session's link")
    s.add_argument("--over", metavar="SESSION",
                   help="take: the session whose seat this one takes, on the user's word")

    s = cmd("board", board.board,
            "serve the planning folder's batch, CRs, inbox and backlog as a read-only web page, "
            "for the user in remote; writes nothing, no password", False)
    s.add_argument("--host", help="the address to listen on (default: chantier.yaml's board.host, "
                   "else 127.0.0.1)")
    s.add_argument("--port", type=int, help="the port (default: chantier.yaml's board.port, else 8765)")
    s.add_argument("--seat", metavar="SESSION",
                   help="the Chief of Staff session this board is for: it stops when the seat no "
                        "longer names it")

    s = cmd("status", commands.status,
            "one line per CR, the open orders (untouched, then applied), the unread asks; "
            "--refresh: the live facts; its line says `heartbeat N min` (since the last "
            "`--refresh --epoch`), `never` or `stopped`",
            epoch=True)
    s.add_argument("--notes", action="store_true", help="each CR's last note")
    s.add_argument("--refresh", action="store_true",
                   help="the activity of each working CR (age of its last event or session "
                        "record, `gate running`, `not measured`) and the spend (recorded); "
                        "with --epoch, the steering session's wake: it records the heartbeat "
                        "and prints the gap since the wake before; without, it moves nothing")
    s.add_argument("--stop-heartbeat", action="store_true",
                   help="with --epoch: record that the steering session ended its loop "
                        "(`heartbeat stopped`, until the next wake)")

    s = cmd("asks", commands.asks, "the Foreman's asks still unread; with text, record one")
    s.add_argument("text", nargs="*", help="the Foreman's own ask")
    s.add_argument("--read", metavar="A-k|all", help="mark heard")

    s = cmd("agents", commands.agents, "map a CR (or stack) to its agent id", epoch=True)
    s.add_argument("action", choices=["set"])
    s.add_argument("cr")
    s.add_argument("agent", help="the agent id; `-` clears it")

    s = cmd("take", commands.take,
            "a Driver takes the CR (or `stack`): the slot, then its facts",
            epoch=True)
    s.add_argument("cr", help="the CR, or `stack` for the stack driver")
    s.add_argument("--note", help="why a ready or blocked CR goes back to a Driver, or a working CR "
                        "restarts (needs `agents set <cr> -` first)")

    s = cmd("round", commands.round_, "count a round of the CR (exit 5 past the budget or the limit); its facts")
    s.add_argument("cr")
    s.add_argument("--note", help="the round's brief, kept in the log")

    s = cmd("handback", commands.handback, "a Driver's end: ready <link> or blocked <reason>")
    s.add_argument("cr")
    s.add_argument("result", choices=["ready", "blocked"])
    s.add_argument("note", nargs="*")
    s.add_argument("--no-gate", metavar="REASON",
                   help="ready: the project's rule that declares no long gate or exempts this CR "
                        "from it; the steering session checks it")

    s = cmd("note", commands.note, "a line in the CR's record, shown in its STATUS.md")
    s.add_argument("cr")
    s.add_argument("text", nargs="*")
    s.add_argument("--draft", help="a file the user reviews and edits in place")

    s = cmd("log", commands.log, "the CR's events")
    s.add_argument("cr")

    cmd("rules", commands.rules, "the project's instruction file and the files it links")

    s = cmd("playbook", commands.playbook,
            "the agent and model each role runs, from chantier.yaml (or, with --batch, as the batch opened); "
            "exit 2 if the file is invalid")
    s.add_argument("--host", choices=["claude", "copilot"],
                   help="the host to resolve for (default: the detected host); ignored with --batch")

    s = cmd("handoff", commands.handoff, "the CR's facts, for any agent; changes nothing")
    s.add_argument("cr")

    s = cmd("gate", commands.gate, "run the long gate in the CR worktree, alone in the repository")
    s.add_argument("cr")
    s.add_argument("command", nargs="+", help="the long gate's commands, from the project's rules: "
                   "one per argument, never chained with ; or &&; they stop at the first failure")

    s = cmd("verdict", commands.verdict, "the Verifier's verdict on the CR's worktree head: "
            "VERIFIED or \"NOT VERIFIED\"")
    s.add_argument("cr")
    s.add_argument("result", nargs="+", help="VERIFIED, or NOT VERIFIED (one argument or two)")

    s = cmd("ship", commands.ship, "record the PR the Driver opened or updated; say what is off")
    s.add_argument("cr")
    s.add_argument("pr", help="the PR link")

    s = cmd("stack", commands.stack, "the stack's order, as its driver set it")
    s.add_argument("crs", nargs="+", help="the CRs, bottom first")

    s = cmd("release", commands.release,
            "release driver: start an attempt, go for an irreversible action, published")
    s.add_argument("action", choices=["start", "go", "published"])
    s.add_argument("cr")
    s.add_argument("--note", help="go: the irreversible action; published: version and link")

    s = cmd("cancel", commands.cancel, "stop a CR's processes and mark it cancelled", epoch=True)
    s.add_argument("cr")

    cmd("pause", commands.pause, "pause the batch once its work is done: refused while anything is live or already paused; prints the cost to date", epoch=True)

    s = cmd("close", commands.close, "refused while anything runs; prints the final cost and what deleting a paused batch would remove; --yes deletes it")
    s.add_argument("--yes", action="store_true", help="on the user's word")

    s = cmd("cost", commands.cost, "price the Foreman's transcript and its subagents")
    s.add_argument("--by", choices=["role", "cr"], default="role",
                   help="role: the Foreman, each Driver type, each worker type; cr: a CR's own")
    s.add_argument("--explain", action="store_true",
                   help="under each line: agents, model, shares of cost, calls after the cache "
                        "expired, restarted Drivers; ends with what the figures do not count")
    s.add_argument("--summary", action="store_true",
                   help="total, budget, Foreman, Drivers and workers, the costliest CRs")
    return p


def main(argv: list[str] | None = None) -> int:
    # Output holds `→` and paths: UTF-8 everywhere, not the Windows code page of a pipe.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    for name in ("cr", "fix_for"):  # one spelling of a CR, whatever the command
        if hasattr(args, name):
            setattr(args, name, state.normalize_cr(getattr(args, name)))
    if getattr(args, "crs", None):
        args.crs = [state.normalize_cr(x) for x in args.crs]
    state.PROJECT = args.project
    try:
        result = args.fn(args)
    except ChantierError as e:
        print(f"error: {e}", file=sys.stderr)
        return e.code
    lines, code = result if isinstance(result, tuple) else (result, 0)
    if args.cmd not in FULL_OUTPUT and len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES - 1] + [f"… {len(lines) - MAX_LINES + 1} more lines"]
    if lines:  # `board` printed its own lines while it served
        print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main())

"""`chantier` entry point: argparse, at most ten output lines, exit codes from ChantierError."""

from __future__ import annotations

import argparse
import sys
from typing import Any, NoReturn

from chantier import __version__, plugin_files
from chantier.clients import remote as client
from chantier.core import repo
from chantier.core.errors import ChantierError
from chantier.core.ids import normalize_cr
from chantier.declare import (
    access,
    batch_status,
    closing,
    cost,
    delivery,
    driver,
    facts,
    forge_stack,
    gate,
    help,
    host,
    intake,
    interests,
    journal,
    live,
    opening,
    orders,
    park,
    preflight,
    release,
    remote,
    rules,
    seat,
    serve,
    summary,
    sync,
    validate,
    watch,
    webui,
)
from chantier.near_misses import normalize
from chantier.writer import lines as writer_lines

MAX_LINES = 10
# The facts of a CR, a list of files, the whole batch, or what the user approves, is useless cut
# short.
FULL_OUTPUT = {
    "take",
    "round",
    "seat",  # the arrivals no watcher told, listed once
    "wait",
    "handoff",
    "asks",
    "close",
    "pause",
    "order",  # the end of the last CR prints its cleanup and the pause
    "handback",
    "cancel",
    "rules",
    "host",
    "help",
    "log",
    "status",
    "cost",
    "playbook",
    "preflight",
    "watch",
    "validate",
    "interests",
    "journal",
    "sync",  # a conflict names its files
}


class Usage(Exception):
    """What a quiet parser raises in place of printing and exiting."""


class _Quiet(argparse.ArgumentParser):
    """A parser that raises `Usage` where argparse would print and exit: the server judges the
    arguments of a client's command with it (the subparsers are of its class)."""

    def error(self, message: str) -> NoReturn:
        raise Usage(message)

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        raise Usage((message or "").strip() or "this option prints and exits")

    def _print_message(self, message: str, file: Any = None) -> None:
        pass


_MODULES = (
    preflight,
    intake,
    opening,
    orders,
    park,
    seat,
    serve,
    webui,
    live,
    batch_status,
    driver,
    access,
    host,
    rules,
    help,
    facts,
    gate,
    delivery,
    forge_stack,
    release,
    remote,
    closing,
    cost,
    summary,
    interests,
    journal,
    sync,
    validate,
    watch,
)


def _parser(quiet: bool = False) -> argparse.ArgumentParser:
    """The root parser and the options every command shares; each module declares its own."""
    kind = _Quiet if quiet else argparse.ArgumentParser
    p = kind(prog="chantier", description="The chantier team's CLI.")
    _root_options(p)
    sub = p.add_subparsers(dest="cmd", required=True)
    for module in _MODULES:
        module.register(sub)
    return p


def _root_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--version", action="version", version=f"chantier {__version__}")
    p.add_argument(
        "--project",
        help="the project's folder in a planning surface "
        "(`<surface>/projects/<name>`, or the bare name); omitted: the project's own "
        ".agents/changes/, or the surface's only project",
    )
    p.add_argument(
        "--profile",
        help="the profile (`chantier login`) that runs this command on its server, or `local` "
        "to run it here; omitted: the default profile, for the projects it was logged in for",
    )
    p.add_argument(
        "--skill",
        help="the chantier skill's folder, needed when this code runs from uv's cache (a plugin "
        "install); omitted: CHANTIER_SKILL_DIR, else the folder this code lives in",
    )


def _one_spelling_of_a_cr(args: argparse.Namespace) -> None:
    for name in ("cr", "fix_for"):
        if hasattr(args, name):
            setattr(args, name, normalize_cr(getattr(args, name)))
    if getattr(args, "crs", None):
        args.crs = [normalize_cr(x) for x in args.crs]


def cut(lines: list[str]) -> list[str]:
    """Past `MAX_LINES`, the output is cut from the end, but a last `watch: not running:` line
    (the Chief of Staff's trigger) stays last."""
    if len(lines) <= MAX_LINES:
        return lines
    if lines[-1].startswith("watch: not running:"):
        keep = MAX_LINES - 2
        return [*lines[:keep], f"… {len(lines) - keep - 1} more lines", lines[-1]]
    return [*lines[: MAX_LINES - 1], f"… {len(lines) - MAX_LINES + 1} more lines"]


def with_notes(lines: list[str]) -> list[str]:
    """The `writer: <state>: not pushed yet (...)` lines of a command that wrote to a surface,
    before a last `watch: not running:` line."""
    notes = writer_lines.notes()
    if not notes:
        return lines
    at = len(lines) - 1 if lines and lines[-1].startswith("watch: not running:") else len(lines)
    return [*lines[:at], *notes, *lines[at:]]


def main(argv: list[str] | None = None) -> int:
    # Output holds `→` and paths: UTF-8 everywhere, not the Windows code page of a pipe.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = _parser()
    argv = normalize(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(argv)
    _one_spelling_of_a_cr(args)
    repo.PROJECT = args.project
    repo.COMMAND = " ".join(
        filter(
            None,
            (
                args.cmd,
                getattr(args, "kind", None) if args.cmd == "order" else None,
                getattr(args, "action", None) if args.cmd == "summary" else None,
            ),
        )
    )
    plugin_files.SKILL = args.skill
    writer_lines.forget()
    try:
        sent = client.forward(args, argv, parser)
        if sent is not None:  # a profile's server ran it
            return sent
        result: Any = args.fn(args)
    except ChantierError as e:
        print(f"error: {e}", file=sys.stderr)
        return e.code
    lines, code = result if isinstance(result, tuple) else (result, 0)
    full = args.cmd in FULL_OUTPUT or (args.cmd == "order" and args.kind == "qa")  # a prompt
    if not full:
        lines = cut(lines)
    if args.cmd != "serve":  # its routes write too, and its output is its own
        lines = with_notes(lines)
    if lines:  # `serve` printed its own lines while it served
        print("\n".join(lines))
    return int(code)


if __name__ == "__main__":
    sys.exit(main())

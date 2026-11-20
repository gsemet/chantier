"""`chantier` entry point: argparse, at most ten output lines, exit codes from ChantierError."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from chantier import __version__, plugin_files
from chantier.core import repo
from chantier.core.errors import ChantierError
from chantier.core.ids import normalize_cr
from chantier.declare import (
    access,
    batch_status,
    board,
    closing,
    cost,
    delivery,
    driver,
    facts,
    forge_stack,
    gate,
    intake,
    interests,
    journal,
    live,
    opening,
    orders,
    preflight,
    release,
    rules,
    seat,
    summary,
    sync,
    validate,
    watch,
)
from chantier.writer import lines as writer_lines

MAX_LINES = 10
# The facts of a CR, a list of files, the whole batch, or what the user approves, is useless cut
# short.
FULL_OUTPUT = {
    "take",
    "round",
    "wait",
    "handoff",
    "asks",
    "close",
    "pause",
    "order",  # the end of the last CR prints its cleanup and the pause
    "handback",
    "cancel",
    "rules",
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


def _parser() -> argparse.ArgumentParser:
    """The root parser and the options every command shares; each module declares its own."""
    p = argparse.ArgumentParser(prog="chantier", description="The chantier team's CLI.")
    p.add_argument("--version", action="version", version=f"chantier {__version__}")
    p.add_argument(
        "--project",
        help="the project's folder in a planning surface "
        "(`<surface>/projects/<name>`, or the bare name); omitted: the project's own "
        ".agents/changes/, or the surface's only project",
    )
    p.add_argument(
        "--skill",
        help="the chantier skill's folder, needed when this code runs from uv's cache (a plugin "
        "install); omitted: CHANTIER_SKILL_DIR, else the folder this code lives in",
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    for module in (
        preflight,
        intake,
        opening,
        orders,
        seat,
        board,
        live,
        batch_status,
        driver,
        access,
        rules,
        facts,
        gate,
        delivery,
        forge_stack,
        release,
        closing,
        cost,
        summary,
        interests,
        journal,
        sync,
        validate,
        watch,
    ):
        module.register(sub)
    return p


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
    args = _parser().parse_args(argv)
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
        result: Any = args.fn(args)
    except ChantierError as e:
        print(f"error: {e}", file=sys.stderr)
        return e.code
    lines, code = result if isinstance(result, tuple) else (result, 0)
    full = args.cmd in FULL_OUTPUT or (args.cmd == "order" and args.kind == "qa")  # a prompt
    if not full:
        lines = cut(lines)
    if args.cmd != "board":  # its routes write too, and its output is its own
        lines = with_notes(lines)
    if lines:  # `board` printed its own lines while it served
        print("\n".join(lines))
    return int(code)


if __name__ == "__main__":
    sys.exit(main())

"""`chantier` entry point: argparse, at most ten output lines, exit codes from ChantierError."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from chantier import __version__, plugin_files
from chantier.board import command as board_command
from chantier.commands import (
    batch_status,
    closing,
    delivery,
    driver,
    facts,
    forge_stack,
    gate,
    intake,
    opening,
    orders,
    preflight,
    release,
    rules,
    seat,
    summary,
)
from chantier.commands.cost import command as cost_command
from chantier.core import repo
from chantier.core.errors import ChantierError
from chantier.core.records import normalize_cr

MAX_LINES = 10
# The facts of a CR, a list of files, the whole batch, or what the user approves, is useless cut
# short.
FULL_OUTPUT = {
    "take",
    "round",
    "handoff",
    "asks",
    "close",
    "pause",
    "rules",
    "log",
    "status",
    "cost",
    "playbook",
    "preflight",
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
        board_command,
        batch_status,
        driver,
        rules,
        facts,
        gate,
        delivery,
        forge_stack,
        release,
        closing,
        cost_command,
        summary,
    ):
        module.register(sub)
    return p


def _one_spelling_of_a_cr(args: argparse.Namespace) -> None:
    for name in ("cr", "fix_for"):
        if hasattr(args, name):
            setattr(args, name, normalize_cr(getattr(args, name)))
    if getattr(args, "crs", None):
        args.crs = [normalize_cr(x) for x in args.crs]


def main(argv: list[str] | None = None) -> int:
    # Output holds `→` and paths: UTF-8 everywhere, not the Windows code page of a pipe.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    _one_spelling_of_a_cr(args)
    repo.PROJECT = args.project
    plugin_files.SKILL = args.skill
    try:
        result: Any = args.fn(args)
    except ChantierError as e:
        print(f"error: {e}", file=sys.stderr)
        return e.code
    lines, code = result if isinstance(result, tuple) else (result, 0)
    if args.cmd not in FULL_OUTPUT and len(lines) > MAX_LINES:
        lines = [*lines[: MAX_LINES - 1], f"… {len(lines) - MAX_LINES + 1} more lines"]
    if lines:  # `board` printed its own lines while it served
        print("\n".join(lines))
    return int(code)


if __name__ == "__main__":
    sys.exit(main())

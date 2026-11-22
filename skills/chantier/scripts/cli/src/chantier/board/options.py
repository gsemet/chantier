"""The options of `chantier serve` that are checked or turned into the `server` entry before the
board starts."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from chantier.board.api import times
from chantier.board.watch_files import FileWatchThread
from chantier.core import clock
from chantier.core.errors import EXIT_USAGE, ChantierError

BOTH_FLAGS = (
    "--stop-idle and --forge-always do not go together: a board the pull path relies on for the "
    "forge must not stop by itself; pass one"
)


def ui_of(arg: Path | str) -> Path | None:
    """The folder to serve: `None` for `none`, else a folder holding an `index.html`."""
    if arg == "none":
        return None
    folder = Path(arg).resolve()
    if not (folder / "index.html").is_file():
        raise ChantierError(
            f"--ui {arg}: not a folder with an index.html: give a folder of static files, or none",
            EXIT_USAGE,
        )
    return folder


def extra_of(args: argparse.Namespace, files: FileWatchThread) -> dict[str, Any]:
    """The `server` entry's fields beyond the address: the file watch's mode, the idle stop, the
    forge always."""
    extra: dict[str, Any] = {"files": files.mode}
    if args.stop_idle:
        extra["stop_idle"] = int(times.IDLE_STOP_S)
    if args.forge_always:
        extra["forge"] = "always"
    return extra


def options_of(args: argparse.Namespace) -> Path | None:
    """The options checked before anything is read: the two flags that do not go together, the
    clock, the folder to serve (`ui_of`)."""
    if args.stop_idle and args.forge_always:
        raise ChantierError(BOTH_FLAGS, EXIT_USAGE)
    if args.clock:
        try:
            clock.fix(args.clock)
        except ValueError as e:
            raise ChantierError(
                f"--clock {args.clock!r}: use YYYY-MM-DDTHH:MM:SSZ", EXIT_USAGE
            ) from e
    return ui_of(args.ui)

"""One serving process per planning surface and machine. `chantier serve` takes `hub.lock` before
it looks at what runs, and holds it for its whole life (the forge hub loop uses the same handle):
a start that does not win it waits a little for the winner's `server` entry, then joins that board
or refuses. A running server that finds another live process recorded as the server stops itself."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from chantier.board.address import probe
from chantier.board.binding import not_started
from chantier.hub import state

WAIT_S = 20.0  # a start that lost waits this long for the winner's board to answer
STEP_S = 0.2
HELD = (
    "another start of chantier serve holds this surface and no board answers yet: wait, then "
    "run serve again"
)
STRAY = "board: another server (PID {pid}) holds this surface; stopping"


def wait_for_board(
    git_dir: Path,
    key: str,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """The `server` entry of the process that won the claim, once it answers; at the bound, the
    entry when one is recorded (the caller refuses it as a silent board), else a refusal."""
    deadline = clock() + WAIT_S
    while True:
        run = state.live_entry(git_dir, state.SERVER)
        if run is not None and isinstance(probe(run["host"], run["port"], key), dict):
            return run
        if clock() >= deadline:
            if run is not None:
                return run
            raise not_started(HELD)
        sleep(STEP_S)


def stray_check(git_dir: Path, stop: Callable[[], None]) -> Callable[[], None]:
    """The server's tick: when the live recorded server is another process, say so and stop (the
    clean stop, its writer's last cycle included). Nothing is written to `server.json`."""

    def check() -> None:
        pid = state.recorded_other(git_dir)
        if pid is not None:
            print(STRAY.format(pid=pid), file=sys.stderr, flush=True)
            stop()

    return check


def tick(git_dir: Path, ctx: Any, stop: Callable[[], None]) -> Callable[[], None]:
    """The server's pass: its entry put back when the file lost it, and a stop when another
    process is the recorded server."""
    stray = stray_check(git_dir, stop)

    def one() -> None:
        stray()
        state.reassert_server(git_dir, ctx.key.current(), ctx.key.read_current())

    return one

"""The parser of the `serve` command; the handlers load when one runs."""

from __future__ import annotations

import argparse
from pathlib import Path

from chantier.commands.registry import NO_BATCH, Subparsers, add_command

SHIPPED_UI = Path(__file__).resolve().parents[1] / "clients" / "web"
HELP = (
    "serve the board's API and the web client (or another UI: --ui) on this machine (on the "
    "local network with --host or chantier.yaml's board.host: network), behind a key"
)


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(sub, "serve", "chantier.board.command:board", HELP, NO_BATCH)
    s.add_argument(
        "--host",
        help="the address to listen on, for this start (default: chantier.yaml's board.host: "
        "network, this machine's local network address found at each start, else 127.0.0.1, "
        "this machine only; 0.0.0.0 or an address of this machine on the network opens it to "
        "the local network)",
    )
    s.add_argument(
        "--port",
        type=int,
        help="the port, or 0 for a free one the system picks (default: chantier.yaml's "
        "board.port, else 8765)",
    )
    s.add_argument(
        "--seat",
        metavar="SESSION",
        help="the Chief of Staff session this board is for: the board follows its seats and "
        "stops when none of them names its session any more; with none, it serves until stopped "
        "by hand",
    )
    s.add_argument(
        "--clock",
        metavar="TIMESTAMP",
        help="answer as if it were this instant (UTC, YYYY-MM-DDTHH:MM:SSZ), for screenshots "
        "and tests",
    )
    s.add_argument(
        "--ui",
        metavar="FOLDER",
        default=SHIPPED_UI,
        help="the folder of static files the board serves at `/` (default: the shipped web "
        "client); `none`: the API only, no page",
    )
    _switches(s)


def _switches(s: argparse.ArgumentParser) -> None:
    """The board's on/off options."""
    s.add_argument(
        "--new-key",
        action="store_true",
        help="replace the board's key: the old link stops working",
    )
    s.add_argument(
        "--stop-idle",
        action="store_true",
        help="stop by itself after 30 minutes with no client (no page, no watcher, no chantier "
        "live), after the writer's last cycle: what a watcher passes to the board it starts",
    )
    s.add_argument(
        "--forge-always",
        action="store_true",
        help="read the forge every 20 s with or without a client, for a host that cannot run "
        "the watcher (not with --stop-idle)",
    )

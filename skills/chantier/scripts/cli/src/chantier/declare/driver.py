"""The parser of the `driver` command(s); the handlers load when one runs."""

from __future__ import annotations

import argparse

from chantier.commands.registry import BATCH, BATCH_EPOCH, Subparsers, add_command, add_lease
from chantier.core.phases import PHASES


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "take",
        "chantier.commands.driver:take",
        "a Driver takes the CR (or `stack`): the slot, then its facts",
        BATCH_EPOCH,
    )
    s.add_argument("cr", help="the CR, or `stack` for the stack driver")
    s.add_argument(
        "--note",
        help="why a ready or blocked CR goes back to a Driver, or a working CR "
        "restarts (needs `agents set <cr> - --epoch <n>` first)",
    )
    s.add_argument(
        "--reclaim",
        action="store_true",
        help="take a unit whose lease is live (only on the user's word) or not confirmed (once "
        "the host shows its Driver ended): ends that lease and logs it",
    )

    s = add_command(
        sub,
        "round",
        "chantier.commands.driver:round_",
        "count a round of the CR (exit 5 past the budget or the limit); its facts",
        BATCH,
    )
    s.add_argument("cr")
    s.add_argument("--note", help="the round's brief, kept in the log")
    add_lease(s, required=True)
    _register_record(sub)
    _register_lease(sub)


def _register_record(sub: Subparsers) -> None:
    s = add_command(
        sub,
        "handback",
        "chantier.commands.driver:handback",
        "a Driver's end: ready <link> or blocked <reason>",
        BATCH,
    )
    s.add_argument("cr")
    s.add_argument("result", choices=["ready", "blocked"])
    s.add_argument("note", nargs="*")
    s.add_argument(
        "--no-gate",
        metavar="REASON",
        help="ready: the project's rule that declares no long gate or exempts this CR "
        "from it; the steering session checks it",
    )
    add_lease(s, required=True)

    s = add_command(
        sub,
        "note",
        "chantier.commands.driver_notes:note",
        "a line in the CR's record, shown in its STATUS.md",
        BATCH,
    )
    s.add_argument("cr")
    s.add_argument("text", nargs="*")
    s.add_argument("--draft", help="a file the user reviews and edits in place")
    add_lease(s)

    s = add_command(
        sub,
        "phase",
        "chantier.commands.driver_notes:phase",
        "record the step the CR is at, shown by the status, the board and the pane",
        BATCH,
    )
    s.add_argument("cr")
    s.add_argument("phase", choices=PHASES)
    s.add_argument("detail", nargs="*", help="review: the step's name; gate, release: optional")
    add_lease(s)

    s = add_command(sub, "log", "chantier.commands.driver:log", "the CR's events", BATCH)
    s.add_argument("cr")


def _register_lease(sub: Subparsers) -> None:
    s = add_command(
        sub,
        "lease",
        "chantier.commands.leases:lease",
        "a unit's lease: `lease <unit>` shows it, `lease <unit> renew --lease <n>` renews it, "
        "`lease <unit> hold --lease <n> -- <command> [args...]` keeps it live while the command "
        "runs",
        BATCH,
    )
    s.add_argument("unit", help="a CR, `stack` or a QA order `O-k`")
    s.add_argument(
        "rest",
        nargs=argparse.REMAINDER,
        help="[renew|hold] [--lease N] [--batch B] [-- <command> [args...]]: the form after the "
        "unit, as written in `lease --help`",
    )

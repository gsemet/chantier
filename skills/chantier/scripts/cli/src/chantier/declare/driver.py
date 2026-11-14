"""The parser of the `driver` command(s); the handlers load when one runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH, BATCH_EPOCH, Subparsers, add_command


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
        "restarts (needs `agents set <cr> -` first)",
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
    _register_record(sub)


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

    s = add_command(
        sub,
        "note",
        "chantier.commands.driver:note",
        "a line in the CR's record, shown in its STATUS.md",
        BATCH,
    )
    s.add_argument("cr")
    s.add_argument("text", nargs="*")
    s.add_argument("--draft", help="a file the user reviews and edits in place")

    s = add_command(sub, "log", "chantier.commands.driver:log", "the CR's events", BATCH)
    s.add_argument("cr")

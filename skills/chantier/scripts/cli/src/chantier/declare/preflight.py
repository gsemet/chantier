"""The parser of the `preflight` command(s); the handlers load when one runs."""

from __future__ import annotations

from chantier.commands.registry import NO_BATCH, Subparsers, add_command


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "preflight",
        "chantier.commands.preflight:preflight",
        "check P1, P4–P8, P10 and P12; exit 2 if any fails (P10 only warns)",
        NO_BATCH,
    )
    s.add_argument(
        "--direct",
        action="store_true",
        help="the Chief of Staff steers the batch: P1 passes on any Claude Code entry point",
    )

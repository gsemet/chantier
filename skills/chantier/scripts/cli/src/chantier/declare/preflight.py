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
    s.add_argument(
        "--mode",
        choices=["parallel", "series", "stack"],
        help="the batch's mode, as `open` takes it: stack adds the capability a stack",
    )
    s.add_argument(
        "--autonomous-releases",
        type=int,
        default=0,
        metavar="N",
        help="releases the user allows without asking: N > 0 adds a release on its own",
    )
    s.add_argument(
        "--grant-fixes",
        action="store_true",
        help="the release's fixes are merged on a grant: adds fixes on a grant",
    )

"""The parser of the `access` command; the handler loads when it runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH_EPOCH, Subparsers, add_command

HELP = (
    "explain, read-only, why this session may or may not write the planning folder, claim a CR "
    "or push its branch; it changes nothing and renews no lease"
)


def register(sub: Subparsers) -> None:
    """Declare `access`."""
    s = add_command(sub, "access", "chantier.commands.access:access", HELP, BATCH_EPOCH)
    s.add_argument(
        "action_or_cr",
        nargs="?",
        help="write, claim or push; or the CR, to answer all three",
    )
    s.add_argument("cr", nargs="?", help="the CR, after claim or push")
    s.add_argument(
        "--lease", type=int, help="push: the lease number the Driver holds (not renewed)"
    )

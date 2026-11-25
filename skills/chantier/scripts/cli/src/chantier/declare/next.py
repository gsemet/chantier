"""The parser of the `next` command; the handler loads when it runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH_EPOCH, Subparsers, add_command, add_lease

HELP = (
    "read-only advice: with `--epoch`, what the steering session has due; with `<cr>`, that CR's "
    "next step; with neither, the Chief of Staff's view. It records nothing, renews no lease and "
    "reads no forge"
)

LEASE = (
    "the lease number `take` printed: checked, never renewed; a stale one exits 3 (`claim lost`)"
)


def register(sub: Subparsers) -> None:
    """Declare `next`."""
    s = add_command(sub, "next", "chantier.commands.next_advice:next_", HELP, BATCH_EPOCH)
    s.add_argument("cr", nargs="?", help="the CR: its Driver's next step")
    add_lease(s, how=LEASE)  # optional; checked, never renewed

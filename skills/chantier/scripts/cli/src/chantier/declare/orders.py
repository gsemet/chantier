"""The parser of the `orders` command(s); the handlers load when one runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH_EPOCH, Subparsers, add_command


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "order",
        "chantier.commands.orders:order",
        "the user's word, recorded at once; the Foreman does what needs its hands",
        BATCH_EPOCH,
    )
    s.add_argument(
        "kind",
        help="add [--release], after, drop, merged, note, rounds, slots, budget, qa, mode (series "
        "to stack); "
        "for the release CR: approve, grant, confirm; the Foreman: done <O-k>, merged "
        "--epoch, add --fix-for --epoch",
    )
    s.add_argument("cr", nargs="?", default="-", help="the CR, or the order id for `done`")
    s.add_argument(
        "--note",
        help="add: <folder>, or a release's fix file; after: the CR ids it waits "
        "for, comma separated, or - for none; note: the line; rounds, "
        "slots, budget: the number; qa: what to test; approve: the action; grant: "
        "releases=N fixes=on|off budget=N; confirm: the user's word to run the "
        "release procedure, once the other CRs are merged",
    )
    s.add_argument("--fix-for", help="add: the release CR this fix is for")
    s.add_argument(
        "--release",
        action="store_true",
        help="add: the folder is the batch's release CR, which waits for every other CR (refused "
        "once it has started)",
    )

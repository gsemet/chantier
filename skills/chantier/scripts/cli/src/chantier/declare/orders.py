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
        help="add [--release], after (--note replaces, --add/--remove change one), "
        "drop (--note trash|ready|P1..P4), merged, hold|unhold "
        "(a live CR, or a ready CR of a stack, out of the slots and the order, and back), note, "
        "rounds, slots, budget, qa, "
        "mode (any mode to any other), "
        "waive stack|<cr> [--follow-up] (the long gate; --note - withdraws); "
        "for the release CR: approve, grant, confirm; the Foreman: done <O-k>, merged "
        "--epoch, add --fix-for --epoch",
    )
    s.add_argument("cr", nargs="?", default="-", help="the CR, or the order id for `done`")
    s.add_argument(
        "--note",
        help="add: <folder>, or a release's fix file; drop: trash, P1..P4 or ready (the next "
        "batch, 3-ready), where the CR goes (the user's word; never a default); "
        "after: the CRs it waits for, replacing the list (ids, slugs or paths, comma separated), "
        "or - for none; note: the line; rounds, "
        "slots, budget: the number; mode: parallel, series or stack; qa: what to test; "
        "approve: the action; grant: releases=N fixes=on|off budget=N; "
        "confirm: the user's word to run the release procedure, once the other CRs are merged",
    )
    for flag, to in (("--add", "add to"), ("--remove", "take out of")):
        help_ = f"after: the CRs to {to} what it waits for, comma separated; the rest stays"
        s.add_argument(flag, help=help_)
    s.add_argument("--fix-for", help="add: the release CR this fix is for")
    s.add_argument(
        "--follow-up",
        help="waive <cr>: the backlog folder (1-inbox, 2-backlog/P*, 3-ready) of the CR that "
        "runs the long gate on main afterwards",
    )
    s.add_argument(
        "--release",
        action="store_true",
        help="add: the folder is the batch's release CR, which waits for every other CR (refused "
        "once it has started)",
    )

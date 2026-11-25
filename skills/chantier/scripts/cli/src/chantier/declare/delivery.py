"""The parser of the `delivery` command(s); the handlers load when one runs."""

from __future__ import annotations

import argparse

from chantier.commands.registry import (
    ALSO_LEASE,
    BATCH,
    LEASE_ALSO,
    Subparsers,
    add_command,
    add_lease,
)


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "verdict",
        "chantier.commands.next_lines:verdict",
        "the Verifier's verdict on the CR's worktree head: VERIFIED or \"NOT VERIFIED\"",
        BATCH,
        LEASE_ALSO,
    )
    s.add_argument("cr")
    s.add_argument("result", nargs="+", help="VERIFIED, or NOT VERIFIED (one argument or two)")
    add_lease(s, how=ALSO_LEASE)

    s = add_command(
        sub,
        "ship",
        "chantier.commands.next_lines:ship",
        "record the PR the Driver opened or updated, with its base and draft state read from the "
        "forge; say what is off; in a stack or series batch, refused (nothing recorded) for a CR "
        "whose branch does not hold the recorded head of the CR below it",
        BATCH,
    )
    s.add_argument("cr")
    s.add_argument("pr", help="the PR link")
    s.add_argument(
        "--conflict",
        action="store_true",
        help="the rebase this ship follows resolved a conflict (whoever resolved it): no pass and "
        "no verdict from before carries, here or later; the ship event records `conflict: true`",
    )
    add_lease(s, required=True)

    _push_command(sub)

    s = add_command(
        sub,
        "stack",
        "chantier.commands.delivery:stack",
        "the stack's order, as its driver set it",
        BATCH,
    )
    _stack_arguments(s)
    add_lease(s, required=True)


def _push_command(sub: Subparsers) -> None:
    """`push`: the CR's own branch, through the CLI."""
    s = add_command(
        sub,
        "push",
        "chantier.commands.next_lines:push",
        "push the CR's own recorded `chantier/*` branch from its worktree with `git push "
        "--force-with-lease`: chantier's own update of the CR's branch after a rebase, declared "
        "legitimate by this command, with the lease held; never another branch, never "
        "`--force`, never `--no-verify`, no forge call",
        BATCH,
    )
    s.add_argument("cr")
    s.add_argument(
        "--unit",
        metavar="stack|O-k",
        help="whose lease the push holds: none, the CR's own; `stack`, the stack's (a CR of a "
        "stack batch's chain); `O-k`, a QA order of this CR",
    )
    add_lease(s, required=True)


def _stack_arguments(s: argparse.ArgumentParser) -> None:
    s.add_argument(
        "crs",
        nargs="*",
        help="the stack's order, as its driver set it, bottom first; naming only some CRs "
        "puts them at the bottom, the others above in their order; "
        "with no CR, print the stack as it stands (writes nothing)",
    )
    s.add_argument(
        "--out-of-draft",
        action="store_true",
        help="record the named CRs' PRs as out of draft on the forge (after turning them ready); "
        "refused for a CR not handed back ready, for one with a draft under it and for one whose "
        "recorded head does not hold the recorded head of the CR below it",
    )
    s.add_argument(
        "--draft",
        action="store_true",
        help="record the named CRs' PRs as back to a draft on the forge",
    )

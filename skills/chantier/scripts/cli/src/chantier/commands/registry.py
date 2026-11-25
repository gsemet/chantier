"""How a command module declares itself: `add_command` and the options every command shares."""

from __future__ import annotations

import argparse
import importlib
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    Subparsers = argparse._SubParsersAction[argparse.ArgumentParser]
else:
    Subparsers = argparse._SubParsersAction
Handler = Callable[[argparse.Namespace], Any]

NO_BATCH = "no-batch"  # the command reads no batch
OWN_PROJECT = "own-project"  # no batch, and its own `--project` (`login`: repeatable)
BATCH = "batch"  # `--batch` picks the batch
BATCH_EPOCH = "batch-epoch"  # `--batch`, and the Foreman's `--epoch`


def lazy(path: str) -> Handler:
    """The handler named `module:function`, imported when the command runs, not at start-up."""

    def run(args: argparse.Namespace) -> Any:
        module, _, name = path.partition(":")
        handler: Handler = getattr(importlib.import_module(module), name)
        return handler(args)

    return run


ALSO_LEASE = (
    "accepted on this command too: a valid one renews, a stale one exits 3 (`claim lost`); "
    "without it nothing is checked"
)
IGNORED_LEASE = "accepted and ignored: `rules` names no unit"


def add_lease(
    s: argparse.ArgumentParser, required: bool = False, *, how: str | None = None
) -> None:
    """`--lease <n>`: the number `take` (or `order qa`) printed, on a Driver's command. `how`: the
    help of a command that accepts it only as a near miss (`ALSO_LEASE`, `IGNORED_LEASE`)."""
    s.add_argument(
        "--lease",
        type=int,
        metavar="N",
        help=how
        or (
            "the lease number `take` printed: "
            + ("required" if required else "optional")
            + " when the unit has a lease; a valid one renews it, a stale one exits 3 "
            "(`claim lost`)"
        ),
    )


LEASE_ALSO = ("`--lease N`, renewed when valid",)
LEASE_IGNORED = ("`--lease N`, ignored",)
EPOCH_FORM = "`--epoch N` before the command name"
PATH_FORMS = (
    "a path repeating the planning prefix (`projects/<name>/changes/1-inbox/<cr>`)",
    "a path from a shell inside the planning folder (`.`)",
    "the CR's short name",
)


def also_text(forms: list[str]) -> str | None:
    """A command's `--help` epilog: one line per near-miss form it accepts."""
    return "\n".join(["also accepted:", *(f"  {f}" for f in forms)]) if forms else None


def add_command(  # noqa: PLR0913, PLR0917 - the command's words
    sub: Subparsers, name: str, fn: str, help_: str, scope: str = BATCH, also: tuple[str, ...] = ()
) -> argparse.ArgumentParser:
    """Add one command: its handler (`module:function`), `--project` and `--profile` (accepted after
    the command too), and its scope."""
    forms = [*also, *([EPOCH_FORM] if scope == BATCH_EPOCH else [])]
    s: argparse.ArgumentParser = sub.add_parser(
        name,
        help=help_,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=also_text(forms),
    )
    s.set_defaults(fn=lazy(fn))
    if scope != OWN_PROJECT:
        s.add_argument("--project", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    s.add_argument("--profile", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    s.add_argument("--skill", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    if scope not in (NO_BATCH, OWN_PROJECT):
        s.add_argument(
            "--batch",
            help="batch number, 4 or batch-04 (default: $CHANTIER_BATCH, else the only running "
            "one)",
        )
    if scope == BATCH_EPOCH:
        s.add_argument(
            "--epoch",
            type=int,
            help=(
                "the steering session's number in the batch (Foreman n°<n>): missing on a "
                "steering command exits 2, stale exits 3"
            ),
        )
    return s

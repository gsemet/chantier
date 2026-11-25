"""The forms argparse would refuse that can mean only one thing, rewritten to the canonical form
before it parses: `phase <cr> "gate preflight"` (one quoted word holding the step and its detail)
and `--epoch N` before the command's name. Every other argv comes back unchanged. Light: it imports
no command and no model, so start-up time does not change."""

from __future__ import annotations

from chantier.core.phases import PHASES

# The commands that declare `--epoch` (`registry.BATCH_EPOCH`); a test keeps it equal to the
# parser's.
EPOCH_COMMANDS = (
    "access",
    "agents",
    "brief",
    "cancel",
    "foreman",
    "gate",
    "inbox",
    "judge",
    "next",
    "order",
    "park",
    "pause",
    "status",
    "take",
    "wait",
)
ROOT_VALUE_OPTIONS = ("--project", "--profile", "--skill")
VALUE_OPTIONS = (*ROOT_VALUE_OPTIONS, "--lease", "--batch")


def _epoch_before(argv: list[str]) -> tuple[int | None, list[int]]:
    """The command name's place, and the places of an `--epoch N` or `--epoch=N` before it. The
    command name is the first token that is not an option (nor a root option's value)."""
    at: list[int] = []
    i = 0
    while i < len(argv):
        t = argv[i]
        if t == "--epoch" and i + 1 < len(argv):
            at += [i, i + 1]
            i += 2
        elif t.startswith("--epoch="):
            at.append(i)
            i += 1
        elif t in ROOT_VALUE_OPTIONS:
            i += 2
        elif t.startswith("-"):
            i += 1
        else:
            return i, at
    return None, at


def _second_positional(argv: list[str], after: int) -> int | None:
    """The place of the second positional after the command's name, skipping options and the
    values of the ones that take one."""
    seen = 0
    i = after + 1
    while i < len(argv):
        t = argv[i]
        if t in VALUE_OPTIONS:
            i += 2
            continue
        if not t.startswith("-"):
            seen += 1
            if seen == 2:  # noqa: PLR2004 - the CR, then the step
                return i
        i += 1
    return None


def _phase(argv: list[str], name: int) -> list[str]:
    at = _second_positional(argv, name)
    if at is None:
        return argv
    first, space, rest = argv[at].partition(" ")
    if not space or first not in PHASES:
        return argv
    return [*argv[:at], first, *([rest] if rest.strip() else []), *argv[at + 1 :]]


def normalize(argv: list[str]) -> list[str]:
    """`argv` with the near-miss forms rewritten; any other argv, unchanged."""
    name, epoch = _epoch_before(argv)
    if name is None:
        return argv
    if epoch and argv[name] in EPOCH_COMMANDS:
        moved = [argv[i] for i in epoch]
        rest = [t for i, t in enumerate(argv) if i not in epoch]
        place = name - len(epoch) + 1
        argv = [*rest[:place], *moved, *rest[place:]]
        name -= len(epoch)
    if argv[name] == "phase":
        return _phase(argv, name)
    return argv

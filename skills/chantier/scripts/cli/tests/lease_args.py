"""The lease a Driver passes: the `chantier` fixture does so for the tests whose subject is another
rule (`run.bare` runs a command as typed, for the tests of the lease itself)."""

from __future__ import annotations

import re

from chantier.core.ids import normalize_cr

GUARDED = ("round", "handback", "ship", "push")


def _unit(argv: list[str]) -> str | None:
    """The unit a lease-guarded command works on, None for any other command."""
    cmd = argv[0] if argv else ""
    rest = [a for a in argv[1:] if not a.startswith("-")]
    if cmd == "push" and "--unit" in argv:
        return argv[argv.index("--unit") + 1]
    if cmd in GUARDED and rest:
        return normalize_cr(rest[0])
    if cmd == "release" and len(rest) > 1:
        return normalize_cr(rest[1])
    writes_stack = cmd == "stack" and (rest or "--out-of-draft" in argv or "--draft" in argv)
    if writes_stack or (cmd == "forge-stack" and rest and rest[0] != "show"):
        return "stack"
    return None


def with_lease(argv: list[str], held: dict[str, str]) -> list[str]:
    """`argv` with the lease `take` printed for the unit, when the command needs one and the
    test passed none."""
    if "--lease" in argv or "--epoch" in argv:
        return argv
    unit = _unit(argv)
    return [*argv, "--lease", held[unit]] if unit in held else argv


def learn(argv: list[str], lines: list[str], held: dict[str, str]) -> None:
    """Keep the lease numbers a command printed."""
    for line in lines:
        if m := re.match(r"took (\S+) .*, lease (\d+) until", line):
            held[m[1]] = m[2]
        elif m := re.match(r"\s*lease: stack (\d+) ", line):
            held["stack"] = m[1]
        elif argv[:2] == ["agents", "set"] and (m := re.match(r"lease (\d+) of (O-\d+): ", line)):
            held[m[2]] = m[1]

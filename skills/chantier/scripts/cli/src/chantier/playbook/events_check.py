"""The checks of the `events` block of a `chantier.yaml`: `wake_every`, how soon after its own
start a watcher may end (one wake per window), checked as `long_gate` is."""

from __future__ import annotations

import re
from collections.abc import Callable

from chantier.playbook.yaml_subset import Node, is_reset

Bad = Callable[[int, str], None]
KEY = "wake_every"
LEAST_S = 20  # the watcher's quiet: below it the limit changes nothing
_DURATION = re.compile(r"([0-9]+)(s|m|h)")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600}
_OWN = re.compile(r':\d+: (events: |"events" )')  # a problem of this block, in a layer's list


def seconds(text: str) -> int | None:
    """A duration `<whole number><s|m|h>` in seconds, at least `LEAST_S`, else None."""
    found = _DURATION.fullmatch(text)
    total = int(found[1]) * _UNIT_SECONDS[found[2]] if found else 0
    return total if total >= LEAST_S else None


def events_key(node: Node, kline: int, bad: Bad) -> dict[str, int]:
    """The `events` key: the least time a watcher runs."""
    if node.kind != "map" or not node.value:
        bad(kline, f'"events" holds its key: `{KEY}:`')
        return {}
    rec: dict[str, int] = {}
    for name, (line, value) in node.value.items():
        if name != KEY:
            bad(line, f'events: unknown key "{name}": one of {KEY}')
        elif is_reset(value):
            continue
        elif (got := seconds(value.value) if value.kind == "scalar" else None) is None:
            found = value.value if value.kind == "scalar" else ""
            bad(
                line,
                f'events: "{KEY}" is <whole number><s|m|h>, {LEAST_S}s or more, found "{found}"',
            )
        else:
            rec[KEY] = got
    return rec


def missing(tree: Node) -> list[str]:
    """What the shipped defaults must set under `events` and do not."""
    found = tree.value.get("events")
    if found is None or found[1].kind != "map" or KEY not in found[1].value:
        return [f'the shipped defaults lack "events.{KEY}": every release sets it']
    return []


def own_problem(message: str) -> bool:
    """Whether a problem (`<file>:<line>: <text>`) is one of the `events` block."""
    return _OWN.search(message) is not None

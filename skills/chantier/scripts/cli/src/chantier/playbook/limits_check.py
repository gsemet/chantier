"""The checks of the two limits a `chantier.yaml` may hold, `specifying.parallel` and
`batch.slots`: each key holds one whole number, checked as `long_gate` is."""

from __future__ import annotations

import re
from collections.abc import Callable

from chantier.playbook.yaml_subset import Node, is_reset

Bad = Callable[[int, str], None]
LIMIT_KEYS = ("specifying.parallel", "batch.slots")  # the dotted paths the board edits


def _limit(node: Node, kline: int, bad: Bad, where: tuple[str, str, int]) -> dict[str, int]:
    """A top-level key that holds one whole number, checked as `long_gate` is. `where`: the key,
    its one sub-key and the least value it takes."""
    key, sub, least = where
    if node.kind != "map" or not node.value:
        bad(kline, f'"{key}" holds its key: `{sub}:`')
        return {}
    rec: dict[str, int] = {}
    for name, (line, value) in node.value.items():
        if name != sub:
            bad(line, f'{key}: unknown key "{name}": one of {sub}')
        elif is_reset(value):
            continue
        elif (
            value.kind != "scalar"
            or not re.fullmatch(r"[0-9]+", value.value)
            or int(value.value) < least
        ):
            found = value.value if value.kind == "scalar" else ""
            bad(line, f'{key}: "{sub}" is a whole number, {least} or more, found "{found}"')
        else:
            rec[sub] = int(value.value)
    return rec


def specifying_key(node: Node, kline: int, bad: Bad) -> dict[str, int]:
    """The `specifying` key: how many CRs are specified at once on the project."""
    return _limit(node, kline, bad, ("specifying", "parallel", 1))


def batch_key(node: Node, kline: int, bad: Bad) -> dict[str, int]:
    """The `batch` key: how many slots a new batch gets."""
    return _limit(node, kline, bad, ("batch", "slots", 0))


def missing_limits(tree: Node) -> list[str]:
    """The limits the shipped defaults must set and do not (the other layers may leave them)."""
    out: list[str] = []
    for dotted in LIMIT_KEYS:
        key, sub = dotted.split(".")
        found = tree.value.get(key)
        if found is None or found[1].kind != "map" or sub not in found[1].value:
            out.append(f'the shipped defaults lack "{dotted}": every release sets it')
    return out

"""The check of the `board` key of a `chantier.yaml`: `host` holds the word `network`, `port` one
integer."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from chantier.playbook.yaml_subset import Node, is_reset

Bad = Callable[[int, str], None]
BOARD_KEYS = ("host", "port")
MAX_PORT = 65535
HOST_NOT_NETWORK = (
    'board: "host" is network (this machine\'s local network address, found at each start); '
    "a fixed address goes in --host, for one start"
)


def board_key(node: Node, kline: int, bad: Bad) -> dict[str, Any]:
    """The `board` key: where `chantier serve` listens. Both keys are optional."""
    rec: dict[str, Any] = {}
    if node.kind != "map" or not node.value:
        bad(kline, f'"board" holds its keys: `host:` and `port:` ({", ".join(BOARD_KEYS)})')
        return rec
    for key, (line, value) in node.value.items():
        if key not in BOARD_KEYS:
            bad(line, f'board: unknown key "{key}": one of {", ".join(BOARD_KEYS)}')
        elif is_reset(value):
            continue
        elif key == "host":
            if value.kind == "scalar" and value.value == "network":
                rec["host"] = value.value
            else:
                bad(line, HOST_NOT_NETWORK)
        elif value.kind != "scalar" or not value.value.strip() or re.search(r"\s", value.value):
            bad(line, 'board: "port" is one integer with no whitespace')
        elif not re.fullmatch(r"[0-9]+", value.value) or not 1 <= int(value.value) <= MAX_PORT:
            bad(line, f'board: "port" is an integer from 1 to 65535, found "{value.value}"')
        else:
            rec["port"] = int(value.value)
    return rec

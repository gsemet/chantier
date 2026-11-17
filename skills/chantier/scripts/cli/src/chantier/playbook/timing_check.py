"""The `hosts.<host>.timing` block of a `chantier.yaml` layer: the settings, the columns each
host has, what each column reads, and the checks of every value."""

from __future__ import annotations

import re
from collections.abc import Callable

from chantier.playbook.yaml_subset import Node, is_reset

Bad = Callable[[int, str], None]

TIMING_SETTINGS = ("steering_wake", "cache_ttl", "ci_reruns")
TIMING_COLUMNS = {"claude": ("subagent", "session"), "copilot": ("claude", "gpt")}
# what each column reads: a setting under a column that does not read it is refused
TIMING_READS = {
    ("claude", "session"): ("steering_wake", "cache_ttl"),
    ("claude", "subagent"): ("cache_ttl", "ci_reruns"),
    ("copilot", "claude"): TIMING_SETTINGS,
    ("copilot", "gpt"): TIMING_SETTINGS,
}
MAX_STEERING_WAKE_CLAUDE = 3600  # seconds: unproved above (hosts/claude-code.md)
_DURATION = re.compile(r"([0-9]+)(s|m|h)")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600}


def parse_duration(text: str) -> int | None:
    """A duration `<whole number><s|m|h>` in seconds, at least one minute, else None."""
    found = _DURATION.fullmatch(text)
    seconds = int(found[1]) * _UNIT_SECONDS[found[2]] if found else 0
    return seconds if seconds >= 60 else None  # noqa: PLR2004 - one minute


def _timing_value(host: str, key: str, where: str, at: tuple[int, Node], bad: Bad) -> None:
    """One timing setting's value, within the host's bounds; a reset is accepted."""
    line, node = at
    if is_reset(node):
        return
    found = node.value if node.kind == "scalar" else node.kind
    if key == "ci_reruns":
        if node.kind != "scalar" or not re.fullmatch(r"[0-9]+", node.value):
            bad(line, f'{where}: "ci_reruns" is a whole number, 0 or more, found "{found}"')
        return
    seconds = parse_duration(node.value) if node.kind == "scalar" else None
    if seconds is None:
        bad(
            line,
            f'{where}: "{key}" is a duration of 1 minute or more: <n>s, <n>m or <n>h, '
            f'found "{found}"',
        )
    elif host == "copilot" and seconds % 60:
        bad(line, f'{where}: "{key}" is whole minutes on Copilot (<n>m or <n>h): found "{found}"')
    elif host == "claude" and key == "steering_wake" and seconds > MAX_STEERING_WAKE_CLAUDE:
        bad(
            line,
            f'{where}: "steering_wake" is at most 60 minutes on Claude Code: found "{found}"',
        )


def check_timing(host: str, node: Node, kline: int, bad: Bad) -> None:
    """A host's `timing` block: the three settings (general values) and one block per column."""
    where = f"hosts.{host}.timing"
    columns = TIMING_COLUMNS[host]
    if node.kind != "map" or not node.value:
        bad(
            kline, f"{where}: holds settings and columns: {', '.join((*TIMING_SETTINGS, *columns))}"
        )
        return
    for key, (line, value) in node.value.items():
        if key in TIMING_SETTINGS:
            _timing_value(host, key, where, (line, value), bad)
        elif key not in columns:
            bad(
                line,
                f'host "{host}": timing: unknown key "{key}": '
                f"one of {', '.join((*TIMING_SETTINGS, *columns))}",
            )
        elif not is_reset(value):
            _timing_column(host, key, value, line, bad)


def _timing_column(host: str, column: str, node: Node, kline: int, bad: Bad) -> None:
    where = f"hosts.{host}.timing.{column}"
    if node.kind != "map" or not node.value:
        bad(kline, f"{where}: holds its settings: {', '.join(TIMING_READS[(host, column)])}")
        return
    for key, (line, value) in node.value.items():
        if key not in TIMING_SETTINGS:
            bad(line, f'{where}: unknown setting "{key}": one of {", ".join(TIMING_SETTINGS)}')
        elif key not in TIMING_READS[(host, column)]:
            readers = [c for c in TIMING_COLUMNS[host] if key in TIMING_READS[(host, c)]]
            bad(
                line,
                f'{where}: "{key}" is not read by the {column} column: set it under '
                f"{' or '.join(readers)}, or as the general value",
            )
        else:
            _timing_value(host, key, where, (line, value), bad)

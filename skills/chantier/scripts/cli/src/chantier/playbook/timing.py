"""The timing of each host: its settings resolved for every column from the layers of the
configuration (see `timing_check.py` for what a file may hold).

Each layer is read alone, strongest first, never merged: a stronger layer's general value beats a
weaker layer's column value, and within one layer the column's value beats the general one (so a
user's general `cache_ttl` gives its value to the Claude Code session column, above the shipped
`session: 1h`). The shipped defaults come last and no reset reaches them."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from chantier.core.repo import Repo
from chantier.playbook import layers
from chantier.playbook.timing_check import (
    TIMING_COLUMNS,
    TIMING_READS,
    TIMING_SETTINGS,
    parse_duration,
)
from chantier.playbook.yaml_subset import Node, is_reset


def _timing_block(tree: Node | None, host: str) -> dict[str, tuple[int, Node]]:
    node = tree
    for key in ("hosts", host, "timing"):
        if node is None or node.kind != "map" or key not in node.value:
            return {}
        node = node.value[key][1]
    return node.value if node is not None and node.kind == "map" else {}


def _timing_entry(setting: str, node: Node, label: str, src: str) -> dict[str, Any]:
    value = int(node.value) if setting == "ci_reruns" else parse_duration(node.value)
    return {"value": value, "layer": label, "src": src}


def _search(
    stack: list[tuple[str, str, Node | None]], host: str, column: str | None, setting: str
) -> dict[str, Any] | None:
    """One setting of one column (or the host's general value when `column` is None) in these
    layers, strongest first: a stronger layer's general value beats a weaker layer's column
    value; within one layer the column's value beats the general one. A plain `default` takes
    back what it names, as in `merge`: the column (or its setting), or the general value, of the
    weaker layers is no longer read."""
    column_dead = setting_dead = general_dead = False
    for label, src, tree in stack:
        block = _timing_block(tree, host)
        held = block[column][1] if column and column in block else None
        if held is not None and not column_dead:
            column_dead = is_reset(held)
            node = held.value.get(setting) if held.kind == "map" and not setting_dead else None
            if node is not None and not is_reset(node[1]):
                return _timing_entry(setting, node[1], label, src)
            setting_dead = setting_dead or node is not None
        if setting in block and not general_dead:
            if not is_reset(block[setting][1]):
                return _timing_entry(setting, block[setting][1], label, src)
            general_dead = True
    return None


def _timing_value(
    user: list[tuple[str, str, Node | None]],
    shipped: list[tuple[str, str, Node | None]],
    host: str,
    column: str | None,
    setting: str,
) -> dict[str, Any] | None:
    """The user layers decide; a reset leads to the shipped default, which no reset touches."""
    return _search(user, host, column, setting) or _search(shipped, host, column, setting)


def timing_from(user: list[layers.Layer], defaults: Node | None) -> dict[str, dict[str, Any]]:
    """The timing of every host from layers already read: for each host `general` (each setting's
    value that the host's general level gives) and `columns` (for each column, each setting it
    reads as `{value, layer, src}`, and None for one it does not read). Durations in seconds."""
    stack: list[tuple[str, str, Node | None]] = [
        (layer.label, layer.display, layer.tree) for layer in reversed(user)
    ]
    shipped: list[tuple[str, str, Node | None]] = [("defaults", layers.DEFAULTS_DISPLAY, defaults)]
    out: dict[str, dict[str, Any]] = {}
    for host, columns in TIMING_COLUMNS.items():
        out[host] = {
            "general": {s: _timing_value(stack, shipped, host, None, s) for s in TIMING_SETTINGS},
            "columns": {
                col: {
                    s: _timing_value(stack, shipped, host, col, s)
                    if s in TIMING_READS[(host, col)]
                    else None
                    for s in TIMING_SETTINGS
                }
                for col in columns
            },
        }
    return out


def load_timing(
    repo: Repo, roles_by_host: dict[str, list[str]], defaults: Path | None
) -> tuple[dict[str, dict[str, Any]] | None, list[str]]:
    """The timing of every host (see `timing_from`), from the user layers and the shipped
    defaults, each layer read and searched alone, strongest first (never merged: a stronger
    layer's general value beats a weaker layer's column value). With no user file the defaults
    answer alone; with no plugin (no defaults), None. The problems of any layer come back as
    the other keys' do."""
    defaults_tree, problems = layers.read_defaults(defaults, roles_by_host)
    user, found = layers.read_user(repo, roles_by_host)
    problems += found
    if problems or defaults_tree is None:
        return None, problems
    return timing_from(user, defaults_tree), []

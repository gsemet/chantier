"""The two limits of the project, resolved from the layers of the configuration:
`specifying.parallel` (how many CRs are specified at once) and `batch.slots` (the slots `open`
gives a batch).

Each layer is read alone, strongest first (repository, surface project, surface), then the shipped
defaults, the way `timing.py` resolves timing: a plain `default` in a user layer takes back the
weaker user layers' value, and the shipped value then answers. With no plugin (no defaults) a key
no user layer sets has no value: the CLI holds none of its own."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from chantier.core.repo import Repo
from chantier.playbook import layers
from chantier.playbook.limits_check import LIMIT_KEYS
from chantier.playbook.yaml_subset import Node, is_reset

RESET = "reset"


def held(tree: Node | None, key: str) -> int | str | None:
    """What a layer holds at a dotted key: its whole number, `"reset"` for a plain `default` at
    the key or above it, None when it holds nothing."""
    node = tree
    for part in key.split("."):
        if node is None or node.kind != "map" or part not in node.value:
            return None
        node = node.value[part][1]
        if is_reset(node):
            return RESET
    return int(node.value) if node is not None and node.kind == "scalar" else None


def _one(user: list[layers.Layer], defaults: Node | None, key: str) -> dict[str, Any]:
    """`{value, layer, src, layers}` for one key: `value` None when no layer sets it, `layers`
    the value each layer holds (None for none, `"reset"` for a reset)."""
    per: dict[str, int | str | None] = {"defaults": held(defaults, key)}
    per.update({layer.label: held(layer.tree, key) for layer in user})
    found: dict[str, Any] = {"value": None, "layer": None, "src": None, "layers": per}
    for layer in reversed(user):
        got = held(layer.tree, key)
        if got == RESET:
            break
        if got is not None:
            return {**found, "value": got, "layer": layer.label, "src": layer.display}
    shipped = held(defaults, key)
    if isinstance(shipped, int):
        return {**found, "value": shipped, "layer": "defaults", "src": layers.DEFAULTS_DISPLAY}
    return found


def limits_from(user: list[layers.Layer], defaults: Node | None) -> dict[str, dict[str, Any]]:
    """Both limits from layers already read (`user` weakest first)."""
    return {key: _one(user, defaults, key) for key in LIMIT_KEYS}


def load_limits(
    repo: Repo, roles_by_host: dict[str, list[str]], defaults: Path | None
) -> tuple[dict[str, dict[str, Any]] | None, list[str]]:
    """The limits (see `limits_from`), or the problems found in any layer, the shipped defaults
    included (a defaults file without a limit is one)."""
    defaults_tree, problems = layers.read_defaults(defaults, roles_by_host)
    user, found = layers.read_user(repo, roles_by_host)
    problems += found
    if problems:
        return None, problems
    return limits_from(user, defaults_tree), []

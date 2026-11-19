"""The `events` block of a `chantier.yaml`, resolved from the layers as the limits are:
strongest layer first, then the shipped defaults, a plain `default` taking the weaker layers'
value back. With no plugin, a key no user layer sets has no value."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from chantier.core.repo import Repo
from chantier.playbook import layers
from chantier.playbook.events_check import KEY, own_problem, seconds
from chantier.playbook.yaml_subset import Node, is_reset


def _held(tree: Node | None) -> str | None:
    """What a layer holds: the text of its value, `"reset"` for a reset, None for nothing."""
    node = tree.value.get("events") if tree is not None else None
    if node is None:
        return None
    if is_reset(node[1]):
        return "reset"
    got = node[1].value.get(KEY) if node[1].kind == "map" else None
    if got is None:
        return None
    return "reset" if is_reset(got[1]) else got[1].value


def load_wake_rules(
    repo: Repo, roles_by_host: dict[str, list[str]], defaults: Path | None
) -> dict[str, Any]:
    """`{text, seconds, layer, src, events_problems, other}`: the value (None for none), its
    layer, the problems of the `events` block in any layer, and the first other problem."""
    defaults_tree, dprob = layers.read_defaults(defaults, roles_by_host)
    user, uprob = layers.read_user(repo, roles_by_host, "events")
    _, every = layers.read_user(repo, roles_by_host)
    mine = [p for p in dict.fromkeys([*dprob, *uprob]) if own_problem(p)]
    other = next((p for p in [*dprob, *every] if not own_problem(p)), None)
    out: dict[str, Any] = {
        "text": None,
        "seconds": None,
        "layer": None,
        "src": None,
        "events_problems": mine,
        "other": other,
    }
    if mine:
        return out
    found = next(
        (
            (layer.label, layer.display, text)
            for layer in reversed(user)
            if (text := _held(layer.tree)) is not None
        ),
        None,
    )
    if found and found[2] != "reset":
        label, src, text = found
    else:  # no user layer sets it, or a plain `default` took the weaker layers' value back
        label, src, text = "defaults", layers.DEFAULTS_DISPLAY, _held(defaults_tree)
    if text and text != "reset" and (got := seconds(text)) is not None:
        out.update(text=text, seconds=got, layer=label, src=src)
    return out

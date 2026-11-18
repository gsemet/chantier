"""The Configuration page's Timing and Limits tabs as `edit.config_view` gives them."""

from __future__ import annotations

from typing import Any

from chantier.playbook import layers, limits, models, timing, timing_check
from chantier.playbook.lines import minutes
from chantier.playbook.yaml_subset import Node

TIMING_COLUMN_WORDS = {
    "subagent": "Subagent",
    "session": "Session",
    "claude": "Claude models",
    "gpt": "GPT models",
}


def timing_cell(setting: str, entry: dict[str, Any] | None) -> dict[str, Any]:
    """A cell of the Timing tab: the value that applies, the layer (and file) behind it and
    whether it is the shipped default, or `not_used`."""
    if entry is None:
        return {"not_used": True}
    value = entry["value"]
    return {
        "value": value,
        "text": str(value) if setting == "ci_reruns" else minutes(value),
        "layer": entry["layer"],
        "src": entry["src"],
        "default": entry["layer"] == "defaults",
    }


def timing_view(user: list[layers.Layer], defaults: Node | None) -> dict[str, Any] | None:
    """The timing of each host for the page: its columns, then for each setting its cell per
    column and the general value. None when the defaults are not readable."""
    if defaults is None:
        return None
    found = timing.timing_from(user, defaults)
    out: dict[str, Any] = {}
    for host, one in found.items():
        columns = list(one["columns"])
        out[host] = {
            "name": models.HOST_NAMES[host],
            "columns": [{"id": c, "name": TIMING_COLUMN_WORDS[c]} for c in columns],
            "settings": {
                s: {
                    "general": timing_cell(s, one["general"][s]),
                    "columns": {c: timing_cell(s, one["columns"][c][s]) for c in columns},
                }
                for s in timing_check.TIMING_SETTINGS
            },
        }
    return out


def limits_view(user: list[layers.Layer], defaults: Node | None) -> dict[str, Any]:
    """The Limits tab: for each limit its effective value (None when no layer sets it), the layer
    and file behind it, the value each layer holds and the code repository's file when it sets or
    resets the key (the page writes only the surface project's file)."""
    repository = next((layer for layer in user if layer.label == "repository"), None)
    out: dict[str, Any] = {}
    for key, found in limits.limits_from(user, defaults).items():
        held = limits.held(repository.tree, key) if repository else None
        out[key] = {
            "effective": found["value"],
            "layer": found["layer"],
            "src": found["src"],
            "default": found["layer"] == "defaults",
            "layers": found["layers"],
            "overridden_by": repository.display if repository and held is not None else None,
        }
    return out

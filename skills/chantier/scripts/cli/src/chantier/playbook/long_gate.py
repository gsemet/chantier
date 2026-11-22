"""The `long_gate` key for `chantier gate`, `playbook` and `validate`: `parallel` merged across
the layers, `commands` from the code repository's root layer only."""

from __future__ import annotations

from typing import NamedTuple

from chantier.core.repo import Repo
from chantier.playbook import config
from chantier.playbook.layers import _sink, merge, read_user


class LongGate(NamedTuple):
    """The `long_gate` key for `chantier gate` and `playbook`."""

    parallel: int  # merged across all layers
    commands: dict[str, str]  # the code repository's root layer only
    ignored: list[str]  # surface files holding a `long_gate.commands`, ignored for running
    problems: list[str]


def load_long_gate(repo: Repo) -> LongGate:
    """The `long_gate` key alone, for `chantier gate`: one, no command and no problem when there is
    none. `commands` come from the code repository's root layer only (`Repo.root`, the main
    checkout); the surface layers' are listed in `ignored`."""
    layers, problems = read_user(repo, {}, only="long_gate")
    if problems or not layers:
        return LongGate(1, {}, [], problems)
    found = config.typed(
        merge(layers).tree, _sink(problems, "the merged configuration"), only="long_gate"
    )
    commands: dict[str, str] = {}
    ignored: list[str] = []
    for layer in layers:
        held = config.gate_commands(
            layer.tree.value["long_gate"][1]
            if layer.tree and "long_gate" in layer.tree.value
            else None
        )
        if layer.label == "repository":
            commands = held
        elif held:
            ignored.append(layer.display)
    return LongGate(found.get("long_gate", 1), commands, ignored, problems)

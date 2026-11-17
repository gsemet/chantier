"""The escalation key of a role: the shipped default, the roles that carry one, the effective
map and the checks. Low level: it reads a merged tree and takes the judged roles as given."""

from __future__ import annotations

from typing import Any

from chantier.playbook import config
from chantier.playbook.models import HOST_NAMES, NAMED_AGENT_MODEL_AT_START, resolve
from chantier.playbook.yaml_subset import Node


def default_key(defaults: Node | None, host: str, role: str, key: str) -> str | None:
    """The identifier the defaults layer gives a role's `model` or `escalation`, resolved."""
    if defaults is None:
        return None
    node = defaults
    for step in ("hosts", host, "roles", role, key):
        if node.kind != "map" or step not in node.value:
            return None
        node = node.value[step][1]
    found, _ = resolve(host, node.value) if node.kind == "scalar" else (None, None)
    return found.id if found else None


def default_escalation(defaults: Node | None, host: str, role: str) -> str | None:
    """The escalation model the defaults layer gives a role on a host, resolved, or None."""
    return default_key(defaults, host, role, "escalation")


def carrying(defaults: Node | None, host: str) -> list[str]:
    """The roles whose shipped defaults carry an `escalation` on this host: the only roles a user
    layer may set one on (the CLI names no role)."""
    if defaults is None:
        return []
    node = defaults
    for step in ("hosts", host, "roles"):
        if node.kind != "map" or step not in node.value:
            return []
        node = node.value[step][1]
    return [
        role
        for role, (_, child) in node.value.items()
        if child.kind == "map" and "escalation" in child.value
    ]


def role_nodes(tree: Node, host: str) -> dict[str, Node]:
    node = tree
    for key in ("hosts", host, "roles"):
        if node.kind != "map" or key not in node.value:
            return {}
        node = node.value[key][1]
    return {role: child for role, (_, child) in node.value.items()}


def carry_problems(tree: Node, defaults: Node | None) -> list[str]:
    """The `escalation` keys the merged layers set on a role whose defaults carry none."""
    problems: list[str] = []
    for host in HOST_NAMES:
        for role, node in role_nodes(tree, host).items():
            if node.kind != "map" or "escalation" not in node.value:
                continue
            allowed = carrying(defaults, host)
            if role not in allowed:
                held = node.value["escalation"][1]
                problems.append(
                    f'{held.src}:{held.line}: role "{role}": "escalation" is set only on a role '
                    f"whose shipped defaults carry one: {', '.join(allowed) or '(none)'}"
                )
    return problems


def escalation_map(defaults: Node | None, judged: Any, host: str) -> dict[str, dict[str, Any]]:
    """The escalation of each role that has one on this host, from the shipped defaults then the
    user layers (a user value wins), `{role: {id, name, start, mode[, layer]}}`: `start` is the
    model's value on the host, `mode` how the escalated role starts (`named`, or `generic` on a
    host that cannot start a named agent with a model), `layer` the label of the user layer that
    set it (absent for the shipped default). A role that carries the user's own agent on a host
    that cannot start it with a model does not escalate there: it is absent."""
    out: dict[str, dict[str, Any]] = {}
    for role in carrying(defaults, host):
        rec = (judged.roles.get(role) if judged else None) or {}
        if not NAMED_AGENT_MODEL_AT_START[host] and "agent" in rec:
            continue
        if rec.get("escalation"):
            entry = dict(rec["escalation"])
            entry["layer"] = judged.nodes[role].value["escalation"][1].layer
        else:
            found, _ = resolve(host, str(default_escalation(defaults, host, role)))
            if found is None:
                continue
            entry = {"id": found.id, "name": found.name, "start": found.start}
        entry["mode"] = "named" if NAMED_AGENT_MODEL_AT_START[host] else "generic"
        out[role] = entry
    return out


def escalation_problems(
    role: str,
    rec: dict[str, Any],
    nodes: dict[str, Node],
    host: str,
    refusals: dict[str, str] | None,
) -> list[str]:
    """Judge a role's own `escalation` for this host and record its `mode`: `named`, or `generic`
    on a host that cannot start a named agent with a model. The user's own agent is never
    replaced by a generic one, so an escalation the user wrote on a role that carries that agent,
    on such a host, is refused (at its line, apart in `refusals` when given) and dropped."""
    if "escalation" not in rec:
        return []
    why = config.start_refusal(host, role, "escalation") if "agent" in rec else None
    if not why:
        rec["escalation"]["mode"] = "named" if NAMED_AGENT_MODEL_AT_START[host] else "generic"
        return []
    node = nodes[role].value["escalation"][1]
    line = f"{node.src}:{node.line}: {why}"
    del rec["escalation"]
    if refusals is None:
        return [line]
    refusals[f"{role}/escalation"] = line
    return []


def row(
    host: str, role: str, node: Node | None, defaults: Node | None, refusals: dict[str, str]
) -> dict[str, Any]:
    """A board row's escalation, shaped like its model: the one that applies and its layer, and
    `allowed`: whether the role's shipped defaults carry one (the only roles that may set it).
    On a host that cannot start the user's own agent with a model, a role that carries the
    user's agent does not escalate: `applies` is false, and a value the user wrote there shows
    its refusal."""
    if role not in carrying(defaults, host):
        return {"allowed": False}
    held = node.value["escalation"][1] if node is not None and "escalation" in node.value else None
    named = str(held.value) if held is not None else default_escalation(defaults, host, role)
    model = resolve(host, named)[0] if named else None
    generic = not NAMED_AGENT_MODEL_AT_START[host]
    return {
        "allowed": True,
        "effective": {"id": model.id, "name": model.name} if model else None,
        "layer": (held.layer if held is not None else "defaults") if model else None,
        "applies": not (generic and node is not None and "agent" in node.value),
        "start": "generic" if generic else "named",
        "refusal": refusals.get(f"{role}/escalation"),
    }

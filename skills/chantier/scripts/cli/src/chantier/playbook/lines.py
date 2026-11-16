"""The playbook, the team and the escalation as printed lines."""

from __future__ import annotations

from typing import Any

from chantier.playbook.config import FILE, default_agent
from chantier.playbook.models import ESCALATION, MODELS


def _model_text(model: dict[str, Any]) -> str:
    return f"{model['start']} ({model['id']}, {model['name']})"


def _labelled(text: str, labels: dict[str, str], key: str) -> str:
    return f"{text} [{labels[key]}]" if labels.get(key) else text


def _fields(
    rec: dict[str, Any],
    agent: str | None,
    unset_model: bool,
    labels: dict[str, str] | None = None,
    resets: dict[str, str] | None = None,
) -> str:
    """A role's keys, each followed by the layer that set it, or `reset in <layer>` when a layer
    took the value back. A value no user layer set has no label."""
    labels, resets = labels or {}, resets or {}

    def one(key: str, text: str) -> str:
        if key in resets and key not in rec:
            return f"{text} [reset in {resets[key]}]"
        return _labelled(text, labels, key)

    parts = [one("agent", f"agent={agent}")] if agent else []
    if rec.get("model"):
        parts.append(one("model", f"model={_model_text(rec['model'])}"))
    elif unset_model:
        parts.append(one("model", "model=(its file's)"))
    for key in ("skills", "tools"):
        if rec.get(key):
            parts.append(one(key, f"{key}={','.join(rec[key])}"))
        elif key in resets:
            parts.append(f"{key}=(none) [reset in {resets[key]}]")
    return " ".join(parts)


def _files(resolved: dict[str, Any]) -> str:
    """The user files read, weakest first; a record from before the layers has one `file`."""
    return ", ".join(resolved.get("files") or [resolved.get("file") or FILE])


def _layer_names(resolved: dict[str, Any], key: str) -> str:
    """The distinct layers behind the `prices` entries (or the one behind `ci`), in order."""
    if key == "prices":
        names = list(dict.fromkeys((resolved.get("price_layers") or {}).values()))
    else:
        names = [resolved.get("layers", {}).get("ci")]
    return ", ".join(n for n in names if n) or FILE  # a record from before the layers: the file


def playbook_lines(
    resolved: dict[str, Any] | None, host: str, roles: list[str], recorded: str | None = None
) -> list[str]:
    """The playbook, one line per role of the plugin, then one per need."""
    if resolved is None:
        head = "playbook: no chantier.yaml, the plugin's agents and models"
    elif recorded:
        head = f"playbook: {_files(resolved)} as {recorded} opened it, host {host}"
    else:
        head = f"playbook: {_files(resolved)}, valid, host {host}"
    lines = [head]
    configured = (resolved or {}).get("roles", {})
    layers = (resolved or {}).get("layers", {})
    for role in roles:
        rec = configured.get(role, {})
        lines.append(
            f"{role}: "
            + _fields(
                rec,
                rec.get("agent") or default_agent(host, role),
                True,
                {k: v for k, v in rec_labels(layers, role).items() if k in rec},
                layers.get("resets", {}).get(role),
            )
        )
    if resolved and resolved.get("prices"):
        names = _layer_names(resolved, "prices")
        lines.append(f"prices: {', '.join(resolved['prices'])} ({names}, above the built-in table)")
        if host == "copilot":
            lines.append("prices: not used on Copilot, whose records carry the price")
    lines += ci_lines(resolved)
    lines += [
        f"needs: {role}: "
        + "; ".join(
            _labelled(f"{k} {', '.join(rec[k])}", rec_labels(layers, role), k)
            for k in ("skills", "tools")
            if rec.get(k)
        )
        for role, rec in configured.items()
        if rec.get("skills") or rec.get("tools")
    ]
    return lines


def rec_labels(layers: dict[str, Any], role: str) -> dict[str, str]:
    """The label of the layer behind each key of a role, `{}` for a record from before them."""
    found: dict[str, str] = layers.get("roles", {}).get(role, {})
    return found


def escalate_line(host: str) -> str:
    """The escalation model of the host, one for every role, or that there is none."""
    entry = ESCALATION.get(host)
    found = next((m for m in MODELS[host] if m.id == entry), None) if entry else None
    return (
        f"escalate: {_model_text({'start': found.start, 'id': found.id, 'name': found.name})}"
        if found
        else "escalate: (none on this host)"
    )


def ci_lines(resolved: dict[str, Any] | None) -> list[str]:
    """The `ci:` line, only when `beside_gate` is on."""
    if not resolved or not (resolved.get("ci") or {}).get("beside_gate"):
        return []
    return [
        f"ci: beside the long gate ({_layer_names(resolved, 'ci')}): push at the approved round, "
        "run the long gate while CI runs"
    ]


def ci_source(resolved: dict[str, Any] | None) -> str:
    """Where `beside_gate` was set: the layer's label, or the file's name in an old record."""
    return _layer_names(resolved or {}, "ci")


def team_lines(resolved: dict[str, Any] | None) -> list[str]:
    """One `team:` line per configured role, with the keys set only, each with its layer."""
    if not resolved:
        return []
    layers = resolved.get("layers", {})
    return [
        f"team: {role} " + _fields(rec, rec.get("agent"), False, rec_labels(layers, role))
        for role, rec in resolved.get("roles", {}).items()
    ]

"""The playbook, the team and the escalation as printed lines."""

from __future__ import annotations

from typing import Any

from chantier.playbook.config import FILE, default_agent
from chantier.playbook.models import HOST_NAMES

GENERIC_AGENT = "(generic)"
GENERIC_TOOLS = "(the caller's, not restricted)"


def _model_text(model: dict[str, Any]) -> str:
    return f"{model['start']} ({model['id']}, {model['name']})"


def _escalation_text(entry: dict[str, Any]) -> str:
    """An escalation as printed: the model as `_model_text` gives it, and `(generic)` when the
    escalated role starts as a generic agent."""
    text = _model_text(entry)
    return f"{text} (generic)" if entry.get("mode") == "generic" else text


def _agent(rec: dict[str, Any]) -> str | None:
    """The agent a role's record names: the generic agent when the role starts generic."""
    return GENERIC_AGENT if rec.get("start") == "generic" else rec.get("agent")


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
    took the value back. A value no user layer set has no label. A role started generic prints
    `agent=(generic)` and, after its model, that its tools are the caller's."""
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
    if rec.get("start") == "generic":
        parts.append(f"tools={GENERIC_TOOLS}")
    for key in ("skills", "tools"):
        if rec.get(key):
            parts.append(one(key, f"{key}={','.join(rec[key])}"))
        elif key in resets:
            parts.append(f"{key}=(none) [reset in {resets[key]}]")
    return " ".join(parts)


def _escalated(fields: str, escalation: dict[str, Any] | None) -> str:
    """A role's fields followed by its `escalation` (an entry of the map, with its layer when a
    user layer set it)."""
    if not escalation:
        return fields
    text = f"escalation={_escalation_text(escalation)}"
    if escalation.get("layer"):
        text = f"{text} [{escalation['layer']}]"
    return f"{fields} {text}".strip()


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
    resolved: dict[str, Any] | None,
    host: str,
    roles: list[str],
    recorded: str | None = None,
    escalation: dict[str, Any] | None = None,
) -> list[str]:
    """The playbook, one line per role of the plugin, then one per need. A role with an
    `escalation` (the effective map) prints it after its model."""
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
            + _escalated(
                _fields(
                    rec,
                    _agent(rec) or default_agent(host, role),
                    True,
                    {k: v for k, v in rec_labels(layers, role).items() if k in rec},
                    layers.get("resets", {}).get(role),
                ),
                (escalation or {}).get(role),
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


def escalate_line(escalation: dict[str, Any] | None) -> str:
    """The escalation of each role that has one on the host, or that there is none."""
    if not escalation:
        return "escalate: (none on this host)"
    return "escalate: " + "; ".join(f"{r} {_escalation_text(e)}" for r, e in escalation.items())


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
        f"team: {role} "
        + _escalated(
            _fields(rec, _agent(rec), False, rec_labels(layers, role)),
            _team_escalation(rec, layers, role),
        )
        for role, rec in resolved.get("roles", {}).items()
    ]


def _team_escalation(
    rec: dict[str, Any], layers: dict[str, Any], role: str
) -> dict[str, Any] | None:
    """The escalation a user layer set on a configured role, with that layer's label."""
    held = rec.get("escalation")
    return {**held, "layer": rec_labels(layers, role).get("escalation")} if held else None


SECONDS_PER_MINUTE = 60
TIMING_WORDS = {
    "steering_wake": "steering wake",
    "cache_ttl": "cache TTL",
    "ci_reruns": "CI re-runs",
}


def minutes(seconds: int) -> str:
    """A duration as the CLI prints it: `30 min`, or `1 min 30 s` when not whole minutes."""
    whole, rest = divmod(seconds, SECONDS_PER_MINUTE)
    return f"{whole} min {rest} s" if rest else f"{whole} min"


def _timing_entry(setting: str, entry: dict[str, Any]) -> str:
    value = str(entry["value"]) if setting == "ci_reruns" else minutes(entry["value"])
    text = f"{TIMING_WORDS[setting]} {value}"
    return text if entry["layer"] == "defaults" else f"{text} [{entry['layer']}]"


def _timing_rows(timing: dict[str, Any], host: str) -> list[tuple[str, dict[str, Any]]]:
    """Each printed row of a host: its name and the settings it reads, in a fixed order. A
    Copilot host also has `other models`: the general values."""
    name = HOST_NAMES[host]
    rows: list[tuple[str, dict[str, Any]]] = []
    for column, settings in timing["columns"].items():
        label = f"{column} models" if host == "copilot" else column
        rows.append((f"{name} {label}", {s: e for s, e in settings.items() if e is not None}))
    if host == "copilot":
        rows.append((f"{name} other models", {s: e for s, e in timing["general"].items() if e}))
    return rows


def timing_lines(timing: dict[str, Any] | None, host: str) -> list[str]:
    """One `timing:` line per column of the host, with the settings that column reads, each
    followed by the layer that set it (none for a shipped default)."""
    if not timing:
        return []
    return [
        f"timing: {name}: " + ", ".join(_timing_entry(s, e) for s, e in settings.items())
        for name, settings in _timing_rows(timing, host)
    ]


def timing_warnings(timing: dict[str, Any] | None, host: str) -> list[str]:
    """One line for each column whose steering wake is longer than its cache TTL."""
    if not timing:
        return []
    out = []
    for name, settings in _timing_rows(timing, host):
        wake, ttl = settings.get("steering_wake"), settings.get("cache_ttl")
        if wake and ttl and wake["value"] > ttl["value"]:
            out.append(
                f"timing: {name}: steering wake {minutes(wake['value'])} is above the cache TTL "
                f"{minutes(ttl['value'])}: each wake starts cold"
            )
    return out


def timing_text(timing: dict[str, Any] | None, host: str) -> str:
    """The timing lines on one line, for the brief."""
    return "; ".join(line.removeprefix("timing: ") for line in timing_lines(timing, host))

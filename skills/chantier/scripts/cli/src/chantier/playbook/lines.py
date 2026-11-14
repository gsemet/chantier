"""The playbook, the team and the escalation as printed lines."""

from __future__ import annotations

from typing import Any

from chantier.playbook.config import FILE, default_agent
from chantier.playbook.models import ESCALATION, MODELS


def _model_text(model: dict[str, Any]) -> str:
    return f"{model['start']} ({model['id']}, {model['name']})"


def _fields(rec: dict[str, Any], agent: str | None, unset_model: bool) -> str:
    parts = [f"agent={agent}"] if agent else []
    if rec.get("model"):
        parts.append(f"model={_model_text(rec['model'])}")
    elif unset_model:
        parts.append("model=(its file's)")
    return " ".join(parts + [f"{k}={','.join(rec[k])}" for k in ("skills", "tools") if rec.get(k)])


def playbook_lines(
    resolved: dict[str, Any] | None, host: str, roles: list[str], recorded: str | None = None
) -> list[str]:
    """The playbook, one line per role of the plugin, then one per need."""
    if resolved is None:
        head = "playbook: no chantier.yaml, the plugin's agents and models"
    elif recorded:
        head = f"playbook: {FILE} as {recorded} opened it, host {host}"
    else:
        head = f"playbook: {FILE}, valid, host {host}"
    lines = [head]
    configured = (resolved or {}).get("roles", {})
    for role in roles:
        rec = configured.get(role, {})
        lines.append(
            f"{role}: " + _fields(rec, rec.get("agent") or default_agent(host, role), True)
        )
    if resolved and resolved.get("prices"):
        lines.append(f"prices: {', '.join(resolved['prices'])} ({FILE}, above the built-in table)")
        if host == "copilot":
            lines.append("prices: not used on Copilot, whose records carry the price")
    lines += ci_lines(resolved)
    lines += [
        f"needs: {role}: "
        + "; ".join(f"{k} {', '.join(rec[k])}" for k in ("skills", "tools") if rec.get(k))
        for role, rec in configured.items()
        if rec.get("skills") or rec.get("tools")
    ]
    return lines


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
        f"ci: beside the long gate ({FILE}): push at the approved round, "
        "run the long gate while CI runs"
    ]


def team_lines(resolved: dict[str, Any] | None) -> list[str]:
    """One `team:` line per configured role, with the keys set only."""
    if not resolved:
        return []
    return [
        f"team: {role} " + _fields(rec, rec.get("agent"), False)
        for role, rec in resolved.get("roles", {}).items()
    ]

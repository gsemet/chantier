"""The models each role can run and how a name resolves to one."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Model:
    id: str  # the exact identifier the host's agent files name
    name: str  # the display name
    start: str  # the value a start of an agent takes on this host


# Seeded from the plugin's agent files (a test checks they cannot drift). A new role model reaches
# the table by a release; a new model's price does not need one: a project sets it under `prices:`
# in `chantier.yaml`, above the built-in `costs.PRICE`.
MODELS = {
    "claude": (
        Model("claude-opus-5-5", "Claude Opus 5.5", "opus"),
        Model("claude-sonnet-5-5", "Claude Sonnet 5.5", "sonnet"),
        Model("claude-haiku-5-5", "Claude Haiku 5.5", "haiku"),
    ),
    "copilot": (
        Model("claude-opus-5.5", "Claude Opus 5.5", ""),
        Model("claude-sonnet-5.5", "Claude Sonnet 5.5", ""),
        Model("gpt-5.6-luna", "GPT-5.6 Luna", ""),
        Model("gpt-6.1-sol", "GPT-6.1 Sol", ""),
    ),
}


# Whether a start of an agent takes a model on this host: only what the host's reference marks
# proved (hosts/claude-code.md, hosts/copilot.md, row "Models").
SETS_MODEL_AT_START = {"claude": True, "copilot": False}


# The model an escalated task starts on (concepts.md, "Escalation"): one per host, the same for
# every role, kept next to MODELS so a release changes both. None where a start sets no model.
ESCALATION = {"claude": "claude-opus-5-5", "copilot": None}


def normalise(name: str) -> str:
    """Lower case; every run of characters other than letters and digits becomes one `-`."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _shown(models) -> str:
    return ", ".join(f"{m.id} ({m.name})" for m in models)


def resolve(host: str, name: str) -> tuple[Model | None, str | None]:
    """One model of the host's table, or the reason there is none."""
    wanted = normalise(name)
    models = MODELS[host]
    if not re.search("[a-z]", wanted):
        return None, f'model "{name}": name the model, not only its version'
    found = [m for m in models if wanted in (normalise(m.id), normalise(m.name))]
    if not found:
        parts = wanted.split("-")
        found = [m for m in models if _contains(normalise(m.id).split("-"), parts)]
    if len(found) == 1:
        return found[0], None
    if not found:
        return None, f'model "{name}" is unknown on {HOST_NAMES[host]}; known: {_shown(models)}'
    return None, f'model "{name}" is ambiguous on {HOST_NAMES[host]}: it matches {_shown(found)}'


def _contains(parts: list[str], run: list[str]) -> bool:
    """`run` is a contiguous run of whole parts of `parts`."""
    return any(parts[i : i + len(run)] == run for i in range(len(parts) - len(run) + 1))


HOST_NAMES = {"claude": "Claude Code", "copilot": "Copilot"}

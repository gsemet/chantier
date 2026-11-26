"""The models each role can run and how a name resolves to one."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from chantier.playbook.copilot_catalog import CATALOG_FILE, normalise


@dataclass(frozen=True)
class Model:
    id: str  # the exact identifier the host's agent files name
    name: str  # the display name
    start: str  # the value a start of an agent takes on this host


def copilot_catalog() -> list[dict[str, Any]]:
    """The Copilot models of `copilot-models.json`, with their status, clients and plans."""
    try:
        text = CATALOG_FILE.read_text(encoding="utf-8")
        models: list[dict[str, Any]] = json.loads(text)["models"]
    except (OSError, ValueError, KeyError) as error:
        message = f"{CATALOG_FILE}: the Copilot model catalog is unreadable: {error}"
        raise ImportError(message) from error
    return models


# Where each host's list comes from. Each role's default model is in
# `config/chantier.defaults.yml`, kept equal to the agent files by a test. Claude's list: by hand
# (a test checks the agent files cannot drift from it); a new role model reaches the table by a
# release, and a new model's price does not need one: a project sets it under `prices:` in
# `chantier.yaml`, above the built-in `costs.PRICE`. Copilot's: `copilot-models.json`, built by
# `just copilot-models` from GitHub's tables (`github/docs`, `data/tables/copilot/`) and the
# Copilot CLI reference's "Supported models", never edited by hand. An identifier with
# `in_cli_reference: false` there is derived by the rule, unproved until the runtime's
# `listModels()`.
MODELS = {
    "claude": (
        Model("claude-opus-5-5", "Claude Opus 5.5", "opus"),
        Model("claude-sonnet-5-5", "Claude Sonnet 5.5", "sonnet"),
        Model("claude-haiku-5-5", "Claude Haiku 5.5", "haiku"),
    ),
    "copilot": tuple(Model(m["id"], m["name"], m["id"]) for m in copilot_catalog()),
}


# Whether this host starts a named agent with a model given at the start, so that model runs and
# the agent keeps its file's tools: only what the host's reference marks proved
# (the host row `model-at-start`, references/hosts/*.json). A host added later
# declares its own value. Copilot's turns True once the eval's probe (evals/copilot/RUNBOOK.md,
# "Models") shows a named agent ran the requested model, together with the removal of
# `model-policy: required` from the agent files the proof covers. It is the one switch.
NAMED_AGENT_MODEL_AT_START = {"claude": True, "copilot": False}


def _shown(models: Iterable[Model]) -> str:
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

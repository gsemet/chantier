"""The Copilot model catalog, built from the copy of GitHub's tables (`copilot_tables/`).

It reads local files only: no network. `scripts/copilot_models.py` (`just copilot-models`) is what
copies the tables and writes `copilot-models.json`; nothing else writes it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

TABLES = Path(__file__).with_name("copilot_tables")
CATALOG_FILE = Path(__file__).with_name("copilot-models.json")

CLIENTS = "model-supported-clients.yml"
AUTO = "auto-model-selection.yml"
STATUS = "model-release-status.yml"
PLANS = "model-supported-plans.yml"
CLI_REFERENCE = "cli-supported-models.md"
PLAN_KEYS = ("pro", "pro_plus", "max", "business", "enterprise")

_FOOTNOTE = re.compile(r"\[\^[^\]]*\]")
_PREVIEW = re.compile(r"\(preview\)", re.IGNORECASE)
_CLI_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|", re.MULTILINE)

Model = dict[str, Any]


def normalise(name: str) -> str:
    """Lower case; every run of characters other than letters and digits becomes one `-`."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def display_name(name: str) -> str:
    """The name without its footnote markers and `(preview)`; case and spaces kept."""
    return " ".join(_PREVIEW.sub("", _FOOTNOTE.sub("", name)).split())


def identifier(name: str) -> str:
    """The identifier a Copilot call takes, by copilot-session-usage's rule."""
    return display_name(name).lower().replace(" ", "-")


def _rows(path: Path) -> list[dict[str, Any]]:
    from ruamel.yaml import YAML  # banned at module level

    data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    return [row for row in data or [] if isinstance(row, dict) and "name" in row]


def _by_id(path: Path) -> dict[str, dict[str, Any]]:
    table: dict[str, dict[str, Any]] = {}
    for row in _rows(path):
        table[identifier(str(row["name"]))] = {**row, "name": display_name(str(row["name"]))}
    return table


def cli_reference_ids(path: Path) -> list[str]:
    """The identifiers of the CLI reference's "Supported models" table."""
    ids = _CLI_ROW.findall(path.read_text(encoding="utf-8"))
    if not ids:
        raise ValueError(f"{path}: no model row in the Supported models table")
    return ids


def _tri(values: list[Any]) -> bool | None:
    named = [v for v in values if isinstance(v, bool)]
    return any(named) if named else None


def _admitted(clients: dict[str, Any], auto: dict[str, Any], reference: list[str]) -> list[str]:
    ids = {i for i, row in clients.items() if row.get("cli") is True}
    ids |= {i for i, row in auto.items() if row.get("cli") is True or row.get("app") is True}
    return sorted(ids | set(reference))


def build(tables: Path = TABLES) -> dict[str, Any]:
    """`{"models": [...], "differences": [...]}` from the copied tables alone."""
    clients, auto = _by_id(tables / CLIENTS), _by_id(tables / AUTO)
    status, plans = _by_id(tables / STATUS), _by_id(tables / PLANS)
    reference = cli_reference_ids(tables / CLI_REFERENCE)
    files = ((CLIENTS, clients), (AUTO, auto), (STATUS, status), (PLANS, plans))
    models: list[Model] = []
    for ident in _admitted(clients, auto, reference):
        rows = [row for _, table in files if (row := table.get(ident))]
        name = (status.get(ident) or next(iter(rows), {})).get("name", ident)
        plan = plans.get(ident)
        models.append(
            {
                "id": ident,
                "name": name,
                "release_status": status.get(ident, {}).get("release_status"),
                "cli": _tri([clients.get(ident, {}).get("cli"), auto.get(ident, {}).get("cli")]),
                "app": _tri([auto.get(ident, {}).get("app")]),
                "plans": {k: plan.get(k) for k in PLAN_KEYS} if plan else None,
                "in_cli_reference": ident in reference,
                "sources": [f for f, table in files if ident in table]
                + ([CLI_REFERENCE] if ident in reference else []),
            }
        )
    named = set(clients) | set(auto) | set(status) | set(plans)
    return {"models": models, "differences": _differences(models, clients, auto, named)}


def _differences(
    models: list[Model],
    clients: dict[str, Any],
    auto: dict[str, Any],
    named: set[str],
) -> list[str]:
    lines: list[str] = []
    for m in models:
        i = m["id"]
        if not m["in_cli_reference"]:
            lines.append(f"{i}: in the tables, not in the CLI reference's Supported models")
        if i not in named:
            lines.append(f"{i}: in the CLI reference, named by no table")
        if i in auto and i not in clients:
            lines.append(
                f"{i}: absent from {CLIENTS}, cli {auto[i].get('cli')} and app "
                f"{auto[i].get('app')} in {AUTO}"
            )
        elif i in auto and clients[i].get("cli") != auto[i].get("cli"):
            lines.append(f"{i}: cli differs between {CLIENTS} and {AUTO}")
        if m["release_status"] is None and i in named:
            lines.append(f"{i}: no release status in {STATUS}")
        if m["plans"] is None and i in named:
            lines.append(f"{i}: no plans row in {PLANS}")
    lines.extend(_twins(models))
    return lines


def _twins(models: list[Model]) -> list[str]:
    keys: dict[str, list[str]] = {}
    for m in models:
        keys.setdefault(normalise(m["id"]), []).append(m["id"])
    return [
        f"{' and '.join(ids)}: share the normalise key {key}; nothing is merged"
        for key, ids in keys.items()
        if len(ids) > 1
    ]


def document(source: dict[str, Any], tables: Path = TABLES) -> dict[str, Any]:
    """The content of `copilot-models.json`."""
    return {"schema": 1, "source": source, **build(tables)}


def dump(doc: dict[str, Any]) -> str:
    """The file's text: two-space indent, LF, one final newline."""
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


_AGENT_MODEL = re.compile(r"^model:\s*\[(.+?),\s*([^,\]]+)\]\s*$", re.MULTILINE)


def agent_file_differences(models: list[Model], agents: Path) -> list[str]:
    """Where a Copilot agent file's `model: [name, id]` and the catalog disagree."""
    by_id = {m["id"]: m for m in models}
    lines: list[str] = []
    for path in sorted(agents.glob("*.agent.md")):
        found = _AGENT_MODEL.search(path.read_text(encoding="utf-8"))
        if not found:
            continue
        name, ident = found.group(1).strip(), found.group(2).strip()
        where = f"{agents.parent.name}/{agents.name}/{path.name}"
        if ident not in by_id:
            lines.append(
                f"{ident}: named by {where}, not listed by GitHub; the agent file must change"
            )
        elif by_id[ident]["name"] != name:
            lines.append(
                f"{ident}: {where} names it {name!r}, the catalog {by_id[ident]['name']!r}"
            )
    return lines

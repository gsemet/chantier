"""The configuration as the board's Configuration page shows and edits it, role-free: `config_view`
reads the layers (`layers.py`) and says, for each host and each role, the value of `agent` and
`model` in each layer, the one that applies, the layer behind it, how the role starts and whether
the code repository's file overrides what the page writes; `edit_surface_file` changes each
role's `agent` and `model` in the planning surface's `projects/<name>/chantier.yaml` after the same
reading and checks, and writes that one file, keeping its other keys and its comments."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chantier.core.errors import EXIT_CONFLICT, EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.files import retry, write_bytes
from chantier.core.repo import Repo
from chantier.lifecycle.stages import changes_lock
from chantier.playbook import config, edit_text, layers, models, timing, timing_check
from chantier.playbook.lines import GENERIC_AGENT, minutes
from chantier.playbook.yaml_subset import Node, is_reset
from chantier.plugin_files import HOSTS, plugin_role_descriptions, plugin_roles, plugin_root

KEYS = ("agent", "model")
PROJECT_LABEL = "surface project"
LABELS = ("defaults", "surface", PROJECT_LABEL, "repository")
READ_ONLY = (
    "the configuration is read-only with no planning surface: edit chantier.yaml by hand "
    "(the board writes only a planning surface's file)"
)
DEFAULT_TEXT = (
    'no agent or model is named "default": to take the value back, choose "inherited" '
    "(the key is removed from the file)"
)
TOOLS_FILE = "the agent file's"
TOOLS_CALLER = "the caller's, not restricted"


def _roles_by_host() -> dict[str, list[str]]:
    return {h: plugin_roles(h) for h in HOSTS}


def _defaults_path() -> Path | None:
    root = plugin_root()
    return root / "config" / "chantier.defaults.yml" if root else None


def _sha(data: bytes | None) -> str | None:
    return hashlib.sha256(data).hexdigest() if data is not None else None


@dataclass
class Target:
    """The file the page writes: the project's folder's existing one, else `chantier.yaml`."""

    path: Path
    shown: str
    both: str | None  # the line of Q1's refusal when both names are present


def _target(repo: Repo) -> Target:
    folder = repo.project_folder
    found = [folder / n for n in config.FILES if (folder / n).is_file()]
    path = found[0] if found else folder / config.FILE
    both = None
    if len(found) > 1:
        both = f"{' and '.join(layers.display(repo, p) for p in found)} are both present: keep one"
    return Target(path, layers.display(repo, path), both)


def _read_bytes(path: Path) -> bytes | None:
    return retry(path.read_bytes) if path.is_file() else None


# --- reading ------------------------------------------------------------------------------------


def _leaf(tree: Node | None, path: tuple[str, ...]) -> str | None:
    """What a layer holds at a path: its text, `"reset"` for a plain `default`, `~` or `null` at
    the leaf or above it, None when it holds nothing."""
    node = tree
    for key in path:
        if node is None or node.kind != "map" or key not in node.value:
            return None
        node = node.value[key][1]
        if is_reset(node):
            return "reset"
    return str(node.value) if node is not None and node.kind == "scalar" else None


def _by_layer(
    defaults: Node | None, user: list[layers.Layer], path: tuple[str, ...]
) -> dict[str, str | None]:
    held = {layer.label: layer.tree for layer in user}
    return {
        label: _leaf(defaults if label == "defaults" else held.get(label), path) for label in LABELS
    }


def _model_entry(host: str, text: str) -> dict[str, str] | None:
    found, _ = models.resolve(host, text)
    return {"id": found.id, "name": found.name} if found else None


def _effective_model(
    host: str, role: str, node: Node | None, defaults: Node | None
) -> tuple[dict[str, str] | None, str | None]:
    if node is not None and "model" in node.value:
        held = node.value["model"][1]
        return _model_entry(host, str(held.value)), held.layer
    named = layers.default_model(defaults, host, role)
    return (_model_entry(host, named) if named else None), ("defaults" if named else None)


def _effective_agent(host: str, role: str, node: Node | None, start: str) -> tuple[str, str | None]:
    if start == "generic":
        return GENERIC_AGENT, None
    if node is not None and "agent" in node.value:
        held = node.value["agent"][1]
        return str(held.value), held.layer
    return config.default_agent(host, role), "defaults"


def _overridden(user: list[layers.Layer], host: str, role: str) -> tuple[str | None, list[str]]:
    """The code repository's file, when it sets or resets a key the page writes for this row."""
    repository = next((layer for layer in user if layer.label == "repository"), None)
    if repository is None:
        return None, []
    keys = [
        k for k in KEYS if _leaf(repository.tree, ("hosts", host, "roles", role, k)) is not None
    ]
    return (repository.display if keys else None), keys


def _row(
    host: str,
    role: str,
    user: list[layers.Layer],
    defaults: Node | None,
    judged: layers.Judged,
) -> dict[str, Any]:
    node = judged.nodes.get(role)
    refusal = judged.refusals.get(role)
    rec = judged.roles.get(role) or {}
    start = "refused" if refusal else str(rec.get("start", "plugin"))
    agent, agent_layer = _effective_agent(host, role, node, start)
    model, model_layer = _effective_model(host, role, node, defaults)
    where, keys = _overridden(user, host, role)
    return {
        "role": role,
        "agent": {
            "layers": _by_layer(defaults, user, ("hosts", host, "roles", role, "agent")),
            "effective": agent,
            "layer": agent_layer,
        },
        "model": {
            "layers": _by_layer(defaults, user, ("hosts", host, "roles", role, "model")),
            "effective": model,
            "layer": model_layer,
        },
        "overridden_by": where,
        "overridden_keys": keys,
        "start": start,
        "refusal": refusal,
        "tools": TOOLS_CALLER if start == "generic" else TOOLS_FILE,
    }


def _catalog(host: str) -> list[dict[str, Any]]:
    """The host's models; on Copilot each carries its `plans` as `copilot-models.json` gives them
    (None when the entry is not there), read again at each call."""
    if host != "copilot":
        return [{"id": m.id, "name": m.name} for m in models.MODELS[host]]
    plans = {m["id"]: m.get("plans") for m in models.copilot_catalog()}
    return [{"id": m.id, "name": m.name, "plans": plans.get(m.id)} for m in models.MODELS[host]]


def _host(
    host: str,
    roles_by_host: dict[str, list[str]],
    user: list[layers.Layer],
    defaults: Node | None,
    problems: list[str],
) -> tuple[dict[str, Any], layers.Judged]:
    judged = layers.judge(user, host, roles_by_host, defaults, tolerate=True)
    problems += [p for p in judged.problems if p not in problems]
    descriptions = plugin_role_descriptions(host)
    return {
        "name": models.HOST_NAMES[host],
        "named_agent_model_at_start": models.NAMED_AGENT_MODEL_AT_START[host],
        "catalog": _catalog(host),
        "roles": [
            {**_row(host, r, user, defaults, judged), "description": descriptions.get(r)}
            for r in roles_by_host[host]
        ],
    }, judged


def _flat(node: Node, path: tuple[str, ...]) -> list[dict[str, str]]:
    """The merged tree's leaves, each with its layer, but each role's `agent` and `model`."""
    if node.kind == "map":
        return [
            leaf for key, (_, child) in node.value.items() for leaf in _flat(child, (*path, key))
        ]
    if path[:1] == ("hosts",) and path[-1] in KEYS:
        return []
    if path[:1] == ("hosts",) and path[2:3] == ("timing",):
        return []  # the Timing tab shows it
    value = ", ".join(n.value for n in node.value) if node.kind == "list" else node.value
    return [{"path": ".".join(path), "value": str(value), "layer": node.layer}] if value else []


TIMING_COLUMN_WORDS = {
    "subagent": "Subagent",
    "session": "Session",
    "claude": "Claude models",
    "gpt": "GPT models",
}


def _timing_cell(setting: str, entry: dict[str, Any] | None) -> dict[str, Any]:
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


def _timing_view(user: list[layers.Layer], defaults: Node | None) -> dict[str, Any] | None:
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
                    "general": _timing_cell(s, one["general"][s]),
                    "columns": {c: _timing_cell(s, one["columns"][c][s]) for c in columns},
                }
                for s in timing_check.TIMING_SETTINGS
            },
        }
    return out


def _batch(repo: Repo) -> str | None:
    try:
        found = repo.batch_ids()
    except (ChantierError, OSError, ValueError):
        return None
    return found[0] if found else None


def _view(
    repo: Repo,
    user: list[layers.Layer],
    defaults: Node | None,
    problems: list[str],
    held: tuple[Target | None, bytes | None],
) -> dict[str, Any]:
    target, data = held  # the file the page writes (None with no surface) and its bytes
    roles_by_host = _roles_by_host()
    hosts: dict[str, Any] = {}
    last: layers.Judged | None = None
    for host in HOSTS:
        hosts[host], last = _host(host, roles_by_host, user, defaults, problems)
    assert last is not None
    return {
        "hosts": hosts,
        "timing": _timing_view(user, defaults),
        "others": _flat(last.merged.tree, ()),
        "files": [
            {"label": "defaults", "path": layers.DEFAULTS_DISPLAY},
            *({"label": layer.label, "path": layer.display} for layer in user),
        ],
        "problems": problems,
        "writable": target is not None,
        "file": target.shown if target else None,
        "sha256": _sha(data),
        "batch": _batch(repo),
    }


def _writable(repo: Repo) -> Target | None:
    return _target(repo) if repo.external and repo.project_folder.is_dir() else None


def config_view(repo: Repo) -> dict[str, Any]:
    """The Configuration page's data: see the module's text."""
    roles_by_host = _roles_by_host()
    defaults, problems = layers.read_defaults(_defaults_path(), roles_by_host)
    user, found = layers.read_user(repo, roles_by_host)
    target = _writable(repo)
    data = _read_bytes(target.path) if target else None
    return _view(repo, user, defaults, [*problems, *found], (target, data))


# --- writing ------------------------------------------------------------------------------------


def _one(one: object) -> None:
    if not isinstance(one, dict):
        raise ChantierError("each change is {host, role, key, value}", EXIT_USAGE)
    if one.get("host") not in HOSTS:
        raise ChantierError(f"'host' is one of {', '.join(HOSTS)}", EXIT_USAGE)
    if one.get("key") not in KEYS:
        raise ChantierError(f"'key' is one of {', '.join(KEYS)}", EXIT_USAGE)
    if not isinstance(one.get("role"), str) or not one["role"]:
        raise ChantierError("'role' is the role's name", EXIT_USAGE)
    value = one.get("value")
    if value is not None and not isinstance(value, str):
        raise ChantierError("'value' is a text, or null to inherit", EXIT_USAGE)


def _shape(changes: object) -> list[dict[str, Any]]:
    """The changes' shape: a list of `{host, role, key, value}` (a 400 otherwise); a value named
    `default` is refused (409)."""
    if not isinstance(changes, list) or not changes:
        raise ChantierError("'changes' is a list of {host, role, key, value}", EXIT_USAGE)
    for one in changes:
        _one(one)
    if any(one.get("value") == "default" for one in changes):
        raise ChantierError(DEFAULT_TEXT, EXIT_PRECONDITION)
    return changes


def _candidate(
    repo: Repo,
    target: Target,
    text: str,
    roles_by_host: dict[str, list[str]],
    defaults: Node | None,
) -> tuple[list[layers.Layer], list[str], list[str]]:
    """The layers as they would be with the new text, the problems of that text and of the merge
    (a start refused on a host is the user's configuration: it blocks nothing), and the problems
    of the other files, which the write neither causes nor blocks on."""
    tree, problems = layers.read_text(text, target.shown, PROJECT_LABEL, roles_by_host)
    others, found = layers.read_user(repo, roles_by_host)
    user = [layer for layer in others if layer.label != PROJECT_LABEL]
    if tree is not None:
        user.append(layers.Layer(PROJECT_LABEL, target.path, target.shown, tree))
    user.sort(key=lambda layer: LABELS.index(layer.label))
    if tree is not None:
        for host in HOSTS:
            judged = layers.judge(user, host, roles_by_host, defaults, tolerate=True)
            problems += [p for p in judged.problems if p not in problems]
    elsewhere = [p for p in found if not p.startswith(f"{target.shown}:")]
    return user, problems, elsewhere


def _refuse_early(repo: Repo, target: Target | None) -> Target:
    if target is None:
        raise ChantierError(READ_ONLY, EXIT_PRECONDITION)
    if target.both:
        raise ChantierError(target.both, EXIT_PRECONDITION)
    return target


def edit_surface_file(
    repo: Repo, changes: object, base_sha256: str | None, dry_run: bool
) -> dict[str, Any]:
    """Set (a text) or remove (None) each role's `agent` or `model` for a host in the project's
    file of the planning surface, and return the view the file then gives. Refuses, writing
    nothing, with a reason: no surface, a file that changed since it was read, both file names, a
    value the checks refuse (the problem lines, the file named, the line numbers the new text
    would have). With `dry_run` it writes nothing."""
    wanted = _shape(changes)
    target = _refuse_early(repo, _writable(repo))
    roles_by_host = _roles_by_host()
    defaults, _ = layers.read_defaults(_defaults_path(), roles_by_host)
    with changes_lock(repo):
        old = _read_bytes(target.path)
        if _sha(old) != (base_sha256.lower() if base_sha256 else None):
            raise ChantierError(
                f"{target.shown} changed since you read it: reload it", EXIT_CONFLICT
            )
        text = edit_text.new_text(old, target.shown, wanted)
        user, problems, elsewhere = _candidate(repo, target, text, roles_by_host, defaults)
        if problems:
            raise ChantierError("\n".join(problems), EXIT_PRECONDITION)
        data = old
        if not dry_run:
            data = edit_text.file_bytes(text, old)
            write_bytes(target.path, data)
    return _view(repo, user, defaults, elsewhere, (target, data))

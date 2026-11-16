"""The configuration in layers: the plugin's shipped defaults, then the surface root's
`chantier.yaml`, the project's folder's in the surface, and the code repository's.

Each layer is read and checked alone, then the user layers merge node by node (a mapping merges
key by key, a scalar or a list of a stronger layer replaces the weaker one whole, a `prices`
entry is replaced whole). A plain `default`, `~` or `null` in a user layer unsets a node: it
removes it, and everything under it, from the weaker user layers. Every node keeps the label and
the file of the layer that wrote it (`Node.layer`, `Node.src`), and every leaf a reset removed
keeps the reset (`Merged.resets`), for the prints and for the board.

The defaults layer is held apart: it gives each role's default model and never counts as a role
setting. This module reads no plugin file: the caller passes the defaults file and the plugin's
roles."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chantier.core.repo import Repo
from chantier.playbook import config
from chantier.playbook.models import NAMED_AGENT_MODEL_AT_START, resolve
from chantier.playbook.yaml_subset import Node, is_reset

DEFAULTS_DISPLAY = "config/chantier.defaults.yml"
Path_ = tuple[str, ...]
PRICE_DEPTH = 2  # prices, <model id>
ROLE_KEY_DEPTH = 5  # hosts, <host>, roles, <role>, <key>


@dataclass
class Layer:
    label: str  # defaults, surface, surface project or repository
    path: Path
    display: str  # the path as the user types it from the session's folder
    tree: Node | None = None  # None: not read (absent, or a problem)


@dataclass
class Reset:
    label: str
    src: str
    line: int


@dataclass
class Merged:
    """The user layers merged: the tree, the files read and the resets that removed a value."""

    tree: Node
    files: list[str]
    resets: dict[Path_, Reset] = field(default_factory=dict)


def display(repo: Repo, path: Path) -> str:
    """A file's path as the user would type it from the session's folder."""
    try:
        return path.relative_to(repo.session_root).as_posix()
    except ValueError:
        return path.as_posix()


def _places(repo: Repo) -> list[tuple[str, Path]]:
    if repo.external:
        return [
            ("surface", repo.surface_root),
            ("surface project", repo.project_folder),
            ("repository", repo.root),
        ]
    return [("repository", repo.root)]


def _stamp(node: Node, label: str, src: str) -> None:
    node.layer, node.src = label, src
    if node.kind == "map":
        for _, child in node.value.values():
            _stamp(child, label, src)
    elif node.kind == "list":
        for item in node.value:
            _stamp(item, label, src)


def read_text(
    text: str, shown: str, label: str, roles_by_host: dict[str, list[str]]
) -> tuple[Node | None, list[str]]:
    """A layer's text, not yet written, read and checked alone with the lines it would have."""
    return _checked(config.parse_text(text, shown), shown, label, roles_by_host, None)


def read_defaults(
    defaults: Path | None, roles_by_host: dict[str, list[str]]
) -> tuple[Node | None, list[str]]:
    """The plugin's shipped defaults (None with no plugin), and the problems found in them."""
    if defaults is None:
        return None, []
    if not defaults.is_file():
        return None, [f"{DEFAULTS_DISPLAY}: the plugin's defaults file is missing"]
    read = config.read_tree(defaults, DEFAULTS_DISPLAY)
    return _checked(read, DEFAULTS_DISPLAY, "defaults", roles_by_host, None)


def _checked(
    read: tuple[Node | None, list[str]],
    shown: str,
    label: str,
    roles_by_host: dict[str, list[str]],
    only: str | None,
) -> tuple[Node | None, list[str]]:
    tree, stop = read
    if tree is None:
        return None, stop
    found: list[tuple[int, str]] = []
    config.check(tree, roles_by_host, lambda n, m: found.append((n, m)), only)
    if found:
        return None, [f"{shown}:{n}: {m}" for n, m in sorted(found, key=lambda p: p[0])]
    _stamp(tree, label, shown)
    return tree, []


def user_files(repo: Repo) -> list[str]:
    """The user files present, weakest layer first, as the user types them."""
    return [
        display(repo, folder / name)
        for _, folder in _places(repo)
        for name in config.FILES
        if (folder / name).is_file()
    ]


def read_user(
    repo: Repo, roles_by_host: dict[str, list[str]], only: str | None = None
) -> tuple[list[Layer], list[str]]:
    """The user layers present and valid, weakest first, and every problem found in any of them
    (a layer with a problem is not skipped: the others are read too)."""
    layers: list[Layer] = []
    problems: list[str] = []
    for label, folder in _places(repo):
        found = [folder / n for n in config.FILES if (folder / n).is_file()]
        if len(found) > 1:
            names = " and ".join(display(repo, p) for p in found)
            problems.append(f"{names} are both present: keep one")
            continue
        if not found:
            continue
        shown = display(repo, found[0])
        tree, bad = _checked(config.read_tree(found[0], shown), shown, label, roles_by_host, only)
        problems += bad
        if tree is not None:
            layers.append(Layer(label, found[0], shown, tree))
    return layers, problems


def _whole(path: Path_) -> bool:
    """A `prices.<model id>` entry is one value: replaced whole, never merged price by price."""
    return len(path) == PRICE_DEPTH and path[0] == "prices"


def _leaves(node: Node, path: Path_) -> Iterator[Path_]:
    if node.kind == "map" and not _whole(path):
        for key, (_, child) in node.value.items():
            yield from _leaves(child, (*path, key))
    else:
        yield path


def _taken_back(old: Node, here: Path_, reset: Reset) -> dict[Path_, Reset]:
    return {leaf: reset for leaf in _leaves(old, here)}


def _merge(
    acc: dict[str, tuple[int, Node]],
    new: dict[str, tuple[int, Node]],
    path: Path_,
    layer: Layer,
    resets: dict[Path_, Reset],
) -> dict[str, tuple[int, Node]]:
    out = dict(acc)
    for key, (line, node) in new.items():
        here = (*path, key)
        old = out.get(key)
        if is_reset(node):
            if old:
                resets.update(_taken_back(old[1], here, Reset(layer.label, layer.display, line)))
            out.pop(key, None)
        elif node.kind == "map" and old and old[1].kind == "map" and not _whole(here):
            merged = _merge(old[1].value, node.value, here, layer, resets)
            out[key] = (line, Node("map", node.line, merged, layer=node.layer, src=node.src))
        else:
            out[key] = (line, node)
    return out


def _prune(entries: dict[str, tuple[int, Node]]) -> dict[str, tuple[int, Node]]:
    """Without the mappings a reset left empty."""
    out: dict[str, tuple[int, Node]] = {}
    for key, (line, node) in entries.items():
        kept = node
        if node.kind == "map":
            inner = _prune(node.value)
            if not inner:
                continue
            kept = Node("map", node.line, inner, layer=node.layer, src=node.src)
        out[key] = (line, kept)
    return out


def _has(tree: Node, path: Path_) -> bool:
    node = tree
    for key in path:
        if node.kind != "map" or key not in node.value:
            return False
        node = node.value[key][1]
    return True


def merge(layers: list[Layer]) -> Merged:
    """The layers, weakest first, merged node by node."""
    entries: dict[str, tuple[int, Node]] = {}
    resets: dict[Path_, Reset] = {}
    for layer in layers:
        assert layer.tree is not None
        entries = _merge(entries, layer.tree.value, (), layer, resets)
    tree = Node("map", 1, _prune(entries))
    kept = {p: r for p, r in resets.items() if not _has(tree, p)}
    return Merged(tree, [layer.display for layer in layers], kept)


def default_model(defaults: Node | None, host: str, role: str) -> str | None:
    """The identifier the defaults layer gives a role on a host, resolved, or None."""
    if defaults is None:
        return None
    node = defaults
    for key in ("hosts", host, "roles", role, "model"):
        if node.kind != "map" or key not in node.value:
            return None
        node = node.value[key][1]
    found, _ = resolve(host, node.value) if node.kind == "scalar" else (None, None)
    return found.id if found else None


def _sink(problems: list[str], where: str) -> config.Bad:
    return lambda n, m: problems.append(f"{where}:{n}: {m}")


def load(
    repo: Repo, host: str, roles_by_host: dict[str, list[str]], defaults: Path | None
) -> tuple[dict[str, Any] | None, list[str]]:
    """The configuration for this host: `(None, [])` when no user file is present, else the
    resolved playbook (`files`, `host`, `roles`, `prices`, `ci`, and `layers`: for each value,
    the label of the layer that set it, and for each reset the layer) or the problems found.
    `defaults` is the plugin's shipped file, None with no plugin."""
    defaults_tree, problems = read_defaults(defaults, roles_by_host)
    layers, found = read_user(repo, roles_by_host)
    problems += found
    if problems or not layers:
        return None, problems
    judged = judge(layers, host, roles_by_host, defaults_tree)
    if judged.problems:
        return None, judged.problems
    merged, roles, nodes, rest = judged.merged, judged.roles, judged.nodes, judged.rest
    out: dict[str, Any] = {
        "files": merged.files,
        "host": host,
        "roles": roles,
        "prices": rest.get("prices", {}),
    }
    if rest.get("ci"):
        out["ci"] = rest["ci"]
    out["layers"] = _labels(merged, host, roles, nodes, out)
    if out["prices"]:  # read live at each pricing, never frozen with the roles
        held = merged.tree.value["prices"][1].value
        out["price_layers"] = {m: held[m][1].layer for m in out["prices"]}
    return out, []


@dataclass
class Judged:
    """The layers merged and judged for one host: the merged tree, the roles resolved (each with
    its `start`), the role nodes, the other keys typed, the problems and, with `tolerate`, the
    refused starts apart (role -> the line), which are then no problem."""

    merged: Merged
    roles: dict[str, dict[str, Any]]
    nodes: dict[str, Node]
    rest: dict[str, Any]
    problems: list[str]
    refusals: dict[str, str]


def judge(
    layers: list[Layer],
    host: str,
    roles_by_host: dict[str, list[str]],
    defaults: Node | None,
    tolerate: bool = False,
) -> Judged:
    """The user layers, weakest first, merged and judged for this host."""
    problems: list[str] = []
    merged = merge(layers)
    sink = _sink(problems, "the merged configuration")
    rest = config.typed(merged.tree, sink, host=host, roles=roles_by_host.get(host))
    roles: dict[str, dict[str, Any]] = rest.get("roles", {})
    nodes = _role_nodes(merged.tree, host)
    refusals: dict[str, str] = {}
    problems += _model_problems(roles, nodes, host, defaults, refusals if tolerate else None)
    return Judged(merged, roles, nodes, rest, problems, refusals)


def _model_problems(
    roles: dict[str, dict[str, Any]],
    nodes: dict[str, Node],
    host: str,
    defaults: Node | None,
    refusals: dict[str, str] | None = None,
) -> list[str]:
    """Judge each configured role once merged, for this host alone, and record its `start`: a
    model equal to the plugin agent's own, with no agent set, is dropped (nothing to pass); then
    `plugin` (the plugin's agent, no model passed), `named` (the user's agent, or the plugin's with
    a model, on a host that starts a named agent with a model) or `generic` (a model, no agent, on
    a host that cannot). The user's agent with a model on a host that cannot is refused, at the
    line of the layer that wrote the model."""
    problems: list[str] = []
    for role, rec in list(roles.items()):
        if "agent" not in rec and rec.get("model", {}).get("id") == default_model(
            defaults, host, role
        ):
            del rec["model"]
        if not rec:
            del roles[role]
        elif "model" not in rec:
            rec["start"] = "named" if "agent" in rec else "plugin"
        elif NAMED_AGENT_MODEL_AT_START[host]:
            rec["start"] = "named"
        elif "agent" not in rec:
            rec["start"] = "generic"
        elif why := config.start_refusal(host, role):
            node = nodes[role].value["model"][1]
            line = f"{node.src}:{node.line}: {why}"
            if refusals is None:
                problems.append(line)
            else:
                refusals[role] = line
    return problems


def _role_nodes(tree: Node, host: str) -> dict[str, Node]:
    node = tree
    for key in ("hosts", host, "roles"):
        if node.kind != "map" or key not in node.value:
            return {}
        node = node.value[key][1]
    return {role: child for role, (_, child) in node.value.items()}


def _labels(
    merged: Merged,
    host: str,
    roles: dict[str, dict[str, Any]],
    nodes: dict[str, Node],
    out: dict[str, Any],
) -> dict[str, Any]:
    """The label of the layer behind each value, and of the reset behind each value taken back."""
    labels: dict[str, Any] = {
        "roles": {
            r: {k: nodes[r].value[k][1].layer for k in rec if k != "start"}
            for r, rec in roles.items()
        },
        "resets": {},
    }
    for path, reset in merged.resets.items():
        if path[:3] == ("hosts", host, "roles") and len(path) == ROLE_KEY_DEPTH:
            labels["resets"].setdefault(path[3], {})[path[4]] = reset.label
    if out.get("ci"):
        labels["ci"] = merged.tree.value["ci"][1].value["beside_gate"][1].layer
    return labels


def read_key(repo: Repo, key: str) -> tuple[dict[str, Any], list[str]]:
    """One key of the merged user layers (`board`, `long_gate`), for the commands that need no
    plugin: the other keys, the roles among them, are `playbook`'s to judge."""
    layers, problems = read_user(repo, {}, only=key)
    if problems or not layers:
        return {}, problems
    found = config.typed(merge(layers).tree, _sink(problems, "the merged configuration"), only=key)
    return found, problems


def load_board(repo: Repo) -> tuple[dict[str, Any], list[str]]:
    """The `board` key alone, for `chantier board`: `({}, [])` when there is none."""
    found, problems = read_key(repo, "board")
    return found.get("board", {}), problems


def load_long_gate(repo: Repo) -> tuple[int, list[str]]:
    """The `long_gate` key alone, for `chantier gate`: `(1, [])` when there is none."""
    found, problems = read_key(repo, "long_gate")
    return found.get("long_gate", 1), problems

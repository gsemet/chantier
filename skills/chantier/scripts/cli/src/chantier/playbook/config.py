"""`chantier.yaml`: reading and validating one layer of the configuration, and turning the merged
layers (`layers.py`) into the values the commands use."""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from chantier.playbook.models import HOST_NAMES, NAMED_AGENT_MODEL_AT_START, resolve
from chantier.playbook.timing_check import check_timing
from chantier.playbook.yaml_subset import Node, YamlError, is_reset, parse

FILES = ("chantier.yaml", "chantier.yml")
FILE = FILES[0]
Bad = Callable[[int, str], None]


ROLE_KEYS = ("agent", "model", "skills", "tools")


PRICE_NAMES = ("input", "cache_write_5m", "cache_write_1h", "cache_read", "output")


BOARD_KEYS = ("host", "port")


HOST_FILES = {"claude": "claude-code", "copilot": "copilot"}


ROLES_MOVED = (
    '"roles" goes under a host: hosts: claude: roles: or hosts: copilot: roles: '
    "(every role setting is per host)"
)


def default_agent(host: str, role: str) -> str:
    return f"chantier:{role}" if host == "claude" else f"chantier-{role}"


def read_tree(path: Path, display: str) -> tuple[Node | None, list[str]]:
    """One file's tree, or the one problem that stops the reading (`<display>:<line>: ...`)."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        return None, [f"{display}:1: cannot read the file as UTF-8: {e}"]
    return parse_text(text, display)


def parse_text(text: str, display: str) -> tuple[Node | None, list[str]]:
    """A file's text as a tree, or the one problem that stops the reading."""
    try:
        tree = parse(text)
    except YamlError as e:
        return None, [f"{display}:{e.line}: {e.message}"]
    if tree.kind != "map":
        return None, [
            f"{display}:{tree.line}: the file is a mapping: `hosts:` then one entry per host"
        ]
    return tree, []


def check(
    tree: Node, roles_by_host: dict[str, list[str]], bad: Bad, only: str | None = None
) -> None:
    """One layer's keys, each checked alone: the shapes, the names, the values. A reset (a plain
    `default`, `~` or `null`) is accepted where its key is. With `only`, that key alone."""
    for key, (kline, node) in tree.value.items():
        if only and key != only:
            continue
        if key == "roles":
            bad(kline, ROLES_MOVED)
        elif key == "hosts":
            _hosts(node, kline, roles_by_host, bad)
        elif key in _KEYED:
            if not is_reset(node):
                _KEYED[key](node, kline, bad)
        else:
            bad(
                kline,
                f'unknown key "{key}": the top-level keys are "hosts", "prices", "board", "ci" '
                'and "long_gate"',
            )


def typed(
    tree: Node,
    bad: Bad,
    only: str | None = None,
    host: str | None = None,
    roles: list[str] | None = None,
) -> dict[str, Any]:
    """The merged tree's keys as values: `prices`, `board`, `ci`, `long_gate`, and `roles` for
    `host` (the plugin's `roles` of that host). Every key was checked in its own layer."""
    out: dict[str, Any] = {}
    for key, (kline, node) in tree.value.items():
        if only and key != only:
            continue
        if key in _KEYED:
            out[key] = _KEYED[key](node, kline, bad)
        elif key == "hosts" and host:
            found = node.value.get(host)
            held = found[1].value.get("roles") if found else None
            if held:
                out["roles"] = _roles(held[1], held[0], host, roles or [], bad) or {}
    return out


def start_refusal(host: str, role: str) -> str | None:
    """Why the user's own agent cannot start with a model on this host, or None."""
    if NAMED_AGENT_MODEL_AT_START[host]:
        return None
    return (
        f'role "{role}": {HOST_NAMES[host]} cannot start a named agent with a model '
        f'(hosts/{HOST_FILES[host]}.md, "Models at an agent\'s start"): remove "model" for '
        f"{role} under hosts.{host}.roles, or name the model in your agent's own file"
    )


def _hosts(node: Node, kline: int, roles_by_host: dict[str, list[str]], bad: Bad) -> None:
    """The `hosts` key: `<host>:` then `roles:`. Every host's roles are checked in every view."""
    if is_reset(node):
        return
    if node.kind != "map" or not node.value:
        bad(kline, '"hosts" holds one entry per host: `<host>:` then `roles:`')
        return
    for host, (hline, hnode) in node.value.items():
        if host not in HOST_NAMES:
            bad(hline, f'unknown host "{host}": one of {", ".join(HOST_NAMES)}')
        elif is_reset(hnode):
            continue
        elif hnode.kind != "map" or not hnode.value:
            bad(hline, f'host "{host}" holds its keys: `roles:` and `timing:`')
        else:
            _host(host, hnode, roles_by_host.get(host, []), bad)


def _host(host: str, node: Node, roles: list[str], bad: Bad) -> None:
    for key, (line, value) in node.value.items():
        if key not in ("roles", "timing"):
            bad(line, f'host "{host}": unknown key "{key}": one of roles, timing')
        elif is_reset(value):
            continue
        elif key == "roles":
            _roles(value, line, host, roles, bad)
        else:
            check_timing(host, value, line, bad)


def _roles(
    node: Node, kline: int, host: str, roles: list[str], bad: Bad
) -> dict[str, dict[str, Any]] | None:
    """The `roles` key of a host resolved, or None when it is wrong as a whole."""
    if node.kind != "map" or not node.value:
        bad(kline, '"roles" holds one entry per role: `<role>:` then its keys')
        return None
    if not roles:
        bad(kline, f"no plugin agent found for {HOST_NAMES[host]}: the roles cannot be checked")
        return None
    resolved: dict[str, dict[str, Any]] = {}
    for role, (rline, rnode) in node.value.items():
        if role not in roles:
            bad(rline, f'role "{role}" is not one of the plugin\'s agents: {", ".join(roles)}')
        elif is_reset(rnode):
            continue
        elif rnode.kind != "map" or not rnode.value:
            bad(rline, f'role "{role}" is empty: set one of {", ".join(ROLE_KEYS)}')
        else:
            resolved[role] = _role(host, role, rnode, bad)
    return resolved


CI_KEYS = ("beside_gate",)


def _ci(node: Node, kline: int, bad: Bad) -> dict[str, Any]:
    """The `ci` key: how a CR's CI runs. Its one key is optional."""
    rec: dict[str, Any] = {}
    if node.kind != "map" or not node.value:
        bad(kline, '"ci" holds its keys: `beside_gate:`')
        return rec
    for key, (line, value) in node.value.items():
        if key not in CI_KEYS:
            bad(line, f'ci: unknown key "{key}": one of {", ".join(CI_KEYS)}')
        elif is_reset(value):
            continue
        elif value.kind != "scalar" or value.value not in ("true", "false"):
            found = value.value if value.kind == "scalar" else value.kind
            bad(line, f'ci: "beside_gate" is true or false, found "{found}"')
        else:
            rec["beside_gate"] = value.value == "true"
    return rec


def _number(node: Node) -> float | None:
    """A non-negative finite number from a scalar, else None."""
    if node.kind != "scalar":
        return None
    try:
        value = float(node.value)
    except ValueError:
        return None
    return value if math.isfinite(value) and value >= 0 else None


def _five(node: Node, line: int, where: str, bad: Bad, tier: bool) -> dict[str, Any] | None:
    """The five prices of an entry (or of its `long_context`, which also has `above`), or None
    when a value is wrong or one is missing: none is derived from another."""
    need = PRICE_NAMES + (("above",) if tier else ())
    keys = need if tier else (*need, "long_context")
    rec: dict[str, Any] = {}
    ok = True
    for key, (kline, value) in node.value.items():
        if key not in keys:
            bad(kline, f'{where}: unknown key "{key}": one of {", ".join(keys)}')
            ok = False
        elif key == "long_context":
            found = _long_context(value, kline, where, bad)
            if found:
                rec[key] = found
            else:
                ok = False
        elif (number := _number(value)) is None:
            bad(kline, f'{where}: "{key}" is a number, not negative')
            ok = False
        else:
            rec[key] = number
    absent = [k for k in need if k not in node.value]
    if absent:
        bad(
            line,
            f"{where}: missing {', '.join(absent)} (all five prices are required, "
            "none is derived from another)",
        )
    return rec if ok and not absent else None


def _long_context(value: Node, kline: int, where: str, bad: Bad) -> dict[str, Any] | None:
    if value.kind != "map" or not value.value:
        bad(kline, f"{where}: long_context holds `above` and the five prices")
        return None
    return _five(value, kline, f"{where}: long_context", bad, True)


def _prices(node: Node, kline: int, bad: Bad) -> dict[str, dict[str, Any]]:
    """`prices:` one entry per exact model id, in $/MTok."""
    if node.kind != "map" or not node.value:
        bad(kline, '"prices" holds one entry per model id: `<id>:` then its five prices')
        return {}
    out: dict[str, dict[str, Any]] = {}
    for model, (mline, mnode) in node.value.items():
        if is_reset(mnode):
            continue
        if mnode.kind != "map" or not mnode.value:
            bad(mline, f'prices: "{model}" is empty: set {", ".join(PRICE_NAMES)}')
            continue
        found = _five(mnode, mline, f'prices: "{model}"', bad, False)
        if found:
            out[model] = found
    return out


def _board(node: Node, kline: int, bad: Bad) -> dict[str, Any]:
    """The `board` key: where `chantier board` listens. Both keys are optional."""
    rec: dict[str, Any] = {}
    if node.kind != "map" or not node.value:
        bad(kline, f'"board" holds its keys: `host:` and `port:` ({", ".join(BOARD_KEYS)})')
        return rec
    for key, (line, value) in node.value.items():
        if key not in BOARD_KEYS:
            bad(line, f'board: unknown key "{key}": one of {", ".join(BOARD_KEYS)}')
        elif is_reset(value):
            continue
        elif value.kind != "scalar" or not value.value.strip() or re.search(r"\s", value.value):
            bad(
                line,
                f'board: "{key}" is one {"address" if key == "host" else "integer"} '
                "with no whitespace",
            )
        elif key == "host":
            rec["host"] = value.value
        elif not re.fullmatch(r"[0-9]+", value.value) or not 1 <= int(value.value) <= MAX_PORT:
            bad(line, f'board: "port" is an integer from 1 to 65535, found "{value.value}"')
        else:
            rec["port"] = int(value.value)
    return rec


MAX_PORT = 65535


def _long_gate(node: Node, kline: int, bad: Bad) -> int:
    """The `long_gate` key: how many long gates may run at once. 1 when `parallel` is absent."""
    if node.kind != "map" or not node.value:
        bad(kline, '"long_gate" holds its key: `parallel:`')
        return 1
    parallel = 1
    for key, (line, value) in node.value.items():
        if key != "parallel":
            bad(line, f'long_gate: unknown key "{key}": one of parallel')
        elif is_reset(value):
            continue
        elif (
            value.kind != "scalar"
            or not re.fullmatch(r"[0-9]+", value.value)
            or not int(value.value)
        ):
            found = value.value if value.kind == "scalar" else ""
            bad(line, f'long_gate: "parallel" is a whole number, 1 or more, found "{found}"')
        else:
            parallel = int(value.value)
    return parallel


_KEYED: dict[str, Callable[[Node, int, Bad], Any]] = {
    "prices": _prices,
    "board": _board,
    "ci": _ci,
    "long_gate": _long_gate,
}

RESET_TEXT = (
    '"default" resets the value: write it plain, default; no agent or model is named "default"'
)


def _quoted_default(value: Node) -> bool:
    return value.kind == "scalar" and not value.plain and value.value == "default"


def _role_agent(role: str, kline: int, value: Node, bad: Bad) -> str | None:
    if _quoted_default(value):
        bad(kline, RESET_TEXT)
    elif value.kind != "scalar" or not value.value.strip():
        bad(kline, f'role "{role}": "agent" is one string')
    elif re.search(r"\s", value.value):
        bad(kline, f'role "{role}": agent "{value.value}" holds whitespace')
    else:
        return str(value.value)
    return None


def _role_model(host: str, role: str, kline: int, value: Node, bad: Bad) -> dict[str, Any] | None:
    if _quoted_default(value):
        bad(kline, RESET_TEXT)
        return None
    if value.kind != "scalar" or not value.value.strip():
        bad(kline, f'role "{role}": "model" is one string')
        return None
    found, why = resolve(host, value.value)
    if why:
        bad(kline, f'role "{role}": {why}')
    elif found is not None:
        return {"id": found.id, "name": found.name, "start": found.start}
    return None


def _role_list(role: str, key: str, kline: int, value: Node, bad: Bad) -> list[str] | None:
    if value.kind != "list" or not value.value:
        bad(kline, f'role "{role}": "{key}" is a list of names: `[a, b]` or `- a` lines')
    elif any(not n.value.strip() or re.search(r"\s", n.value) for n in value.value):
        bad(kline, f'role "{role}": a name in "{key}" is empty or holds whitespace')
    else:
        return [n.value for n in value.value]
    return None


def _role(host: str, role: str, node: Node, bad: Bad) -> dict[str, Any]:
    rec: dict[str, Any] = {}
    got: Any
    for key, (kline, value) in node.value.items():
        if key not in ROLE_KEYS:
            bad(kline, f'role "{role}": unknown key "{key}": one of {", ".join(ROLE_KEYS)}')
            continue
        if is_reset(value):
            continue
        if key == "agent":
            got = _role_agent(role, kline, value, bad)
        elif key == "model":
            got = _role_model(host, role, kline, value, bad)
        else:
            got = _role_list(role, key, kline, value, bad)
        if got is not None:
            rec[key] = got
    return rec

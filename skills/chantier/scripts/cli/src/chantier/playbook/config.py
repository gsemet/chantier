"""`chantier.yaml`: loading and validating the project's configuration."""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from chantier.playbook.models import HOST_NAMES, SETS_MODEL_AT_START, resolve
from chantier.playbook.yaml_subset import Node, YamlError, parse

FILE = "chantier.yaml"
Bad = Callable[[int, str], None]


ROLE_KEYS = ("agent", "model", "skills", "tools")


PRICE_NAMES = ("input", "cache_write_5m", "cache_write_1h", "cache_read", "output")


BOARD_KEYS = ("host", "port")


HOST_FILES = {"claude": "claude-code", "copilot": "copilot"}


def default_agent(host: str, role: str) -> str:
    return f"chantier:{role}" if host == "claude" else f"chantier-{role}"


def _read_tree(path: Path) -> tuple[Node | None, list[str]]:
    """The file's tree, or the one problem that stops the reading."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        return None, [f"{FILE}:1: cannot read the file as UTF-8: {e}"]
    try:
        tree = parse(text)
    except YamlError as e:
        return None, [f"{FILE}:{e.line}: {e.message}"]
    if tree.kind != "map":
        return None, [
            f"{FILE}:{tree.line}: the file is a mapping: `roles:` then one entry per role"
        ]
    return tree, []


def _roles(
    node: Node, kline: int, host: str, roles: list[str], bad: Bad
) -> dict[str, dict[str, Any]] | None:
    """The `roles` key resolved, or None when it is wrong as a whole."""
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
        elif rnode.kind != "map" or not rnode.value:
            bad(rline, f'role "{role}" is empty: set one of {", ".join(ROLE_KEYS)}')
        else:
            resolved[role] = _role(host, role, rnode, bad)
    return resolved


def load(path: Path, host: str, roles: list[str]) -> tuple[dict[str, Any] | None, list[str]]:
    """`(None, [])` when the file is absent; else the resolved playbook and the problems found
    (each `chantier.yaml:<line>: ...`, in line order). `roles` are the plugin's, for this host."""
    if not path.is_file():
        return None, []
    tree, stop = _read_tree(path)
    if tree is None:
        return None, stop
    problems: list[tuple[int, str]] = []

    def bad(line: int, message: str) -> None:
        problems.append((line, message))

    resolved: dict[str, dict[str, Any]] = {}
    prices: dict[str, dict[str, Any]] = {}
    for key, (kline, node) in tree.value.items():
        if key == "prices":
            prices = _prices(node, kline, bad)
        elif key == "board":
            _board(node, kline, bad)
        elif key == "roles":
            resolved.update(_roles(node, kline, host, roles, bad) or {})
        else:
            bad(kline, f'unknown key "{key}": the top-level keys are "roles", "prices" and "board"')
    problems.sort(key=lambda p: p[0])
    lines = [f"{FILE}:{n}: {m}" for n, m in problems]
    return (
        {"file": FILE, "host": host, "roles": resolved, "prices": prices} if not lines else None
    ), lines


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


def load_board(path: Path) -> tuple[dict[str, Any], list[str]]:
    """The `board` key alone, for `chantier board`: `({}, [])` when there is none, else its keys
    or the problems found in it (the roles are `playbook`'s to judge, not the board's)."""
    if not path.is_file():
        return {}, []
    try:
        tree = parse(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError) as e:
        return {}, [f"{FILE}:1: cannot read the file as UTF-8: {e}"]
    except YamlError as e:
        return {}, [f"{FILE}:{e.line}: {e.message}"]
    if tree.kind != "map":
        return {}, [f"{FILE}:{tree.line}: the file is a mapping: `roles:` then one entry per role"]
    problems: list[tuple[int, str]] = []
    rec: dict[str, Any] = {}
    if "board" in tree.value:
        line, node = tree.value["board"]
        rec = _board(node, line, lambda n, m: problems.append((n, m)))
    return rec, [f"{FILE}:{n}: {m}" for n, m in sorted(problems)]


def _role_agent(role: str, kline: int, value: Node, bad: Bad) -> str | None:
    if value.kind != "scalar" or not value.value.strip():
        bad(kline, f'role "{role}": "agent" is one string')
    elif re.search(r"\s", value.value):
        bad(kline, f'role "{role}": agent "{value.value}" holds whitespace')
    else:
        return str(value.value)
    return None


def _role_model(host: str, role: str, kline: int, value: Node, bad: Bad) -> dict[str, Any] | None:
    if value.kind != "scalar" or not value.value.strip():
        bad(kline, f'role "{role}": "model" is one string')
        return None
    found, why = resolve(host, value.value)
    if why:
        bad(kline, f'role "{role}": {why}')
    elif not SETS_MODEL_AT_START[host]:
        bad(
            kline,
            f"{HOST_NAMES[host]} cannot set a model when it starts an agent "
            f'(hosts/{HOST_FILES[host]}.md, "Models"): remove "model" for {role}, or '
            "run the role with your own agent that names it",
        )
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
        if key == "agent":
            got = _role_agent(role, kline, value, bad)
        elif key == "model":
            got = _role_model(host, role, kline, value, bad)
        else:
            got = _role_list(role, key, kline, value, bad)
        if got is not None:
            rec[key] = got
    return rec

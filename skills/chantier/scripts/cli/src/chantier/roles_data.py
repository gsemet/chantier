"""The plugin's roles as data, read from `skills/chantier/roles.yaml`: the CLI knows roles only as
data, and this module names none of them. `brief` and `help --for` read it, and
`scripts/roles_check.py` (`just roles`) holds the hand-written agent files of both hosts to it."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from chantier import plugin_files
from chantier.core.errors import EXIT_PRECONDITION, ChantierError

KINDS = ("steering", "driver", "worker", "review-step", "critic")
WRITES = ("none", "worktree", "cr-folder")
UNITS = ("cr", "order", "stack", "folder", "none")
HOSTS = ("claude", "copilot")
STARTERS = ("user", "surface-server")
FIELDS = (
    "name",
    "kind",
    "started_by",
    "writes",
    "reply",
    "card",
    "first",
    "description",
    "unit",
    "rows",
    "hosts",
)
OUT_OF_STEP = "the plugin files are out of step"


@dataclass(frozen=True)
class HostSpec:
    """A role's agent file on one host (its repository path, `None` without one) and the tools
    its frontmatter lists, in the file's order."""

    wrapper: str | None
    tools: tuple[str, ...]


@dataclass(frozen=True)
class Role:
    """One role of `roles.yaml`. `first` is the wrapper's first-line template (`None` without a
    wrapper); `rows` the capability ids of the host rows `brief` prints (`None`: every row)."""

    name: str
    kind: str
    started_by: tuple[str, ...]
    writes: str
    reply: str
    card: str
    first: str | None
    description: str
    unit: str
    rows: tuple[str, ...] | None
    hosts: dict[str, HostSpec]


def roles_file() -> Path:
    return plugin_files.skill_dir() / "roles.yaml"


def _bad(where: str, problem: str) -> ChantierError:
    return ChantierError(f"roles.yaml: {where}: {problem}; {OUT_OF_STEP}", EXIT_PRECONDITION)


def _strings(where: str, field: str, value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise _bad(where, f"{field}: a list of names expected")
    return tuple(value)


def _text(where: str, field: str, value: Any, allowed: tuple[str, ...] | None = None) -> str:
    if not isinstance(value, str) or not value:
        raise _bad(where, f"{field}: a text expected")
    if allowed is not None and value not in allowed:
        raise _bad(where, f"{field}: {value!r} is not one of {', '.join(allowed)}")
    return value


def _host(where: str, name: str, value: Any) -> HostSpec:
    if not isinstance(value, dict) or set(value) != {"wrapper", "tools"}:
        raise _bad(where, f"hosts.{name}: wrapper and tools expected")
    wrapper = value["wrapper"]
    if wrapper is not None:
        wrapper = _text(where, f"hosts.{name}.wrapper", wrapper)
    return HostSpec(wrapper, _strings(where, f"hosts.{name}.tools", value["tools"]))


def _role(index: int, raw: Any) -> Role:
    where = f"role {index + 1}"
    if not isinstance(raw, dict):
        raise _bad(where, "a mapping expected")
    if isinstance(raw.get("name"), str):
        where = f"role {raw['name']}"
    for field in FIELDS:
        if field not in raw:
            raise _bad(where, f"no field {field}")
    extra = sorted(set(raw) - set(FIELDS))
    if extra:
        raise _bad(where, f"unknown field {extra[0]}")
    hosts = raw["hosts"]
    if not isinstance(hosts, dict) or set(hosts) != set(HOSTS):
        raise _bad(where, f"hosts: exactly {', '.join(HOSTS)} expected")
    first = raw["first"]
    rows = raw["rows"]
    return Role(
        name=_text(where, "name", raw["name"]),
        kind=_text(where, "kind", raw["kind"], KINDS),
        started_by=_strings(where, "started_by", raw["started_by"]),
        writes=_text(where, "writes", raw["writes"], WRITES),
        reply=_text(where, "reply", raw["reply"]),
        card=_text(where, "card", raw["card"]),
        first=None if first is None else _text(where, "first", first),
        description=_text(where, "description", raw["description"]),
        unit=_text(where, "unit", raw["unit"], UNITS),
        rows=None if rows is None else _strings(where, "rows", rows),
        hosts={h: _host(where, h, hosts[h]) for h in HOSTS},
    )


def _check(found: tuple[Role, ...]) -> None:
    names = [r.name for r in found]
    for r in found:
        if names.count(r.name) > 1:
            raise _bad(f"role {r.name}", "name: given more than once")
        for token in r.started_by:
            if token not in (*names, *KINDS, *STARTERS):
                raise _bad(
                    f"role {r.name}",
                    f"started_by: {token!r} is not a role, a kind, user or surface-server",
                )
        given = [r.first is not None, *(h.wrapper is not None for h in r.hosts.values())]
        if any(given) and not all(given):
            raise _bad(f"role {r.name}", "first and both wrappers: all set or all null")


@cache
def _load(path: Path) -> tuple[Role, ...]:
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError

    try:
        data = YAML(typ="safe", pure=True).load(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, YAMLError) as e:
        raise ChantierError(
            f"roles.yaml: cannot read {path.as_posix()}: {e}; {OUT_OF_STEP}", EXIT_PRECONDITION
        ) from None
    if not isinstance(data, dict) or data.get("version") != 1:
        raise _bad("version", "1 expected")
    raw = data.get("roles")
    if not isinstance(raw, list) or not raw:
        raise _bad("roles", "a non-empty list expected")
    found = tuple(_role(i, r) for i, r in enumerate(raw))
    _check(found)
    return found


def load_roles(path: Path | None = None) -> tuple[Role, ...]:
    """The roles of `roles.yaml` (the plugin's, or `path`'s), in the file's order, checked; a
    problem raises `ChantierError` naming the role and the field. Cached per path."""
    return _load((path or roles_file()).resolve())


def role(name: str) -> Role | None:
    return next((r for r in load_roles() if r.name == name), None)


def names() -> tuple[str, ...]:
    return tuple(r.name for r in load_roles())

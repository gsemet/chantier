"""The text of the planning surface's project file, changed in place: a role's `agent` or `model`
set or removed, the comments and the other keys kept, the file's byte-order mark kept,
the line endings LF. The checks and the write are `edit.py`'s."""

from __future__ import annotations

import io
from collections.abc import Mapping
from typing import Any

from chantier.core.errors import EXIT_PRECONDITION, ChantierError

BOM = b"\xef\xbb\xbf"
WIDE = 4096


def _is_map(node: object) -> bool:
    return isinstance(node, Mapping)


def _walk(data: Any, change: dict[str, Any]) -> list[Any] | None:
    """The maps from the root down to the role's, or None where one is missing."""
    chain = [data]
    for key in ("hosts", change["host"], "roles", change["role"]):
        found = chain[-1].get(key) if _is_map(chain[-1]) else None
        if not _is_map(found):
            return None
        chain.append(found)
    return chain


def _remove(data: Any, change: dict[str, Any]) -> None:
    """The key out of the file, and every map it leaves empty; a role's own reset stays."""
    chain = _walk(data, change)
    if chain is None or change["key"] not in chain[-1]:
        return
    del chain[-1][change["key"]]
    names = ("hosts", change["host"], "roles", change["role"])
    for depth in range(len(chain) - 1, 0, -1):
        if chain[depth]:
            break
        del chain[depth - 1][names[depth - 1]]


def _set(data: Any, change: dict[str, Any]) -> None:
    from ruamel.yaml.comments import CommentedMap

    node = data
    for key in ("hosts", change["host"], "roles", change["role"]):
        if not _is_map(node.get(key)):  # absent, or a reset the new value replaces
            node[key] = CommentedMap()
        node = node[key]
    node[change["key"]] = change["value"]


def _yaml() -> Any:
    from ruamel.yaml import YAML

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = WIDE
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def new_text(old: bytes | None, shown: str, changes: list[dict[str, Any]]) -> str:
    """The file's text with the changes, comments and other keys kept (LF)."""
    from ruamel.yaml.comments import CommentedMap
    from ruamel.yaml.error import YAMLError

    text = (old or b"").decode("utf-8-sig").replace("\r\n", "\n")
    yaml = _yaml()
    try:
        data = yaml.load(text) if text.strip() else None
    except YAMLError as e:
        raise ChantierError(f"{shown}: {e}", EXIT_PRECONDITION) from e
    kept = text if text.strip() and data is None else ""  # a file of comments only
    if data is None:
        data = CommentedMap()
    if not _is_map(data):
        raise ChantierError(f"{shown}:1: the file is a mapping: `hosts:` then one entry per host")
    for change in changes:
        (_set if change["value"] is not None else _remove)(data, change)
    if not data:
        return kept
    out = io.StringIO()
    yaml.dump(data, out)
    return (kept.rstrip("\n") + "\n\n" if kept else "") + out.getvalue()


def file_bytes(text: str, old: bytes | None) -> bytes:
    """The text in UTF-8 with LF line endings only, and with the file's byte-order mark if it had
    one."""
    return (BOM if old is not None and old.startswith(BOM) else b"") + text.encode("utf-8")

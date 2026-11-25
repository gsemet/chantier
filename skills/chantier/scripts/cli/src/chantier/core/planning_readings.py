"""The two other readings of a CR path that names nothing in the planning folder
(`planning_path`)."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from chantier.core.remote_wire import VIA_SERVER


def prefix_of(changes: Path, base: Path) -> str:
    """The planning folder's path from the session's root `base`, with its trailing `/`:
    `projects/<name>/changes/` in a surface, `.agents/changes/` in a project."""
    try:
        return changes.resolve().relative_to(base.resolve()).as_posix() + "/"
    except ValueError:
        return ""


def other_readings(
    changes: Path, base: Path, exists: Callable[[Path], bool], text: str
) -> list[Path]:
    """What a relative value (`/` separators) may also mean: the planning folder's own prefix
    repeated (`projects/<name>/changes/1-inbox/x`, as many times as it leads), and the value read
    from the shell's folder when that is inside the planning folder (never for a command a client
    ran through the server: its folder is not this one). Each kept reading exists and lies
    strictly inside the planning folder; the distinct ones are returned."""
    if not text or text.startswith(("/", "~")) or Path(text).is_absolute():
        return []
    root = changes.resolve()
    found: list[Path] = []
    prefix = prefix_of(changes, base)
    stripped = text
    while prefix and (stripped + "/").startswith(prefix):
        stripped = stripped[len(prefix) :]
    if stripped != text:
        found.append((root / stripped).resolve())
    if not os.environ.get(VIA_SERVER):
        here = Path(os.getcwd()).resolve()
        if here.is_relative_to(root):
            found.append((here / text).resolve())
    out: list[Path] = []
    for path in found:
        if path != root and path.is_relative_to(root) and exists(path) and path not in out:
            out.append(path)
    return out

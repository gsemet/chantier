"""The host rows: how each host does a capability, read from the plugin's
`references/hosts/<host>.json`. A row's means are a few lines; the history behind its mark is in
`docs/proofs/`."""

from __future__ import annotations

import json
from dataclasses import dataclass

from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.plugin_files import skill_dir

UNTESTED = "This path was never tried for real here."
FILES = {"claude": "claude-code.json", "copilot": "copilot.json"}
MARKS = ("proved", "untested")


@dataclass(frozen=True)
class HostRow:
    capability: str
    name: str
    roles: tuple[str, ...]
    means: tuple[str, ...]
    mark: str


def load_rows(host: str) -> list[HostRow]:
    """The rows of one host, in file order; a missing or unreadable file, or a bad row, is a
    precondition failure naming the file and the row."""
    path = skill_dir() / "references" / "hosts" / FILES[host]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data["rows"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise ChantierError(f"host rows: cannot read {path}: {e}", EXIT_PRECONDITION) from e
    rows: list[HostRow] = []
    for i, r in enumerate(raw):
        try:
            row = HostRow(
                str(r["capability"]),
                str(r["name"]),
                tuple(r["roles"]),
                tuple(r["means"]),
                str(r["mark"]),
            )
        except (KeyError, TypeError) as e:
            raise ChantierError(
                f"host rows: {path.name}: row {i + 1} is not readable: {e!r}", EXIT_PRECONDITION
            ) from e
        if row.mark not in MARKS:
            raise ChantierError(
                f"host rows: {path.name}: row `{row.capability}` has mark `{row.mark}`: "
                f"one of {', '.join(MARKS)}",
                EXIT_PRECONDITION,
            )
        rows.append(row)
    return rows


def row_lines(row: HostRow) -> list[str]:
    """`<capability>: <name> (<mark>)`, the means indented, and on a row not proved the one
    sentence that says so."""
    lines = [f"{row.capability}: {row.name} ({row.mark})"]
    lines += [f"  {m}" for m in row.means]
    if row.mark != "proved":
        lines.append(f"  {UNTESTED}")
    return lines

"""The surface's `writer:` line for the commands that print it (`status`, `seat`, `sync`,
`preflight`): external mode only, read-only."""

from __future__ import annotations

from typing import Any

from chantier.core.repo import Repo
from chantier.writer import lines, record


def entry(repo: Repo) -> dict[str, Any]:
    """The live `writer` entry as written, `{"state": "off"}` with none."""
    return record.read(repo.git_dir)


def line(repo: Repo) -> str:
    """The `writer:` line of C.10, the older board's variant when one serves with no writer."""
    return lines.state_line(entry(repo), lines.older_board(repo.git_dir))


def writer_lines(repo: Repo) -> list[str]:
    """The `writer:` line, as a list: none in project mode."""
    return [line(repo)] if repo.external else []

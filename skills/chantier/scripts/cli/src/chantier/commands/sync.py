"""`chantier sync`: the surface's writer, read-only; `sync now` asks it for a cycle at once and
waits for its end (the spec's C.9)."""

from __future__ import annotations

import argparse
import time
from typing import Any

from chantier.commands.writer_line import entry, line
from chantier.core import clock
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.repo import Repo
from chantier.hub import lock
from chantier.writer import lines

WAIT_S = 10.0
STEP_S = 0.2
IN_PROJECT = "sync: in-project planning folder: chantier commits nothing"


def _state(repo: Repo) -> list[str]:
    """The state line, then one line per conflicted file."""
    found = entry(repo)
    out = [line(repo)]
    if found.get("state") == "conflict":
        out += [f"conflict: {p}" for p in (found.get("conflict") or {}).get("files") or []]
    return out


def _after(found: dict[str, Any], touched: str) -> bool:
    """Whether the writer's last cycle ended at or after the touch (stamps are whole seconds)."""
    return str(found.get("last_cycle") or "") >= touched


def sync(args: argparse.Namespace) -> list[str]:
    repo = Repo.find()
    if not repo.external:
        return [IN_PROJECT]
    if args.action != "now":
        return _state(repo)
    if entry(repo).get("state") in ("off", "stopped"):
        raise ChantierError(lines.refusal("sync now", repo.git_dir), EXIT_PRECONDITION)
    touched = clock.now()
    lock.wake(repo.git_dir)
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline and not _after(entry(repo), touched):
        time.sleep(STEP_S)
    return _state(repo)

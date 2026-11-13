"""What the board shows: the data read from the record."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from chantier.core.errors import ChantierError
from chantier.core.files import retry
from chantier.core.records import read_batch_json, read_events
from chantier.core.repo import Repo
from chantier.lifecycle.stages import stage_layout
from chantier.playbook.config import FILE, MAX_PORT, load_board
from chantier.status.views import batch_view, dashboard_view

DEFAULT_HOST, DEFAULT_PORT = "127.0.0.1", 8765
EVENTS_HIDDEN = ("heartbeat", "cost")


EVENTS_SHOWN = 12


def _tail_events(folder: Path) -> list[dict[str, Any]]:
    events = [e.to_data() for e in retry(read_events, folder) if e.kind not in EVENTS_HIDDEN]
    return events[-EVENTS_SHOWN:]


def collect(repo: Repo, seat: str | None) -> dict[str, Any]:
    """What the next `STATUS.json` of the index would say, the batch's own view, its recent
    events, and the board's three own fields. Nothing is written."""
    view = dashboard_view(repo, stage_layout(repo))
    batch, events = None, []
    for folder in repo.batch_folders():
        batch = batch_view(repo, read_batch_json(folder / "batch.json"), folder)
        events = _tail_events(folder)
    return {
        **view,
        "batch": batch,
        "events": events,
        "planning_folder": repo.changes.resolve().as_posix(),
        "seat": seat,
        "board": True,
    }


def settings(repo: Repo, host: str | None, port: int | None) -> tuple[str, int]:
    """The address: the command's options, else `chantier.yaml`'s `board` key, else the default."""
    found, problems = load_board(repo.root / FILE)
    if problems:
        raise ChantierError(problems[0])
    host = host or found.get("host") or DEFAULT_HOST
    port = port if port is not None else found.get("port", DEFAULT_PORT)
    if not 1 <= port <= MAX_PORT:
        raise ChantierError(f"--port {port}: a port is 1 to 65535", 1)
    if re.search(r"\s", host):
        raise ChantierError(f"--host {host!r}: an address holds no whitespace", 1)
    return host, port

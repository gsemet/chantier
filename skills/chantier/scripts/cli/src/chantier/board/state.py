"""A project's state: what the record and the planning folder say, in the shape the views draw.

It is what `collect()` was (the dashboard and batch views of `status/views.py`), plus the fields
the views need that no view has; those stay in the board's own data, never in `STATUS.json`."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from chantier.board import crs
from chantier.board.backlog import backlog_items
from chantier.core.batch import apply_batch_settings
from chantier.core.errors import ChantierError
from chantier.core.files import read_text
from chantier.core.records import (
    BatchRecord,
    BatchSettings,
    EventRecord,
    read_batch_json,
    read_events,
)
from chantier.core.repo import RECORDS, Repo
from chantier.core.seat import read_seat
from chantier.lifecycle.stages import stage_layout
from chantier.rails import held
from chantier.status.views import batch_view, dashboard_view

VIEW_KEYS = (
    "state",
    "mode",
    "steering",
    "spent_usd",
    "budget_usd",
    "unpriced",
    "priced",
    "heartbeat",
    "heartbeat_stopped",
    "asks_unread",
    "orders_pending",
)
EVENTS_SHOWN = 40
EVENT_KINDS = (
    "open",
    "add",
    "take",
    "round",
    "gate",
    "verdict",
    "ship",
    "handback",
    "ask",
    "order",
    "pause",
    "note",
)
EVENT_KEYS = (
    "t",
    "actor",
    "kind",
    "cr",
    "result",
    "pr",
    "note",
    "order_kind",
    "reason",
    "command",
    "round",
)


def _events(events: list[EventRecord]) -> list[dict[str, Any]]:
    shown = [e for e in events if e.kind in EVENT_KINDS][-EVENTS_SHOWN:]
    out = []
    for e in shown:
        data = e.to_data()
        out.append({k: data[k] for k in EVENT_KEYS if data.get(k) is not None})
    return out


def _batch(repo: Repo, d: BatchRecord, folder: Path, events: list[EventRecord]) -> dict[str, Any]:
    view = batch_view(repo, d, folder)
    rows = crs.cr_rows(repo, d, events)
    costs = [e.t for e in events if e.kind == "cost"]
    return {
        "id": d.id,
        **{k: view[k] for k in VIEW_KEYS},
        "created": d.created,
        "default_branch": repo.config["default_branch"],
        "max_rounds": (d.settings or BatchSettings()).max_rounds,
        "slots": {"taken": len(held(d)), "total": d.slots},
        "cost_at": costs[-1] if costs else None,
        "crs": rows,
        "merge_order": crs.merge_order(d, rows),
    }


def _history(changes: Path) -> list[Any]:
    """The batches' own records, newest first, as they are."""
    files = sorted(
        (changes / RECORDS).glob("batch-*.json"),
        key=lambda p: int(m[1]) if (m := re.search(r"(\d+)", p.name)) else 0,
        reverse=True,
    )
    out = []
    for path in files:
        try:
            out.append(json.loads(read_text(path)))
        except (OSError, ValueError):
            continue
    return out


def _seat(repo: Repo) -> dict[str, Any] | None:
    try:
        held_by = read_seat(repo)
    except (ChantierError, OSError, ValueError):  # an unreadable seat file shows no seat
        return None
    return {"title": held_by.title, "env": held_by.env} if held_by else None


def project_state(
    project_id: str, repo: Repo, surface: bool, live: dict[str, Any] | None
) -> dict[str, Any]:
    """The project's state, read now. Nothing is written; `now` is the caller's to add."""
    dash = dashboard_view(repo, stage_layout(repo))
    folders = repo.batch_folders()
    batch = None
    events: list[EventRecord] = []
    if folders:
        d = read_batch_json(folders[0] / "batch.json")
        apply_batch_settings(repo, d)
        events = read_events(folders[0])
        batch = _batch(repo, d, folders[0], events)
    return {
        "project": project_id,
        "surface": surface,
        "seat": _seat(repo),
        "batch": batch,
        "events": _events(events),
        "backlog": backlog_items(repo.changes, dash["backlog"]),
        "merged": dash["merged"],
        "merged_total": dash["merged_total"],
        "trashed": dash["trashed"],
        "trashed_total": dash["trashed_total"],
        "history": _history(repo.changes),
        "live": live,
    }


def _entry(c: dict[str, Any]) -> dict[str, Any]:
    return {"cr": c["cr"], "title": c["title"], "pr": c["pr"]}


def project_line(project_id: str, state: dict[str, Any]) -> dict[str, Any]:
    """What the project picker and "All projects" draw of a project."""
    batch = state["batch"]
    rows = batch["crs"] if batch else []
    review = {c["cr"]: c for c in rows if c["to_review"]}
    ordered = [review[i] for i in batch["merge_order"]] if batch else []
    by_priority = {p: len(state["backlog"][p]) for p in ("P1", "P2", "P3", "P4")}
    return {
        "id": project_id,
        "batch": {k: batch[k] for k in ("id", "state", "mode", "steering")} if batch else None,
        "running": bool(batch and batch["state"] == "running"),
        "working": [_entry(c) for c in rows if c["state"] == "working"],
        "blocked": [_entry(c) for c in rows if c["state"] == "blocked"],
        "to_review": [_entry(c) for c in ordered],
        "merged": sum(1 for c in rows if c["state"] == "merged"),
        "total": len(rows),
        "spent_usd": batch["spent_usd"] if batch else None,
        "budget_usd": batch["budget_usd"] if batch else None,
        "unpriced": batch["unpriced"] if batch else {},
        "inbox": len(state["backlog"]["inbox"]),
        "backlog": sum(by_priority.values()),
        "by_priority": by_priority,
        "cost_at": batch["cost_at"] if batch else None,
        "heartbeat": batch["heartbeat"] if batch else None,
        "heartbeat_stopped": batch["heartbeat_stopped"] if batch else None,
        "asks_unread": batch["asks_unread"] if batch else 0,
        "last_event_at": state["events"][-1]["t"] if state["events"] else None,
    }

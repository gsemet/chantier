"""Which agents the host reports stopped, from a steering transcript's `task_status` records."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from chantier.costs.sessions import _lines_from_end
from chantier.costs.transcripts import transcript_path

_STAMP = re.compile(rb'"timestamp":\s*"([^"]+)"')


def _record_time(raw: bytes) -> datetime | None:
    """The `timestamp` of a transcript line, read without decoding the whole line; None: none, or
    one that is not a time."""
    found = _STAMP.search(raw)
    if found is None:
        return None
    try:
        at = datetime.fromisoformat(found.group(1).decode("ascii"))
    except (ValueError, UnicodeError):
        return None
    return at if at.tzinfo else at.replace(tzinfo=UTC)


def _task_status(raw: bytes) -> tuple[str, str] | None:
    """(`taskId`, `status`) of a `task_status` attachment line, else None."""
    if b'"task_status"' not in raw:
        return None
    try:
        record = json.loads(raw)
    except ValueError:
        return None
    att = record.get("attachment") if isinstance(record, dict) else None
    if not isinstance(att, dict) or att.get("type") != "task_status":
        return None
    return str(att.get("taskId")), str(att.get("status"))


def _scan_stopped(path: Path, starts: dict[str, datetime]) -> dict[str, tuple[datetime, bool]]:
    """One transcript, backward: agent id -> (time of its last `task_status` record, killed)."""
    floor = min(starts.values())
    pending = set(starts)
    found: dict[str, tuple[datetime, bool]] = {}
    for raw in _lines_from_end(path):
        at = _record_time(raw) if raw.strip() else None
        if at is not None and at < floor:
            break
        status = _task_status(raw)
        if status is None or status[0] not in pending or (at and at < starts[status[0]]):
            continue
        pending.discard(status[0])
        found[status[0]] = (at or datetime.min.replace(tzinfo=UTC), status[1] == "killed")
        if not pending:
            break
    return found


def agents_stopped(
    root: Path, sessions: list[str], starts: dict[str, datetime]
) -> dict[str, bool | None]:
    """Claude: whether the host reports each agent stopped, from the end of each steering
    transcript (its main file). `starts`: agent id -> the time it was recorded. The last
    `attachment` record `task_status` of an agent decides: `killed` is stopped (True), any other
    status is False; none, or a file missing or unreadable, is None (not measured, never
    "stopped"). The pass goes backward and stops at the first record older than the earliest start
    asked, or once every agent asked has its record; a record older than an agent's own start
    never decides for it, and a line with no `timestamp` decides but never stops the pass."""
    found: dict[str, tuple[datetime, bool]] = {}
    for session in sessions if starts else []:
        try:
            seen = _scan_stopped(transcript_path(root, session), starts)
        except (OSError, UnicodeError):
            continue
        found |= {a: v for a, v in seen.items() if a not in found or v[0] >= found[a][0]}
    return {a: found[a][1] if a in found else None for a in starts}

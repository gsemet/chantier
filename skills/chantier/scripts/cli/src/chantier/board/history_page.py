"""The History page's answer: what was done in a day, a week or a month, by local day.

It reads only: the closed records (and, for an older one, its archived CRs' `STATUS.json`), the
running batch's record and events. Never the forge, never git; it writes nothing. The index of
dated events is kept in the context with the print of the state it was built from, so no file is
read again while the planning folder does not change."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from chantier.board import reads
from chantier.core import clock
from chantier.core.cr_times import ended
from chantier.core.errors import ChantierError
from chantier.core.files import subject
from chantier.core.records import read_batch_json, read_events
from chantier.core.repo import RECORDS

if TYPE_CHECKING:
    from chantier.board.context import Context
    from chantier.board.projects import Project
    from chantier.core.repo import Repo

ENDING = ("merged", "dropped", "release")
TRASH = "6-trash"


def _valid(at: Any) -> str | None:
    """The stamp when it is one (`YYYY-MM-DDTHH:MM:SSZ`), else None: no time, no event."""
    if not isinstance(at, str):
        return None
    try:
        clock.parse(at)
    except ValueError:
        return None
    return at


class _Index:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.undated = 0
        self.unreadable = 0

    def add(self, kind: str, at: Any, base: dict[str, Any], **more: Any) -> bool:
        stamp = _valid(at)
        if stamp is None:
            return False
        self.events.append({"kind": kind, "at": stamp, **base, **more})
        return True

    def data(self) -> dict[str, Any]:
        return {"events": self.events, "undated": self.undated, "unreadable": self.unreadable}


def _steps(store: Any, archive: str | None, index: _Index) -> list[dict[str, Any]]:
    """The archived CR's `steps`; none when it has no folder or no `STATUS.json`; a file present
    but unreadable is counted."""
    if not archive:
        return []
    rel = f"{archive.rstrip('/')}/STATUS.json"
    try:
        if not store.is_file(rel):
            return []
        found = json.loads(store.read_text(rel))
        steps = found.get("steps") if isinstance(found, dict) else None
        if not isinstance(steps, list):
            raise ValueError("no steps")
    except (OSError, ValueError):
        index.unreadable += 1
        return []
    return [s for s in steps if isinstance(s, dict)]


def _dated(steps: list[dict[str, Any]], name: str) -> str | None:
    for s in steps:
        if s.get("name") == name and _valid(s.get("at")):
            return str(s["at"])
    return None


def _closed_cr(store: Any, batch: str, c: dict[str, Any], index: _Index) -> None:
    result = c.get("result")
    if result not in {"merged", "dropped"}:
        return
    base = {
        "cr": c.get("cr"),
        "title": subject(str(c.get("title") or "")),
        "batch": batch,
        "pr": c.get("pr") or None,
        "folder": c.get("archive") or None,
    }
    tail = {
        "rounds": c.get("rounds"),
        "cost_usd": c.get("cost_usd"),
        "cost_unpriced": c.get("cost_unpriced") or {},
    }
    if "ended" in c:  # a record written with the times
        index.add("opened", c.get("shipped"), base)
        end = c.get("ended")
        if result == "merged" and c.get("kind") == "release":
            done = index.add("release", end, base, **tail, version=c.get("version"))
        elif result == "merged":
            done = index.add("merged", end, base, **tail)
        else:
            done = index.add("dropped", end, base, **tail, to=c.get("to"))
        index.undated += not done
        return
    steps = _steps(store, c.get("archive"), index)
    index.add("opened", _dated(steps, "Shipped"), base)
    # no step says when an older record's CR was dropped
    done = result == "merged" and index.add("merged", _dated(steps, "Merged"), base, **tail)
    index.undated += not done


def _running(repo: Repo, state: dict[str, Any], index: _Index) -> None:
    folders = repo.batch_folders()
    if not folders:
        return
    try:
        d = read_batch_json(repo.store, folders[0] / "batch.json")
        events = read_events(repo.store, folders[0])
    except (OSError, ValueError, ChantierError):
        index.unreadable += 1
        return
    rows = {r["cr"]: r for r in (state.get("batch") or {}).get("crs", [])}
    for c in d.crs:
        own = [e for e in events if e.cr == c.id]
        row = rows.get(c.id) or {}
        base = {
            "cr": c.id,
            "title": row.get("title") or subject(c.title),
            "batch": d.id,
            "pr": c.shown_pr(),
            "folder": row.get("folder"),
        }
        tail = {"rounds": c.round, "cost_usd": c.cost_usd, "cost_unpriced": c.cost_unpriced}
        ship = next((e for e in own if e.kind == "ship"), None)
        if ship:
            index.add("opened", ship.t, base)
        if c.status not in {"merged", "cancelled"}:
            continue
        end = ended(own, c)
        if c.status == "cancelled":
            done = index.add("dropped", end, base, **tail, to=c.left_to or TRASH)
        elif c.kind == "release":
            done = index.add("release", end, base, **tail, version=c.released)
        else:
            done = index.add("merged", end, base, **tail)
        index.undated += not done


def _build(project: Project, state: dict[str, Any]) -> dict[str, Any]:
    repo = project.repo
    index = _Index()
    history = [r for r in state.get("history") or [] if isinstance(r, dict)]
    with repo.store.reading():
        names = repo.store.glob(RECORDS.as_posix(), "batch-*.json")
        read = {str(r.get("batch")) for r in history}
        index.unreadable += sum(1 for n in names if n.removesuffix(".json") not in read)
        for record in history:
            if record.get("state") == "closed":
                _closed_record(repo.store, record, index)
        _running(repo, state, index)
    return index.data()


def _closed_record(store: Any, record: dict[str, Any], index: _Index) -> None:
    for c in record.get("crs") or []:
        if isinstance(c, dict):
            _closed_cr(store, str(record.get("batch")), c, index)


def index_of(ctx: Context, project: Project) -> dict[str, Any]:
    """The project's index of dated events, rebuilt only when the state's print changes."""
    state, print_ = reads.state_of(ctx, project, ask=False)
    kept = ctx.history.get(project.id)
    if kept and kept[0] == print_:
        return kept[1]
    found = _build(project, state)
    ctx.history[project.id] = (print_, found)
    return found


def _bounds(period: str, day: date) -> tuple[date, date, date, date]:
    """The period's first and last local day, and the first days of the periods before and after."""
    if period == "day":
        return day, day, day - timedelta(days=1), day + timedelta(days=1)
    if period == "week":
        first = day - timedelta(days=day.weekday())
        return (
            first,
            first + timedelta(days=6),
            first - timedelta(days=7),
            first + timedelta(days=7),
        )
    first = day.replace(day=1)
    after = (first + timedelta(days=31)).replace(day=1)
    return first, after - timedelta(days=1), (first - timedelta(days=1)).replace(day=1), after


def day_bounds(zone: ZoneInfo, day: date) -> tuple[datetime, datetime]:
    """The local day's limits as UTC instants, `[from, to)`."""
    start = datetime(day.year, day.month, day.day, tzinfo=zone).astimezone(UTC)
    nxt = day + timedelta(days=1)
    return start, datetime(nxt.year, nxt.month, nxt.day, tzinfo=zone).astimezone(UTC)


def _counts() -> dict[str, int]:
    return {"merged": 0, "dropped": 0, "opened": 0, "releases": 0}


ALL = "*"  # the address of "All projects": every project of the surface


def _tagged(ctx: Context, projects: list[Project]) -> dict[str, Any]:
    """The events of every project, each with its `project` (the kept index is not touched), and the
    sums of its counts."""
    events: list[dict[str, Any]] = []
    undated = unreadable = 0
    for p in projects:
        found = index_of(ctx, p)
        events += [{**e, "project": p.id} for e in found["events"]]
        undated += found["undated"]
        unreadable += found["unreadable"]
    return {"events": events, "undated": undated, "unreadable": unreadable}


def feed(ctx: Context, projects: list[Project], rows: int) -> list[dict[str, Any]]:
    """The newest `rows` events of the projects, newest first, as the Home's feed shows them: what
    was done and when. An event's cost and rounds are the History's (private) and are left out."""
    found = sorted(
        _tagged(ctx, projects)["events"],
        key=lambda e: (e["at"], str(e["cr"]), e["kind"], e["project"]),
        reverse=True,
    )[:rows]
    return [
        {k: e[k] for k in ("project", "kind", "at", "cr", "title", "batch", "pr")} for e in found
    ]


def answer(
    ctx: Context, project: Project | list[Project], period: str, on: str | None, tz: str
) -> dict[str, Any]:
    """The period's events by local day, its totals and the counts that no period holds. A list of
    projects answers for all of them at once: each event then carries its `project`."""
    zone = ZoneInfo(tz)
    today = clock.parse(clock.now()).astimezone(zone).date()
    first, last, before, after = _bounds(period, date.fromisoformat(on) if on else today)
    start, stop = day_bounds(zone, first)[0], day_bounds(zone, last)[1]
    holds = first <= today <= last
    found = _tagged(ctx, project) if isinstance(project, list) else index_of(ctx, project)
    days: dict[str, list[dict[str, Any]]] = {}
    for e in found["events"]:
        at = clock.parse(e["at"])
        if start <= at < stop:
            days.setdefault(at.astimezone(zone).date().isoformat(), []).append(e)
    totals = _counts()
    cost, partial = 0.0, False
    shown = []
    for day in sorted(days, reverse=True):
        items = sorted(days[day], key=lambda e: (e["at"], str(e["cr"]), e["kind"]), reverse=True)
        counts = _counts()
        for e in items:
            key = "releases" if e["kind"] == "release" else e["kind"]
            counts[key] += 1
            totals[key] += 1
            if e["kind"] in ENDING:
                price = e.get("cost_usd")
                cost += price or 0.0
                partial = partial or price is None or bool(e.get("cost_unpriced"))
        shown.append({"day": day, "counts": counts, "items": items})
    return {
        "period": period,
        "date": first.isoformat(),
        "end": last.isoformat(),
        "tz": tz,
        "from": start.strftime(clock.FORMAT),
        "to": stop.strftime(clock.FORMAT),
        "today": today.isoformat(),
        "holds_today": holds,
        "prev": before.isoformat(),
        "next": None if holds or first > today else after.isoformat(),
        "totals": {**totals, "cost_usd": round(cost, 4), "cost_partial": partial},
        "days": shown,
        "undated": found["undated"],
        "unreadable": found["unreadable"],
        "now": clock.now(),
    }

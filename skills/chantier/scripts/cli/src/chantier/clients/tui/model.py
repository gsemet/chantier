"""The screen's data of `chantier live`: a plain object fed with each item of the link, with no
Rich and no network in it.

From `board`: the projects and the server's version and folder served. From `project`: the batch's
CR rows, its `stack_lease` and slots, and the record's last 40 events. From `events`: the journal
lines. The flow keeps the last 200 lines of every project shown, by time. "Now" is the server's:
the `now` of the last frame plus the time elapsed since on the local monotonic clock, so a
machine with a wrong clock shows the right time left."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from chantier.clients.tui.link import Event, Idle, Linked, Refused, Wanted

WATCHED = 15  # projects watched at most
FLOW = 200  # lines the flow keeps
FORMAT = "%Y-%m-%dT%H:%M:%SZ"
SECONDS = 60
EVENT_DETAILS = ("result", "round", "order_kind", "reason", "note")


def parse(ts: Any) -> datetime | None:
    try:
        return datetime.strptime(str(ts), FORMAT).replace(tzinfo=UTC)
    except ValueError:
        return None


def hms(ts: Any) -> str:
    """`HH:MM:SS` of a chantier time (UTC), as every chantier text shows it."""
    text = str(ts or "")
    return text[11:19] if len(text) >= 19 else "--:--:--"  # noqa: PLR2004 - ISO 8601 slots


def lease_left(lease: dict[str, Any] | None, now: datetime) -> str | None:
    """The time left of a lease from its facts: none when it ended (or never was); `mm:ss`
    while it expires after now; else its gate's word, else
    `not confirmed <n> min`, the words of the CLI's leases."""
    if not lease or lease.get("ended"):
        return None
    expires = parse(lease.get("expires"))
    if expires is None:
        return None
    left = (expires - now).total_seconds()
    if left > 0:
        whole = int(left)
        return f"{whole // SECONDS:02d}:{whole % SECONDS:02d}"
    if lease.get("gate"):
        return str(lease["gate"])
    return f"not confirmed {int(-left // SECONDS)} min"


def age(since: Any, now: datetime) -> str:
    """How long ago: `<m>m`, or `<h>h<mm>m` past an hour."""
    at = parse(since)
    if at is None:
        return ""
    minutes = max(0, int((now - at).total_seconds() // SECONDS))
    if minutes < SECONDS:
        return f"{minutes}m"
    return f"{minutes // SECONDS}h{minutes % SECONDS:02d}m"


@dataclass(frozen=True)
class Line:
    """One line of the flow."""

    t: str
    project: str
    who: str
    text: str


def record_text(e: dict[str, Any]) -> str:
    """A record event as a line's text: its kind, its CR, and what it has of result, round,
    order kind, reason or note."""
    parts = [str(e.get("kind") or "")]
    if e.get("cr"):
        parts.append(str(e["cr"]))
    for k in EVENT_DETAILS:
        if e.get(k) is not None:
            value = e[k]
            parts.append(f"r{value}" if k == "round" else str(value))
    if e.get("pr"):
        parts.append(str(e["pr"]))
    return " ".join(p for p in parts if p)


@dataclass
class Model:
    """What the screen shows, fed by `feed`."""

    only: list[str] = field(default_factory=list)
    clock: Callable[[], float] = time.monotonic
    board: dict[str, Any] | None = None
    states: dict[str, dict[str, Any]] = field(default_factory=dict)
    journals: set[str] = field(default_factory=set)  # projects whose `events` answered
    dropped: set[str] = field(default_factory=set)
    flow: list[Line] = field(default_factory=list)
    records: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    transport: str | None = None
    lost_at: str | None = None  # the server's time the link was lost, None while live
    server_now: str | None = None
    at: float = 0.0

    # the link's items

    def feed(self, item: Any) -> None:
        now = getattr(item, "now", None)
        if isinstance(now, str) and parse(now):
            self.server_now, self.at = now, self.clock()
        if isinstance(item, Linked):
            self._linked(item)
        elif isinstance(item, Refused):
            self._refused(item.key)
        elif isinstance(item, Event):
            self._event(item)
        elif not isinstance(item, Idle):
            raise TypeError(item)

    def _linked(self, item: Linked) -> None:
        if item.transport is not None:
            self.transport, self.lost_at = item.transport, None
        elif self.lost_at is None:
            self.lost_at = self.now().strftime(FORMAT)

    def _refused(self, key: str) -> None:
        topic, _, project = key.partition(":")
        if topic in ("project", "events") and project:
            self.dropped.add(project)
            self.states.pop(project, None)
            self.journals.discard(project)

    def _event(self, item: Event) -> None:
        topic, _, project = item.key.partition(":")
        if topic == "board":
            self.board = item.data
        elif topic == "project" and project:
            self.states[project] = item.data
            self._records(project, list(item.data.get("events") or []))
        elif topic == "events" and project:
            self.journals.add(project)
            for x in item.data.get("lines") or []:
                text = x.get("text") or x.get("type") or ""
                self._add(Line(str(x.get("t") or ""), project, str(x.get("source") or ""), text))

    def _records(self, project: str, events: list[dict[str, Any]]) -> None:
        """The record events after the last one already shown (the whole object matched); at the
        first `project` event, the recorded ones fill the flow."""
        before = self.records.get(project)
        if before is None:
            new = events
        elif before and before[-1] in events:
            at = len(events) - 1 - events[::-1].index(before[-1])
            new = events[at + 1 :]
        else:
            new = [e for e in events if e not in before]
        self.records[project] = events
        for e in new:
            who = str(e.get("actor") or "")
            self._add(Line(str(e.get("t") or ""), project, who, record_text(e)))

    def _add(self, line: Line) -> None:
        self.flow.append(line)
        self.flow.sort(key=lambda x: x.t)  # stable: lines of one time keep their order
        del self.flow[:-FLOW]

    # what is watched

    def projects(self) -> list[dict[str, Any]]:
        """The board's project lines, in its order."""
        found = (self.board or {}).get("projects") or []
        return [p for p in found if isinstance(p, dict) and isinstance(p.get("id"), str)]

    def unknown_only(self) -> list[str]:
        """The `--only` ids the board does not serve (once the board is known)."""
        if self.board is None:
            return []
        served = {p["id"] for p in self.projects()}
        return [x for x in self.only if x not in served]

    def watched(self) -> list[str]:
        ids = [p["id"] for p in self.projects() if p["id"] not in self.dropped]
        if self.only:
            ids = [x for x in ids if x in self.only]
        return ids[:WATCHED]

    def not_watched(self) -> list[str]:
        if self.only:
            return []
        return [p["id"] for p in self.projects() if p["id"] not in self.dropped][WATCHED:]

    def wanted(self) -> list[Wanted]:
        """`board`, then `project` and `events` of each project watched."""
        out: list[Wanted] = [("board", "board", {})]
        for p in self.watched():
            out.append((f"project:{p}", "project", {"project": p}))
            out.append((f"events:{p}", "events", {"project": p}))
        return out

    def missing(self) -> list[str]:
        """The first answers not received yet: `board`, `project <id>`, `events <id>`."""
        if self.board is None:
            return ["board"]
        out = [f"project {p}" for p in self.watched() if p not in self.states]
        return out + [f"events {p}" for p in self.watched() if p not in self.journals]

    # what is drawn

    def now(self) -> datetime:
        """The server's time now."""
        at = parse(self.server_now)
        if at is None:
            return datetime.now(UTC)
        return at + timedelta(seconds=max(0.0, self.clock() - self.at))

    def batch(self, project: str) -> dict[str, Any] | None:
        found = (self.states.get(project) or {}).get("batch")
        return found if isinstance(found, dict) else None

    def rows(self) -> list[tuple[str, dict[str, Any]]]:
        """The CR rows of the running batches of the projects watched, with their project."""
        out = []
        for p in self.watched():
            b = self.batch(p)
            if b and b.get("state") == "running":
                out += [(p, r) for r in b.get("crs") or [] if isinstance(r, dict)]
        return out

    def counts(self) -> dict[str, int]:
        rows = [r for _, r in self.rows()]
        return {
            "working": sum(1 for r in rows if r.get("state") == "working"),
            "ready": sum(1 for r in rows if r.get("to_review")),
            "held": sum(1 for r in rows if r.get("state") == "blocked"),
            "done": sum(1 for r in rows if r.get("state") == "merged"),
        }

    def agents(self) -> list[tuple[str, str]]:
        """One line per unit held: `Driver <cr> <phase>` per working CR, `Stack driver` while the
        stack's lease has not ended."""
        out = []
        for p in self.watched():
            b = self.batch(p)
            if not b or b.get("state") != "running":
                continue
            for r in b.get("crs") or []:
                if r.get("state") == "working":
                    out.append((p, f"Driver {r.get('cr')} {r.get('phase') or ''}".rstrip()))
            stack = b.get("stack_lease")
            if isinstance(stack, dict) and not stack.get("ended"):
                out.append((p, "Stack driver"))
        return out

    def ready_count(self, project: str) -> int | None:
        found = ((self.states.get(project) or {}).get("backlog") or {}).get("3-ready")
        return len(found) if isinstance(found, list) else None

    def link_word(self) -> str:
        if self.lost_at is not None:
            return f"reconnecting since {hms(self.lost_at)}"
        return "live" if self.transport else "connecting"

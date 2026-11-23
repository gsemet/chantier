"""The screen's data of `chantier live`: a plain object fed with each item of the link, with no
Rich and no network in it.

From `board`: the projects and the server's version and folder served. From `project`: the batch's
CR rows, its `stack_lease` and slots, and the record's last 40 events. From `events`: the journal
lines. From `prs`: the batch's PRs as the forge says them. The flow keeps the last 2000 lines of
every project shown, by time (per board: with several boards the screen merges the boards' flows).
"Now" is the server's: the `now` of the last frame plus the time elapsed since on the local
monotonic clock, so a machine with a wrong clock shows the right time left. Every clock time the
screen draws is in the local zone (`zone`, the system's when None)."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, tzinfo
from typing import Any

from chantier.clients.tui.link import Event, Idle, Linked, Refused, Wanted
from chantier.clients.tui.times import FORMAT, NO_TIME, SECONDS, offset_text, parse

WATCHED = 15  # projects watched at most
FLOW = 2000  # lines the flow keeps, per board
SEAT = "Chief of Staff (seat)"
LATE = "  late"
BEAT_LATE_MARGIN = 5  # minutes past the steering wake before the heartbeat is late
EVENT_DETAILS = ("result", "round", "order_kind", "reason", "note")


@dataclass(frozen=True)
class Line:
    """One line of the flow."""

    t: str
    project: str
    who: str
    text: str
    cr: str = ""
    board: str = ""  # the label of its board when several are watched, else empty

    def holds(self, text: str) -> bool:
        """Whether the text (any case) is in the board label, project, CR, who or text."""
        if not text:
            return True
        label = f"{self.board}/{self.project}" if self.board else ""
        found = (self.board, self.project, label, self.cr, self.who, self.text)
        return any(text.casefold() in x.casefold() for x in found)


def merged(models: list[Model]) -> list[Line]:
    """The flows of the boards, by time (stable: lines of one time keep their order)."""
    return sorted((line for m in models for line in m.flow), key=lambda x: x.t)


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
    label: str = ""  # `a`..`d` with several boards, else empty
    base: str = ""  # the board's base address
    zone: tzinfo | None = None  # the zone times are drawn in; None: the system's local zone
    prs: dict[str, dict[str, Any]] = field(default_factory=dict)  # `prs` answers, by project

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

    @staticmethod
    def _prs_project(rest: str) -> str:
        """The project of a `prs:<project>:<batch>` key: between the first and the last `:`."""
        return rest.rpartition(":")[0]

    def _refused(self, key: str) -> None:
        topic, _, project = key.partition(":")
        if topic == "prs":
            self.prs.pop(self._prs_project(project), None)
        elif topic in ("project", "events") and project:
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
        elif topic == "prs" and self._prs_project(project):
            self.prs[self._prs_project(project)] = item.data
        elif topic == "events" and project:
            self.journals.add(project)
            for x in item.data.get("lines") or []:
                text = x.get("text") or x.get("type") or ""
                who, cr = str(x.get("source") or ""), str(x.get("cr") or "")
                self._add(Line(str(x.get("t") or ""), project, who, text, cr, self.label))

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
            cr = str(e.get("cr") or "")
            self._add(Line(str(e.get("t") or ""), project, who, record_text(e), cr, self.label))

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

    def named(self, project: str) -> str:
        """A project as the screen names it: `<label>/<project>` with several boards."""
        return f"{self.label}/{project}" if self.label else project

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
        """`board`, then `project` and `events` of each project watched, and `prs` of each one
        whose state holds a batch in `4-batch/` (its key names the batch, so a new batch is a new
        subscription)."""
        out: list[Wanted] = [("board", "board", {})]
        for p in self.watched():
            out.append((f"project:{p}", "project", {"project": p}))
            out.append((f"events:{p}", "events", {"project": p}))
            batch = self.batch_id(p)
            if batch:
                out.append((f"prs:{p}:{batch}", "prs", {"project": p, "batch": batch}))
        return out

    def missing(self) -> list[str]:
        """The first answers not received yet: `board`, `project <id>`, `events <id>` (never the
        `prs` ones: see `pending_prs`)."""
        if self.board is None:
            return ["board"]
        out = [f"project {p}" for p in self.watched() if p not in self.states]
        return out + [f"events {p}" for p in self.watched() if p not in self.journals]

    def pending_prs(self) -> list[str]:
        """The `prs` subscriptions not answered yet, as `prs <id>`."""
        out = []
        for p in self.watched():
            batch = self.batch_id(p)
            answer = self.prs.get(p)
            if batch and (answer is None or answer.get("batch") not in (None, batch)):
                out.append(f"prs {p}")
        return out

    # what is drawn

    def now(self) -> datetime:
        """The server's time now."""
        at = parse(self.server_now)
        if at is None:
            return datetime.now(UTC)
        return at + timedelta(seconds=max(0.0, self.clock() - self.at))

    def local(self, at: datetime) -> datetime:
        """An instant in the zone the screen draws in."""
        return at.astimezone(self.zone)

    def stamp(self, ts: Any) -> str:
        """`MM-DD HH:MM:SS` of a chantier time in the local zone; `----- --:--:--` when it does
        not parse."""
        at = parse(ts)
        return self.local(at).strftime("%m-%d %H:%M:%S") if at else NO_TIME

    def clock_text(self) -> str:
        """The server's now in the local zone: `2026-11-23 12:26:25 UTC+01:00`."""
        at = self.local(self.now())
        return f"{at.strftime('%Y-%m-%d %H:%M:%S')} {offset_text(at)}"

    def batch(self, project: str) -> dict[str, Any] | None:
        found = (self.states.get(project) or {}).get("batch")
        return found if isinstance(found, dict) else None

    def batch_id(self, project: str) -> str:
        b = self.batch(project)
        return str(b["id"]) if b and isinstance(b.get("id"), str) else ""

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
        """The sessions of each project watched: `Chief of Staff (seat)  <title>`, `Foreman` with
        its heartbeat, a `Driver <cr> <phase>` per working CR, `Stack driver` while the stack's
        lease has not ended. The seat line says who holds the seat, not that it runs."""
        out = []
        for p in self.watched():
            seat = (self.states.get(p) or {}).get("seat")
            if isinstance(seat, dict):
                title = str(seat.get("title") or "")
                out.append((p, f"{SEAT}  {title}" if title else SEAT))
            b = self.batch(p)
            if not b or b.get("state") != "running":
                continue
            if b.get("steering") == "foreman":
                out.append((p, self._foreman(b)))
            for r in b.get("crs") or []:
                if r.get("state") == "working":
                    out.append((p, f"Driver {r.get('cr')} {r.get('phase') or ''}".rstrip()))
            stack = b.get("stack_lease")
            if isinstance(stack, dict) and not stack.get("ended"):
                out.append((p, "Stack driver"))
        return out

    def _foreman(self, b: dict[str, Any]) -> str:
        if b.get("heartbeat_stopped"):
            return "Foreman  heartbeat stopped"
        beat = parse(b.get("heartbeat"))
        if beat is None:
            return "Foreman"
        minutes = max(0, round((self.now() - beat).total_seconds() / SECONDS))
        text = f"Foreman  beat {minutes} min ago"
        wake = b.get("steering_wake_min")
        if isinstance(wake, int) and minutes > wake + BEAT_LATE_MARGIN:
            text += LATE
        return text

    # Ready

    def review(self) -> list[tuple[str, dict[str, Any]]]:
        """The CRs to review of the running and paused batches watched, with their project, in
        the batch's merge order (the others after, as listed)."""
        out = []
        for p in self.watched():
            b = self.batch(p)
            if not b or b.get("state") not in ("running", "paused"):
                continue
            rows = [r for r in b.get("crs") or [] if isinstance(r, dict) and r.get("to_review")]
            order = [str(x) for x in b.get("merge_order") or []]
            rows.sort(key=lambda r: order.index(r["cr"]) if r.get("cr") in order else len(order))
            out += [(p, r) for r in rows]
        return out

    def has_batch(self) -> bool:
        return any(self.batch_id(p) for p in self.watched())

    def pr_of(self, project: str, cr: str) -> dict[str, Any] | None:
        """The forge's row of a CR's PR from the project's `prs` answer, None when it has none."""
        answer = self.prs.get(project) or {}
        if answer.get("batch") not in (None, self.batch_id(project)):
            return None
        return next((x for x in answer.get("rows") or [] if x.get("cr") == cr), None)

    def prs_error(self) -> str:
        """The forge error of the first project that has one, on one line."""
        for p in self.watched():
            error = (self.prs.get(p) or {}).get("error")
            if error:
                return " ".join(str(error).split())
        return ""

    def ready_count(self, project: str) -> int | None:
        found = ((self.states.get(project) or {}).get("backlog") or {}).get("3-ready")
        return len(found) if isinstance(found, list) else None

    def link_word(self) -> str:
        if self.lost_at is not None:
            at = parse(self.lost_at)
            time_ = self.local(at).strftime("%H:%M:%S") if at else "--:--:--"
            return f"reconnecting since {time_}"
        return "live" if self.transport else "connecting"

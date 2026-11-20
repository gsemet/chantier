"""The API's topics: what a client watches. Each topic's `read(ctx, args, last)` gives the rev
of its whole value now and the value, or no value when the rev is `last` (nothing to send); None
for a project the server does not serve. The push loop and a long-poll call it."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from chantier.board import costs, journal, prs, reads
from chantier.board.api import ops, times
from chantier.board.context import Context
from chantier.board.projects import Project
from chantier.core import clock
from chantier.hub import journal as forge_journal
from chantier.hub import schemas

Reading = tuple[str, dict[str, Any] | None] | None
Read = Callable[[Context, Any, str | None], Reading]


def _hash(*parts: Any) -> str:
    text = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def _unchanged(rev: str, last: str | None, value: Callable[[], dict[str, Any]]) -> Reading:
    return (rev, None) if rev == last else (rev, value())


def _on_project(read: Callable[[Context, Project, Any, str | None], Reading]) -> Read:
    def run(ctx: Context, a: Any, last: str | None) -> Reading:
        project = reads.found(ctx, a.project)
        return None if project is None else read(ctx, project, a, last)

    return run


def _board(ctx: Context, a: Any, last: str | None) -> Reading:
    data = reads.board_data(ctx)
    return _unchanged(_hash(data["projects"], data["seats"], data["writer"]), last, lambda: data)


def _project(ctx: Context, project: Project, a: Any, last: str | None) -> Reading:
    state, print_ = reads.state_of(ctx, project, ask=True)
    return _unchanged(print_, last, lambda: {**state, "rev": print_, "now": clock.now()})


def _costs(ctx: Context, project: Project, a: Any, last: str | None) -> Reading:
    state, _ = reads.state_of(ctx, project, ask=True)
    recorded, live = costs.recorded(state), ctx.live(project)
    rev = _hash(live.mark(), recorded)
    return _unchanged(
        rev,
        last,
        lambda: {"recorded": recorded, "live": live.snapshot(), "now": clock.now()},
    )


def _answer(ctx: Context, project: Project, batch: str | None) -> dict[str, Any]:
    """The PRs' answer; a batch whose PRs are all done (or a closed one) is not read again
    until a PR joins it."""
    state, _ = reads.state_of(ctx, project, ask=False)
    shown, links = prs.watched(state, batch)
    key = (project.id, str(shown))
    kept = ctx.prs_done.get(key)
    if kept and kept[0] == links:
        return kept[1]
    found = prs.answer(ctx.reads, project.id, state, project.repo, batch)
    if found["all_done"] or found["closed"]:
        ctx.prs_done[key] = (links, found)
    else:
        ctx.prs_done.pop(key, None)
    return found


def _prs(ctx: Context, project: Project, a: Any, last: str | None) -> Reading:
    found = _answer(ctx, project, a.batch)
    rev = _hash({k: v for k, v in found.items() if k != "now"})
    return _unchanged(rev, last, lambda: found)


def _journal(ctx: Context, project: Project, a: Any, last: str | None) -> Reading:
    path = project.repo.changes / journal.FILE
    try:
        info = path.stat()
        rev = f"{info.st_size}:{info.st_mtime_ns}"
    except OSError:
        rev = "-"
    return _unchanged(rev, last, lambda: ops.journal_data(project))


def _entries(ctx: Context, changes: Path) -> list[dict[str, Any]]:
    """The forge journal's lines, read again only when the file's size or time moved."""
    path = changes / forge_journal.FILE
    try:
        info = path.stat()
    except OSError:
        return []
    mark = (info.st_size, info.st_mtime_ns)
    kept = ctx.journal_seen.get(path)
    if kept is None or kept[0] != mark:
        kept = ctx.journal_seen[path] = (mark, forge_journal.read(changes)[0])
    return kept[1]


def _told(entry: dict[str, Any]) -> dict[str, Any]:
    """The line with `text`, its type's sentence, when the type is published and its payload is
    accepted; as it is otherwise (an unknown type, a newer version, a refused payload)."""
    type_ = entry.get("type")
    found = schemas.PUBLISHED.get(type_) if isinstance(type_, str) else None
    if found is None or forge_journal.newer(entry) or not entry.get("audience"):
        return entry
    payload = {k: v for k, v in entry.items() if k not in forge_journal.HEADER}
    if schemas.check(type_, payload) is not None:
        return entry
    return {**entry, "text": found.text(entry)}


def _events(ctx: Context, project: Project, a: Any, last: str | None) -> Reading:
    entries = _entries(ctx, project.repo.changes)
    if last is not None and last.isdigit():
        cursor = int(last)
    else:
        cursor = a.after if a.after is not None else forge_journal.last_seq(entries)
    lines = sorted(
        (e for e in entries if type(e.get("seq")) is int and e["seq"] > cursor), key=_seq
    )
    lines = lines[: times.MAX_LINES]
    rev = str(lines[-1]["seq"] if lines else cursor)
    if last is not None and not lines:
        return rev, None
    return rev, {"lines": [_told(e) for e in lines]}


def _seq(entry: dict[str, Any]) -> int:
    return int(entry["seq"])


READS: dict[str, Read] = {
    "board": _board,
    "project": _on_project(_project),
    "costs": _on_project(_costs),
    "prs": _on_project(_prs),
    "journal": _on_project(_journal),
    "events": _on_project(_events),
}


def read(ctx: Context, name: str, a: Any, last: str | None) -> Reading:
    return READS[name](ctx, a, last)

"""Writing the STATUS files and the dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from chantier import __version__
from chantier.board.address import local_url, url
from chantier.core import clock
from chantier.core.files import rel_in, write_file
from chantier.core.records import BatchRecord, EventRecord, read_events
from chantier.core.repo import Repo
from chantier.hub import lock, state
from chantier.status.markdown import batch_markdown, cr_markdown, dashboard_markdown
from chantier.status.views import batch_view, cr_view, dashboard_view


def _write(folder: Path, markdown: str, view: dict[str, Any]) -> None:
    write_file(folder / "STATUS.md", markdown)
    write_file(folder / "STATUS.json", json.dumps(view, indent=2, ensure_ascii=False) + "\n")


def _events_by_cr(repo: Repo, folder: Path) -> dict[str, list[EventRecord]]:
    events: dict[str, list[EventRecord]] = {}
    for e in read_events(repo.store, folder):
        if e.cr:
            events.setdefault(e.cr, []).append(e)
    return events


def write_batch(repo: Repo, d: BatchRecord, folder: Path) -> None:
    """Rewrite the batch's file and each of its CRs', wherever they are."""
    events = _events_by_cr(repo, folder)
    for c in d.crs:
        cr_folder = repo.planning_path(c.path) if c.path else None
        if cr_folder and repo.store.is_dir(rel_in(repo.store.root, cr_folder)):
            where = (cr_folder, events.get(c.id, []), cr_folder.parent.parent == folder)
            v = cr_view(repo, d, c, where)
            _write(cr_folder, cr_markdown(v), v)
    v = batch_view(repo, d, folder)
    _write(folder, batch_markdown(v), v)


def write_final_pages(repo: Repo, d: BatchRecord, folder: Path) -> None:
    """At `close` only, once the cost is priced: the CR pages that outlive the batch's files
    (the archived ones) say their cost is final. Nothing before `close` may say so."""
    d = d.model_copy(update={"closing": True})
    events = _events_by_cr(repo, folder)
    for c in d.crs:
        cr_folder = repo.planning_path(c.path) if c.path else None
        if (
            cr_folder
            and repo.store.is_dir(rel_in(repo.store.root, cr_folder))
            and folder not in cr_folder.parents
            and not c.moved_to()  # moved to the backlog or `3-ready`: no final page there
        ):
            v = cr_view(repo, d, c, (cr_folder, events.get(c.id, []), False))
            _write(cr_folder, cr_markdown(v), v)


def _build_note(entry: dict[str, Any]) -> str | None:
    """One clause when the server runs another version or another build than this CLI."""
    if found := state.other_version(entry, __version__):
        return f"server is chantier {found}, this is chantier {__version__}"
    if found := state.other_build(entry, __version__, state.build_source()):
        return f"server runs another build of chantier {__version__} ({found})"
    return None


def _picked(entry: dict[str, Any] | None, names: tuple[str, ...]) -> dict[str, Any] | None:
    return None if entry is None else {n: entry.get(n) for n in names}


def services_view(repo: Repo) -> dict[str, Any]:
    """A snapshot of this machine's chantier processes for the planning surface, taken now. It
    holds no key: the keys stay in `server.json`."""
    git_dir = repo.git_dir
    server = state.live_entry(git_dir, state.SERVER)
    if server is not None:
        host, port = server["host"], server["port"]
        server = {
            **{n: server.get(n) for n in ("pid", "version", "source", "started", "host", "port")},
            "url": url(host, port),
            "local_url": local_url(host, port),
            "build_note": _build_note(server),
        }
    writer = state.live_entry(git_dir, state.WRITER)
    hub = _picked(state.live_entry(git_dir, state.HUB), ("pid", "version", "started", "idle"))
    if hub is not None:
        hub["idle"] = bool(hub["idle"])
    return {
        "at": clock.now(),
        "server": server,
        "hub": hub,
        "writer": _picked(writer, ("pid", "state", "text")),
        "watchers": lock.watchers(git_dir, (repo.project_dir or repo.root).name),
    }


def write_dashboard(repo: Repo, paths: dict[str, Path]) -> None:
    v = {**dashboard_view(repo, paths), "services": services_view(repo)}
    repo.changes.mkdir(parents=True, exist_ok=True)
    _write(repo.changes, dashboard_markdown(v), v)

"""Writing the STATUS files and the dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from chantier.core.files import write_file
from chantier.core.records import read_events
from chantier.core.repo import Repo
from chantier.status.markdown import batch_markdown, cr_markdown, dashboard_markdown
from chantier.status.views import batch_view, cr_view, dashboard_view


def _write(folder: Path, markdown: str, view: dict[str, Any]) -> None:
    write_file(folder / "STATUS.md", markdown)
    write_file(folder / "STATUS.json", json.dumps(view, indent=2, ensure_ascii=False) + "\n")


def write_batch(repo: Repo, d: dict[str, Any], folder: Path) -> None:
    """Rewrite the batch's file and each of its CRs', wherever they are."""
    events: dict[str, list[dict[str, Any]]] = {}
    for e in read_events(folder):
        if e.get("cr"):
            events.setdefault(e["cr"], []).append(e)
    for c in d["crs"]:
        cr_folder = repo.planning_path(c["path"]) if c.get("path") else None
        if cr_folder and cr_folder.is_dir():
            where = (cr_folder, events.get(c["id"], []), cr_folder.parent.parent == folder)
            v = cr_view(repo, d, c, where)
            _write(cr_folder, cr_markdown(v), v)
    v = batch_view(repo, d, folder)
    _write(folder, batch_markdown(v), v)


def write_final_pages(repo: Repo, d: dict[str, Any], folder: Path) -> None:
    """At `close` only, once the cost is priced: the CR pages that outlive the batch's files
    (the archived ones) say their cost is final. Nothing before `close` may say so."""
    d = {**d, "closing": True}
    events: dict[str, list[dict[str, Any]]] = {}
    for e in read_events(folder):
        if e.get("cr"):
            events.setdefault(e["cr"], []).append(e)
    for c in d["crs"]:
        cr_folder = repo.planning_path(c["path"]) if c.get("path") else None
        if cr_folder and cr_folder.is_dir() and folder not in cr_folder.parents:
            v = cr_view(repo, d, c, (cr_folder, events.get(c["id"], []), False))
            _write(cr_folder, cr_markdown(v), v)


def write_dashboard(repo: Repo, paths: dict[str, Path]) -> None:
    v = dashboard_view(repo, paths)
    repo.changes.mkdir(parents=True, exist_ok=True)
    _write(repo.changes, dashboard_markdown(v), v)

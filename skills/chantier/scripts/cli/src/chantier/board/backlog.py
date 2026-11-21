"""The backlog's items and the one-paragraph description of a CR folder."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from chantier.core import waits
from chantier.core.files import FRONTMATTER, is_lock, rel_in, subject
from chantier.lifecycle.running_batch import MARK
from chantier.status.views import spec_state
from chantier.summaries.view import summary_view

if TYPE_CHECKING:
    from chantier.store import PlanStore

STAGES = ("inbox", "P1", "P2", "P3", "P4", "3-ready")
DESCRIPTION_LIMIT = 300
PREFERRED = ("03-change-spec.md", "01-intent.md")
MARKS = (
    (re.compile(r"!?\[([^\]]*)\]\([^)]*\)"), r"\1"),
    (re.compile(r"[`*~]+|(?<!\w)_+|_+(?!\w)"), ""),
    (re.compile(r"^\s*(?:[-+*>]|\d+\.)\s+", re.M), ""),
)


def _plain(paragraph: str) -> str:
    for pattern, repl in MARKS:
        paragraph = pattern.sub(repl, paragraph)
    return " ".join(paragraph.split())


def _first_paragraph(text: str) -> str:
    """The first paragraph that is not a heading, an `issue:` line or a code fence, after a
    frontmatter at the very start of the text."""
    text = FRONTMATTER.sub("", text.replace("\r\n", "\n"), count=1)
    for block in re.split(r"\n\s*\n", text):
        first = block.strip().splitlines()[0] if block.strip() else ""
        if first and not first.startswith(("#", "```")) and not first.lower().startswith("issue:"):
            return _plain(block)
    return ""


def _candidates(store: PlanStore, rel: str) -> list[str]:
    named = [f"{rel}/{n}" for n in PREFERRED]
    top = sorted(f"{rel}/{n}" for n in store.glob(rel, "*.md") if n not in PREFERRED)
    return named + top + sorted(f"{rel}/intake/{n}" for n in store.glob(f"{rel}/intake", "*.md"))


def description(store: PlanStore, folder: Path) -> str:
    """The first paragraph of the specification, else the intent, else the first Markdown file,
    its marks removed, cut at 300 characters."""
    for path in _candidates(store, rel_in(store.root, folder)):
        try:
            found = (
                _first_paragraph(store.read_text(path, "replace")) if store.is_file(path) else ""
            )
        except OSError:
            continue
        if found:
            return found if len(found) <= DESCRIPTION_LIMIT else found[:DESCRIPTION_LIMIT] + "…"
    return ""


def count_files(store: PlanStore, folder: Path) -> int:
    """The files under a folder, the locks left out."""
    total = 0
    for _, dirs, names in store.walk(rel_in(store.root, folder)):
        dirs[:] = [d for d in dirs if not is_lock(d)]
        total += sum(1 for n in names if not is_lock(n))
    return total


def depends_of(store: PlanStore, folder: Path) -> list[str]:
    """The `after` list of the item's `depends.json`, if it has one."""
    path = f"{rel_in(store.root, folder)}/depends.json"
    try:
        found = json.loads(store.read_text(path)).get("after", []) if store.is_file(path) else []
    except (OSError, ValueError, AttributeError):
        return []
    return [str(x) for x in found] if isinstance(found, list) else []


def grill_of(store: PlanStore, folder: Path, priority: str) -> str:
    """How far the item is: `raw`, `grill`, `specifying`, `specified` or `automatable`."""
    state = spec_state(store, folder)
    if state == "specifying":
        return "specifying"
    if state == "specified":
        return "specified"
    if priority == "3-ready":
        return "automatable"
    answers = f"{rel_in(store.root, folder)}/02-answers.md"
    return "grill" if store.is_file(answers) else "raw"


def summary_fields(store: PlanStore, folder: Path) -> dict[str, Any]:
    """What a card shows of the CR's `summary.json`: title, labels, group, origin, late summary."""
    try:
        view = summary_view(store, folder)
    except (OSError, ValueError):
        view = None
    if view is None:
        return {"title": "", "labels": [], "group": None, "origin": None, "late": False}
    origin = view.origin.model_dump(mode="json", exclude_none=True) if view.origin else None
    return {
        "title": subject(view.title),
        "labels": list(view.labels),
        "group": view.group,
        "origin": origin,
        "late": view.late,
    }


def open_waits(store: PlanStore, folder: Path) -> list[dict[str, Any]]:
    """The open waits a backlog CR's `waits.json` holds; none when there is no file or it is not
    valid (`validate` names it)."""
    try:
        return waits.open_of(waits.read_file(store, folder) or [])
    except waits.WaitsInvalid:
        return []


def running_batch_of(store: PlanStore, folder: Path, batch: str | None) -> str | None:
    """The open batch's id when the item's `work/running-batch` names it, else None: a stale mark
    (another batch's id) and no open batch give None, as `lifecycle/running_batch.py` reads it."""
    path = f"{rel_in(store.root, folder)}/work/{MARK}"
    if batch is None or not store.is_file(path):
        return None
    words = store.read_text(path, "replace").split()
    return batch if words and words[-1] == batch else None


def backlog_items(
    store: PlanStore, changes: Path, rows: list[dict[str, Any]], batch: str | None = None
) -> dict[str, list[dict[str, Any]]]:
    """The inbox, `2-backlog/P1`...`P4` and `3-ready`, by the record's own `priority` word. `batch`
    is the open batch's id: an item whose mark names it carries it as `running_batch`."""
    out: dict[str, list[dict[str, Any]]] = {k: [] for k in STAGES}
    for row in rows:
        folder = changes / row["path"]
        fields = summary_fields(store, folder)
        out[row["priority"]].append(
            {
                "item": row["item"],
                "title": fields["title"] or subject(row["title"]),
                "folder": row["path"],
                "files": count_files(store, folder),
                "depends": depends_of(store, folder),
                "description": description(store, folder),
                "grill": grill_of(store, folder, row["priority"]),
                "open_waits": open_waits(store, folder),
                "running_batch": running_batch_of(store, folder, batch),
                **{k: v for k, v in fields.items() if k != "title"},
            }
        )
    return out

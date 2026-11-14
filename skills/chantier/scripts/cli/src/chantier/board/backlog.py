"""The backlog's items and the one-paragraph description of a CR folder."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from chantier.board.files import is_lock
from chantier.core.files import read_text
from chantier.status.views import spec_state

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
    """The first paragraph that is not a heading, an `issue:` line or a code fence."""
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        first = block.strip().splitlines()[0] if block.strip() else ""
        if first and not first.startswith(("#", "```")) and not first.lower().startswith("issue:"):
            return _plain(block)
    return ""


def _candidates(folder: Path) -> list[Path]:
    named = [folder / n for n in PREFERRED]
    top = sorted(p for p in folder.glob("*.md") if p.name not in PREFERRED)
    return named + top + sorted((folder / "intake").glob("*.md"))


def description(folder: Path) -> str:
    """The first paragraph of the specification, else the intent, else the first Markdown file,
    its marks removed, cut at 300 characters."""
    for path in _candidates(folder):
        try:
            found = _first_paragraph(read_text(path, "replace")) if path.is_file() else ""
        except OSError:
            continue
        if found:
            return found if len(found) <= DESCRIPTION_LIMIT else found[:DESCRIPTION_LIMIT] + "…"
    return ""


def count_files(folder: Path) -> int:
    """The files under a folder, the locks left out."""
    total = 0
    for _, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if not is_lock(d)]
        total += sum(1 for n in names if not is_lock(n))
    return total


def depends_of(folder: Path) -> list[str]:
    """The `after` list of the item's `depends.json`, if it has one."""
    path = folder / "depends.json"
    try:
        found = json.loads(read_text(path)).get("after", []) if path.is_file() else []
    except (OSError, ValueError, AttributeError):
        return []
    return [str(x) for x in found] if isinstance(found, list) else []


def grill_of(folder: Path, priority: str) -> str:
    """How far the item is: `raw`, `grill`, `specifying`, `specified` or `automatable`."""
    state = spec_state(folder)
    if state == "specifying":
        return "specifying"
    if state == "specified":
        return "specified"
    if priority == "3-ready":
        return "automatable"
    return "grill" if (folder / "02-answers.md").is_file() else "raw"


def backlog_items(changes: Path, rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """The inbox, `2-backlog/P1`...`P4` and `3-ready`, by the record's own `priority` word."""
    out: dict[str, list[dict[str, Any]]] = {k: [] for k in STAGES}
    for row in rows:
        folder = (changes / row["path"]).resolve()
        out[row["priority"]].append(
            {
                "item": row["item"],
                "title": subject(row["title"]),
                "folder": row["path"],
                "files": count_files(folder),
                "depends": depends_of(folder),
                "description": description(folder),
                "grill": grill_of(folder, row["priority"]),
            }
        )
    return out


def subject(title: str) -> str:
    """A title without its byte-order mark, its `#` and its "Change Specification:" lead."""
    return re.sub(r"^\ufeff?[#\s]*(?:Change Specification:\s*)?", "", title or "").strip()

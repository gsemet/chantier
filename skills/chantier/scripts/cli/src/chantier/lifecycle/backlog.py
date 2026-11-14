"""The backlog's writes, role-free: file an idea, move an item between the inbox, the priorities and
`3-ready`, edit an item's Markdown, and the user's "next batch is ready" marker. The commands
(`file`, `triage`) and the board's server call these same functions with a `Repo`; each takes
`changes_lock`, rewrites the dashboard and refuses with a `ChantierError`."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from chantier.board.files import inside
from chantier.core.clock import now
from chantier.core.errors import EXIT_CONFLICT, EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.files import read_json, retry, write_bytes, write_json
from chantier.core.repo import Repo
from chantier.lifecycle.filing import new_request, shown, slugify
from chantier.lifecycle.stages import (
    PRIORITIES,
    changes_lock,
    move_backlog_item,
    stage_layout,
)
from chantier.status.write import write_dashboard

NEXT_BATCH = "next-batch.json"
TEXT_LIMIT = 1_000_000  # bytes of a Markdown file the board edits, as the board's file view cuts
NOT_IN_BACKLOG = "{} is not in the backlog (inbox, P1…P4, 3-ready)"


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def idea_slug(text: str, slug: str | None = None) -> str:
    """The slug a request is filed under: the one given, else made from the title (the first
    non-empty line); refused when the text is empty or the slug is not one."""
    if not text.strip():
        raise ChantierError("the request is empty", EXIT_USAGE)
    title = next(line.lstrip("# ").strip() for line in text.splitlines() if line.strip())
    slug = slug or slugify(title)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,80}", slug):
        raise ChantierError("CR slug: lowercase letters, digits and hyphens", EXIT_USAGE)
    return slug


def file_idea(
    repo: Repo, text: str, slug: str | None = None, raw: bytes | None = None
) -> list[str]:
    """File a request in the inbox, kept as received (`raw`, else `text` in UTF-8)."""
    slug = idea_slug(text, slug)
    with changes_lock(repo):
        folder = new_request(repo, slug, text.encode("utf-8") if raw is None else raw)
        write_dashboard(repo, stage_layout(repo))
    return [f"filed {shown(repo, folder)}; write the intent and grill the CR here"]


def move_item(repo: Repo, item: str, to: str) -> list[str]:
    """Triage: `to` is `inbox`, `P1` to `P4` or `3-ready`; `item` is the CR folder."""
    with changes_lock(repo):
        target = move_backlog_item(repo, item, to, stage_layout(repo))
        write_dashboard(repo, stage_layout(repo))
    return [f"triaged {shown(repo, target)}" + (f" ({to})" if to in PRIORITIES else "")]


def backlog_folder(repo: Repo, slug: str) -> Path:
    """The folder of a CR by its slug, among `1-inbox`, `2-backlog/P1`…`P4` and `3-ready` only: a
    CR of a batch, the archives or the trash is never found."""
    paths = stage_layout(repo)
    places = (paths["inbox"], *(paths["backlog"] / p for p in PRIORITIES), paths["ready"])
    if slug and slug == Path(slug).name and not slug.startswith("."):
        for place in places:
            if (place / slug).is_dir():
                return place / slug
    raise ChantierError(NOT_IN_BACKLOG.format(slug), EXIT_PRECONDITION)


def backlog_folders(repo: Repo) -> list[Path]:
    """Every CR folder of the inbox, the priorities and `3-ready`, each stage sorted by name."""
    paths = stage_layout(repo)
    places = (paths["inbox"], *(paths["backlog"] / p for p in PRIORITIES), paths["ready"])
    return [d for place in places if place.is_dir() for d in sorted(place.iterdir()) if d.is_dir()]


def column_of(repo: Repo, folder: Path) -> str:
    """`inbox`, `P1`…`P4` or `3-ready`: where a backlog folder is."""
    parent = folder.parent
    if parent == stage_layout(repo)["ready"]:
        return "3-ready"
    return parent.name if parent.name in PRIORITIES else "inbox"


def _editable(folder: Path, relpath: str) -> Path:
    """The Markdown file of the item that may be edited: relative, no `..`, `.md`, not
    `STATUS.md`, an existing file inside the item's folder."""
    parts = relpath.replace("\\", "/").split("/")
    name = parts[-1]
    if not relpath or ".." in parts or not name.lower().endswith(".md"):
        raise ChantierError(f"{relpath!r} is not a Markdown file of the item", EXIT_USAGE)
    if name.casefold() == "status.md":
        raise ChantierError("STATUS.md is written by chantier: it is not edited", EXIT_USAGE)
    target = inside(folder.resolve(), relpath)
    if target is None or not target.is_file():
        raise ChantierError(f"{relpath} is not a file of {folder.name}", EXIT_USAGE)
    return target


def _with_endings(text: str, old: bytes) -> bytes:
    """The text in UTF-8 with no byte-order mark, in the file's own line endings: a text that was
    mostly CRLF stays CRLF (a browser's text area hands back LF only)."""
    body = text.replace("\r\n", "\n")
    if old.count(b"\r\n") * 2 > old.count(b"\n"):
        body = body.replace("\n", "\r\n")
    return body.encode("utf-8")


def edit_markdown(repo: Repo, item: str, relpath: str, text: str, base_sha256: str) -> list[str]:
    """Replace a backlog item's Markdown file by `text`, when the file on disk still has the
    SHA-256 (of its raw bytes) the editor loaded."""
    folder = backlog_folder(repo, item)
    target = _editable(folder, relpath)
    if len(text.encode("utf-8")) > TEXT_LIMIT:
        raise ChantierError(f"the text is over {TEXT_LIMIT // 1_000_000} MB", EXIT_USAGE)
    with changes_lock(repo):
        old = retry(target.read_bytes)
        if len(old) > TEXT_LIMIT:
            raise ChantierError(f"{item}/{relpath} is over 1 MB: edit it elsewhere", EXIT_USAGE)
        if sha256_of(old) != str(base_sha256).lower():
            raise ChantierError(
                f"{item}/{relpath} changed since you opened it: reload it", EXIT_CONFLICT
            )
        write_bytes(target, _with_endings(text, old))
        write_dashboard(repo, stage_layout(repo))
    return [f"edited {item}/{relpath}"]


def next_batch(repo: Repo) -> dict[str, object] | None:
    """The marker the user wrote, or None when there is none (or it cannot be read)."""
    path = repo.changes / NEXT_BATCH
    try:
        found = read_json(path) if path.is_file() else None
    except (OSError, ValueError):
        return None
    if not isinstance(found, dict) or not isinstance(found.get("crs"), list):
        return None
    return {"declared_at": found.get("declared_at"), "crs": found["crs"]}


def declare_next_batch(repo: Repo) -> list[str]:
    """The user's word that the next batch is ready: the time and the slugs then in `3-ready`,
    read here and never taken from a page. It decides nothing."""
    with changes_lock(repo):
        ready = stage_layout(repo)["ready"]
        slugs = sorted(p.name for p in ready.iterdir() if p.is_dir()) if ready.is_dir() else []
        if not slugs:
            raise ChantierError("3-ready is empty: nothing to declare", EXIT_PRECONDITION)
        marker = next_batch(repo)
        if marker and marker["crs"] == slugs:
            raise ChantierError(
                "the next batch is already declared ready with these CRs", EXIT_PRECONDITION
            )
        write_json(repo.changes / NEXT_BATCH, {"declared_at": now(), "crs": slugs})
    return [f"next batch ready to go with: {', '.join(slugs)}"]

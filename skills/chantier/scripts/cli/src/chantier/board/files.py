"""The planning folder's files: the tree, one file's bytes, and the confinement."""

from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any

from chantier.board.reply import Reply, text
from chantier.core.files import inside, is_lock, rel_in, retry

if TYPE_CHECKING:
    from chantier.store import PlanStore

TEXT_LIMIT = 1_000_000  # bytes of a text file sent; the rest is cut
IMAGE_LIMIT = 5_000_000
TEXT = {
    ".md",
    ".json",
    ".jsonl",
    ".txt",
    ".log",
    ".yml",
    ".yaml",
    ".patch",
    ".diff",
    ".csv",
    ".html",
    ".py",
    ".sh",
    ".toml",
    ".js",
    ".css",
    ".ts",
    ".tsx",
}
IMAGES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
NOT_FOUND = "not found"
SHA_HEADER = "X-Chantier-Sha256"  # of the file's bytes on disk, sent when the text is not cut


def kind_of(name: str) -> str:
    ext = Path(name).suffix.lower()
    return "text" if ext in TEXT else "image" if ext in IMAGES else "other"


def _listed(store: PlanStore, root: Path, folder: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for here, dirs, names in store.walk(folder):
        dirs[:] = sorted(d for d in dirs if not is_lock(d))
        for name in sorted(names):
            rel = name if here == "." else f"{here}/{name}"
            try:
                real = (store.root / rel).resolve()
            except OSError:
                continue
            stat = store.stat(rel)
            if stat is None or is_lock(name) or not real.is_relative_to(root):
                continue
            if not store.is_file(rel):
                continue
            found.append({"path": rel, "size": stat[0], "kind": kind_of(name)})
    return sorted(found, key=lambda f: f["path"])


def tree(store: PlanStore, root: Path, rel: str) -> Reply | list[dict[str, Any]]:
    """Every file under a folder of the planning folder, recursively, sorted; a Reply (404)
    when the path is not a folder inside it."""
    target = root if rel in {"", "."} else inside(root, rel)
    where = rel_in(store.root, target) if target is not None else ""
    if target is None or not store.is_dir(where):
        return text(404, NOT_FOUND)
    return retry(_listed, store, root, where)


def _attachment(name: str) -> dict[str, str]:
    safe = re.sub(r"[^\w.\- ]", "_", name)
    return {"Content-Disposition": f'attachment; filename="{safe}"'}


def read(store: PlanStore, root: Path, rel: str) -> Reply:
    """One file's bytes: text as plain text (cut at 1 MB), an image with its own type, anything
    else as a download."""
    target = inside(root, rel)
    where = rel_in(store.root, target) if target is not None else ""
    stat = store.stat(where) if target is not None else None
    if target is None or stat is None or not store.is_file(where):
        return text(404, NOT_FOUND)
    kind, ext = kind_of(target.name), target.suffix.lower()
    size = stat[0]
    if kind == "text":
        raw = store.read_bytes(where, TEXT_LIMIT)
        head = (
            {"X-Chantier-Cut": "1"} if size > TEXT_LIMIT else {SHA_HEADER: sha256(raw).hexdigest()}
        )
        body = raw[:TEXT_LIMIT].decode("utf-8-sig", errors="replace").encode("utf-8")
        return Reply(200, body, "text/plain; charset=utf-8", head)
    if kind == "image" and size <= IMAGE_LIMIT:
        return Reply(200, store.read_bytes(where), IMAGES[ext])
    return Reply(200, store.read_bytes(where), "application/octet-stream", _attachment(target.name))

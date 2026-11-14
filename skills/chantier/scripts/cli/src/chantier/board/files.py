"""The planning folder's files: the tree, one file's bytes, and the confinement."""

from __future__ import annotations

import os
import re
from hashlib import sha256
from pathlib import Path
from typing import Any

from chantier.board.reply import Reply, text
from chantier.core.files import retry

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


def is_lock(name: str) -> bool:
    """The locks of a running batch: `.lock`, `.lifecycle.lock`, `.long-gate.*`."""
    return name in {".lock", ".lifecycle.lock"} or name.startswith(".long-gate.")


def kind_of(name: str) -> str:
    ext = Path(name).suffix.lower()
    return "text" if ext in TEXT else "image" if ext in IMAGES else "other"


def inside(root: Path, rel: str) -> Path | None:
    """The path in the planning folder, or None when it leaves it, does not exist, or is a
    lock: no absolute path, no drive, no NUL, symlinks out refused."""
    if (
        "\x00" in rel
        or rel.startswith(("/", "\\"))
        or re.match(r"^[A-Za-z]:", rel)
        or Path(rel).is_absolute()
        or any(is_lock(part) for part in re.split(r"[\\/]", rel))
    ):
        return None
    try:
        target = (root / rel).resolve()
    except (OSError, ValueError):
        return None
    return target if target.is_relative_to(root) and target.exists() else None


def _listed(root: Path, folder: Path) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for here, dirs, names in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not is_lock(d))
        for name in sorted(names):
            path = Path(here) / name
            try:
                real = path.resolve()
                size = real.stat().st_size
            except OSError:
                continue
            if is_lock(name) or not real.is_relative_to(root) or not real.is_file():
                continue
            found.append(
                {"path": path.relative_to(root).as_posix(), "size": size, "kind": kind_of(name)}
            )
    return sorted(found, key=lambda f: f["path"])


def tree(root: Path, rel: str) -> Reply | list[dict[str, Any]]:
    """Every file under a folder of the planning folder, recursively, sorted; a Reply (404)
    when the path is not a folder inside it."""
    target = root if rel in {"", "."} else inside(root, rel)
    if target is None or not target.is_dir():
        return text(404, NOT_FOUND)
    return retry(_listed, root, target)


def _head(path: Path) -> bytes:
    with path.open("rb") as f:
        return f.read(TEXT_LIMIT)


def _attachment(name: str) -> dict[str, str]:
    safe = re.sub(r"[^\w.\- ]", "_", name)
    return {"Content-Disposition": f'attachment; filename="{safe}"'}


def read(root: Path, rel: str) -> Reply:
    """One file's bytes: text as plain text (cut at 1 MB), an image with its own type, anything
    else as a download."""
    target = inside(root, rel)
    if target is None or not target.is_file():
        return text(404, NOT_FOUND)
    kind, ext = kind_of(target.name), target.suffix.lower()
    size = target.stat().st_size
    if kind == "text":
        raw = retry(_head, target)
        head = (
            {"X-Chantier-Cut": "1"} if size > TEXT_LIMIT else {SHA_HEADER: sha256(raw).hexdigest()}
        )
        body = raw[:TEXT_LIMIT].decode("utf-8-sig", errors="replace").encode("utf-8")
        return Reply(200, body, "text/plain; charset=utf-8", head)
    if kind == "image" and size <= IMAGE_LIMIT:
        return Reply(200, retry(target.read_bytes), IMAGES[ext])
    return Reply(
        200, retry(target.read_bytes), "application/octet-stream", _attachment(target.name)
    )

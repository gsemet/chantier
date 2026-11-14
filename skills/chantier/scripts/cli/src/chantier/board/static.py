"""The frame: the files of `board/web/`, shipped as package data."""

from __future__ import annotations

from pathlib import Path

from chantier.board.reply import Reply, matches, text

WEB = Path(__file__).resolve().parent / "web"
# Python's `mimetypes` reads the Windows registry: the types are named here.
TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".woff2": "font/woff2",
}


def _file(rel: str) -> Path | None:
    name = rel.strip("/") or "index.html"
    try:
        target = (WEB / name).resolve()
    except (OSError, ValueError):
        return None
    return target if target.is_relative_to(WEB.resolve()) and target.is_file() else None


def serve(rel: str, if_none_match: str | None) -> Reply:
    """A file of the frame, with an `ETag` and `no-cache`: `304` while it is unchanged."""
    target = _file(rel)
    if target is None or target.suffix not in TYPES:
        return text(404, "not found")
    info = target.stat()
    etag = f'"{info.st_size:x}-{info.st_mtime_ns:x}"'
    headers = {"Cache-Control": "no-cache", "ETag": etag}
    if matches(if_none_match, etag):
        return Reply(304, b"", TYPES[target.suffix], headers)
    return Reply(200, target.read_bytes(), TYPES[target.suffix], headers)

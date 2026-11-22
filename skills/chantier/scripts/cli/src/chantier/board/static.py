"""The frame: the static files of the folder `chantier serve` was given (`--ui`); none when it
was given `none`."""

from __future__ import annotations

from pathlib import Path

from chantier.board.reply import Reply, matches, text

NO_UI = "this server serves no UI: see docs/server-api.md"
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


def _file(ui: Path, rel: str) -> Path | None:
    name = rel.strip("/") or "index.html"
    try:
        target = (ui / name).resolve()
    except (OSError, ValueError):
        return None
    return target if target.is_relative_to(ui.resolve()) and target.is_file() else None


def serve(ui: Path | None, rel: str, if_none_match: str | None) -> Reply:
    """A file of the folder served, with an `ETag` and `no-cache`: `304` while it is unchanged;
    `404` with `NO_UI` when there is no folder."""
    if ui is None:
        return text(404, NO_UI)
    target = _file(ui, rel)
    if target is None or target.suffix not in TYPES:
        return text(404, "not found")
    info = target.stat()
    etag = f'"{info.st_size:x}-{info.st_mtime_ns:x}"'
    headers = {"Cache-Control": "no-cache", "ETag": etag}
    if matches(if_none_match, etag):
        return Reply(304, b"", TYPES[target.suffix], headers)
    return Reply(200, target.read_bytes(), TYPES[target.suffix], headers)

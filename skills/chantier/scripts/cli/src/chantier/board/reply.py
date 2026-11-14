"""An answer of the board, before it is handed to the web framework."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

SECURITY = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}
HTML_POLICY = (
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
    "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)


@dataclass
class Reply:
    status: int = 200
    body: bytes = b""
    kind: str = "text/plain; charset=utf-8"
    headers: dict[str, str] = field(default_factory=dict[str, str])

    def all_headers(self) -> dict[str, str]:
        """Every header of the answer: the board's own, then the route's."""
        head = {"Cache-Control": "no-store", **SECURITY}
        if self.kind.startswith("text/html"):
            head["Content-Security-Policy"] = HTML_POLICY
        return {**head, **self.headers}


def text(status: int, line: str, headers: dict[str, str] | None = None) -> Reply:
    return Reply(status, (line.rstrip("\n") + "\n").encode("utf-8"), headers=headers or {})


def as_json(data: Any, status: int = 200, headers: dict[str, str] | None = None) -> Reply:
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return Reply(status, body, "application/json; charset=utf-8", headers or {})


def matches(header: str | None, etag: str) -> bool:
    """If-None-Match: *, or a list of entity tags (weak ones count) holding this one."""
    if not header:
        return False
    tags = [t.strip().removeprefix("W/") for t in header.split(",")]
    return "*" in tags or etag in tags

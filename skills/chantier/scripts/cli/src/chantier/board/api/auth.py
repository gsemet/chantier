"""The key on the API, as the protocol says it (section 7): where it came from, the rule that the
cookie counts only from the server's own origin, the body's type, and CORS for a page served
elsewhere. `GET /` and the static files keep `guard.authorised`, with no origin rule."""

from __future__ import annotations

from typing import Literal

from chantier.board import guard
from chantier.board import key as keys
from chantier.board.context import Request
from chantier.board.reply import Reply, text

PREFIX = "/api/v1/"
Source = Literal["header", "cookie"]
CORS = {"Access-Control-Allow-Origin": "*"}
PREFLIGHT = {
    **CORS,
    "Access-Control-Allow-Methods": "GET, POST",
    "Access-Control-Allow-Headers": f"Content-Type, {keys.HEADER}",
    "Access-Control-Max-Age": "600",
}


def host_of(headers: dict[str, str]) -> str:
    """The host a client asked for: a proxy's `X-Forwarded-Host` first, else `Host`."""
    forwarded = headers.get("x-forwarded-host", "").split(",")[0].strip()
    return forwarded or headers.get("host", "")


def own_origin(headers: dict[str, str]) -> bool:
    """The request comes from the server's own page: `Sec-Fetch-Site` absent or same-origin, and
    `Origin` absent or `http(s)://<host>`."""
    if headers.get("sec-fetch-site") not in (None, "same-origin"):
        return False
    origin = headers.get("origin")
    if origin is None:
        return True
    host = host_of(headers).lower()
    return origin.lower() in (f"http://{host}", f"https://{host}")


def source_of(headers: dict[str, str], key: str) -> Source | None:
    """Where a good key came from: the header, else the cookie from the server's own origin;
    None for none, a bad one, or a cookie from another origin."""
    if keys.is_good(headers.get(keys.HEADER), key):
        return "header"
    if keys.is_good(keys.cookie_value(headers.get("cookie")), key) and own_origin(headers):
        return "cookie"
    return None


def upgrade(headers: dict[str, str], key: str) -> tuple[bool, str | None]:
    """The WebSocket upgrade, judged as a request: (may it open, the good credential it carries).
    No header and no cookie: it opens, and the key comes in `hello`. A credential that is bad, or
    a cookie from another origin, refuses it (401, no socket)."""
    cookie = keys.cookie_value(headers.get("cookie"))
    if keys.HEADER not in headers and cookie is None:
        return True, None
    source = source_of(headers, key)
    if source is None:
        return False, None
    return True, headers[keys.HEADER] if source == "header" else cookie


def judge(req: Request, key: str) -> Reply | None:
    """The refusal of a request to `/api/v1/` (401 for no key, 415 for a body that is not
    JSON), None when it may go on. A cookie from the server's own page and a header key pass
    the same rule: the body is JSON."""
    if source_of(req.headers, key) is None:
        return text(401, guard.NEEDS_KEY)
    if req.body and not req.headers.get("content-type", "").startswith("application/json"):
        return text(415, "refused: the body is application/json")
    return None


def cors(reply: Reply) -> Reply:
    """Every answer of `/api/v1/` allows any origin; credentials are never allowed."""
    reply.headers.update(CORS)
    return reply


def preflight() -> Reply:
    return Reply(204, b"", headers=dict(PREFLIGHT))

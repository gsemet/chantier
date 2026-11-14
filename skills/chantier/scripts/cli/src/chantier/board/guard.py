"""The key's guard: the exchange for a cookie, the check, and the rule for requests that change
something."""

from __future__ import annotations

from urllib.parse import quote, urlencode

from chantier.board import key as keys
from chantier.board.context import Request
from chantier.board.reply import Reply, text

NEEDS_KEY = "this board needs the link with its key: ask the Chief of Staff for it"
READ = ("GET", "HEAD")
ALLOWED = (*READ, "POST")


def exchange(req: Request, key: str) -> Reply | None:
    """A request with `k`: a bad one is refused; a good one with a method the board does not
    know gets `405`; a good read gets the cookie and a `303` to the same address without it; a
    good `POST` carries on (it still needs the cookie or the header)."""
    if not keys.is_good(req.query.get("k"), key):
        return text(401, NEEDS_KEY)
    if req.method not in ALLOWED:
        return not_allowed()
    if req.method not in READ:
        return None
    rest = {k: v for k, v in req.query.items() if k != "k"}
    where = quote(req.path, safe="/") + (f"?{urlencode(rest)}" if rest else "")
    return text(303, "the key is in the cookie now", {"Location": where, **_cookie(key)})


def _cookie(key: str) -> dict[str, str]:
    return {"Set-Cookie": keys.set_cookie(key)}


def authorised(req: Request, key: str) -> bool:
    """The key from the header (scripts, the probe) or the cookie."""
    got = req.headers.get(keys.HEADER) or keys.cookie_value(req.headers.get("cookie"))
    return keys.is_good(got, key)


def refusal(req: Request) -> Reply | None:
    """For a request that changes something: `403` unless it comes from the board's own page
    (`Sec-Fetch-Site` same-origin or absent, `Origin` the board's own) and its body is JSON."""
    site = req.headers.get("sec-fetch-site")
    origin = req.headers.get("origin")
    host = req.headers.get("host", "")
    if site not in (None, "same-origin"):
        return text(403, "refused: not from the board's own page")
    if origin is not None and origin.lower() != f"http://{host}".lower():
        return text(403, "refused: not from the board's own page")
    if req.body and not req.headers.get("content-type", "").startswith("application/json"):
        return text(403, "refused: the body is application/json")
    return None


def not_allowed() -> Reply:
    return text(405, "method not allowed", {"Allow": ", ".join(ALLOWED)})

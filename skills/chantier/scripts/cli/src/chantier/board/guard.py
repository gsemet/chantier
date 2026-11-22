"""The key's guard: the exchange for a cookie, the check, and the rule for requests that change
something."""

from __future__ import annotations

from urllib.parse import quote, urlencode

from chantier.board import key as keys
from chantier.board.context import Request
from chantier.board.reply import Reply, text

NEEDS_KEY = "this board needs the link with its key: ask the Chief of Staff for it"
READ = ("GET", "HEAD")
WRITE = ("POST", "PUT")
ALLOWED = (*READ, *WRITE)


def exchange(req: Request, key: str, cookie: str, read_key: str = "") -> Reply | None:
    """A request with `k`: a bad one is refused; a good one with a method the board does not
    know gets `405`; a good read gets the cookie of the key it held (the private key's, or the
    public one's own `_read` cookie: never the other's) and a `303` to the same address without
    it (a relative `Location`); a good `POST` carries on (it still needs the cookie or the
    header)."""
    held = keys.access_of(req.query.get("k"), key, read_key)
    if held is None:
        return text(401, NEEDS_KEY)
    if req.method not in ALLOWED:
        return not_allowed()
    if req.method not in READ:
        return None
    rest = {k: v for k, v in req.query.items() if k != "k"}
    last = req.path.rsplit("/", 1)[-1]  # relative, so a path prefix behind a proxy is kept
    where = "./" + quote(last, safe="") + (f"?{urlencode(rest)}" if rest else "")
    held_key, name = (key, cookie) if held == "write" else (read_key, keys.read_name(cookie))
    set_ = {"Set-Cookie": keys.set_cookie(held_key, name)}
    return text(303, "the key is in the cookie now", {"Location": where, **set_})


def access(req: Request, key: str, cookie: str, read_key: str = "") -> keys.Access | None:
    """What the request's key opens: the header (scripts, the probe) or the cookies; the private
    key wins when both are there."""
    header = keys.access_of(req.headers.get(keys.HEADER), key, read_key)
    kept = keys.cookie_access(req.headers.get("cookie"), cookie, key, read_key)
    return "write" if "write" in (header, kept) else header or kept


def authorised(req: Request, key: str, cookie: str, read_key: str = "") -> bool:
    return access(req, key, cookie, read_key) is not None


def refusal(req: Request) -> Reply | None:
    """For a request that changes something: `403` unless it comes from the board's own page
    (`Sec-Fetch-Site` same-origin or absent, `Origin` the board's own), `415` when its body is
    not JSON."""
    site = req.headers.get("sec-fetch-site")
    origin = req.headers.get("origin")
    host = req.headers.get("host", "")
    if site not in (None, "same-origin"):
        return text(403, "refused: not from the board's own page")
    if origin is not None and origin.lower() != f"http://{host}".lower():
        return text(403, "refused: not from the board's own page")
    if req.body and not req.headers.get("content-type", "").startswith("application/json"):
        return text(415, "refused: the body is application/json")
    return None


def not_allowed() -> Reply:
    return text(405, "method not allowed", {"Allow": ", ".join(ALLOWED)})

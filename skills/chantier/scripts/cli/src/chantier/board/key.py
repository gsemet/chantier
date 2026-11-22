"""The board's key: the file in the git folder, the cookie, the check."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from http.cookies import SimpleCookie
from pathlib import Path

from chantier.core.errors import EXIT_EXTERNAL, ChantierError
from chantier.core.files import read_text
from chantier.core.repo import Repo
from chantier.hub import state

COOKIE_PREFIX = "chantier_board_"
HEADER = "x-chantier-board-key"
COOKIE_MAX_AGE_S = 30 * 24 * 3600


def cookie_name(served: Path | str) -> str:
    """This server's own cookie: `chantier_board_<12 hex of the SHA-256 of the served folder's
    POSIX path>`, so several boards work side by side in one browser."""
    posix = served.as_posix() if isinstance(served, Path) else str(served)
    return COOKIE_PREFIX + hashlib.sha256(posix.encode("utf-8")).hexdigest()[:12]


def key_path(repo: Repo) -> Path:
    """`<git common dir>/chantier/server.json`: never in a working tree, never pushed."""
    return state.path(repo.git_dir)


def read_key(path: Path) -> str:
    try:
        key = json.loads(read_text(path)).get("key")
    except (OSError, ValueError, AttributeError) as e:
        raise ChantierError(f"board not started: {path} is unreadable: {e}", EXIT_EXTERNAL) from e
    if not isinstance(key, str) or not key:
        raise ChantierError(f"board not started: {path} holds no key", EXIT_EXTERNAL)
    return key


def load_or_create(repo: Repo, new: bool = False) -> str:
    """The board's key; made at the first start, replaced by `--new-key`, which keeps the
    `server` and `hub` entries. A failed write raises `state.StateError`."""
    if not new:
        key = state.read(repo.git_dir).get("key")
        if isinstance(key, str) and key:
            return key
    key = secrets.token_urlsafe(32)
    state.set_key(repo.git_dir, key)
    return key


class KeyFile:
    """The key, read again when the file changes (`--new-key` while the board runs)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._seen: tuple[int, int] | None = None
        self._key = ""

    def current(self) -> str:
        try:
            info = self.path.stat()
        except OSError:
            return self._key
        mark = (info.st_mtime_ns, info.st_size)
        if mark != self._seen:
            try:
                self._key, self._seen = read_key(self.path), mark
            except ChantierError:  # a file in the middle of a replace: the last good key stays
                return self._key
        return self._key


def is_good(candidate: str | None, key: str) -> bool:
    return (
        bool(candidate)
        and bool(key)
        and hmac.compare_digest((candidate or "").encode("utf-8"), key.encode("utf-8"))
    )


def cookie_value(raw: str | None, name: str) -> str | None:
    """The key a request's `Cookie` header carries under this server's cookie name."""
    if not raw:
        return None
    jar: SimpleCookie = SimpleCookie()
    try:
        jar.load(raw)
    except ValueError:
        return None
    return jar[name].value if name in jar else None


def set_cookie(key: str, name: str) -> str:
    return f"{name}={key}; Max-Age={COOKIE_MAX_AGE_S}; Path=/; HttpOnly; SameSite=Strict"

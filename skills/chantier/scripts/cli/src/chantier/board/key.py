"""The board's two keys, the private and the public read-only: the file in the git folder, the
cookie, the check."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Literal

from chantier.core.errors import EXIT_EXTERNAL, ChantierError
from chantier.core.files import read_text
from chantier.core.repo import Repo
from chantier.hub import state

COOKIE_PREFIX = "chantier_board_"
HEADER = "x-chantier-board-key"
READ_SUFFIX = "_read"
COOKIE_MAX_AGE_S = 30 * 24 * 3600


def cookie_name(served: Path | str) -> str:
    """This server's own cookie: `chantier_board_<12 hex of the SHA-256 of the served folder's
    POSIX path>`, so several boards work side by side in one browser."""
    posix = served.as_posix() if isinstance(served, Path) else str(served)
    return COOKIE_PREFIX + hashlib.sha256(posix.encode("utf-8")).hexdigest()[:12]


def key_path(repo: Repo) -> Path:
    """`<git common dir>/chantier/server.json`: never in a working tree, never pushed."""
    return state.path(repo.git_dir)


def _parse(path: Path) -> dict[str, object]:
    try:
        data = json.loads(read_text(path))
    except (OSError, ValueError) as e:
        raise ChantierError(f"board not started: {path} is unreadable: {e}", EXIT_EXTERNAL) from e
    if not isinstance(data, dict):
        raise ChantierError(
            f"board not started: {path} is unreadable: not an object", EXIT_EXTERNAL
        )
    return data


def read_key(path: Path) -> str:
    key = _parse(path).get("key")
    if not isinstance(key, str) or not key:
        raise ChantierError(f"board not started: {path} holds no key", EXIT_EXTERNAL)
    return key


def public_key(repo: Repo) -> str:
    """The public read-only key now in the file (`""` for an older file with none)."""
    found = state.read(repo.git_dir).get("read_key")
    return found if isinstance(found, str) else ""


def load_or_create(repo: Repo, new: bool = False) -> str:
    """The board's private key; made at the first start, replaced by `--new-key` (the public
    read-only key with it), which keeps the `server` and `hub` entries. A file with a key and no
    read-only key (an older build's) gets one here. A failed write raises `state.StateError`."""
    found = state.read(repo.git_dir)
    key = found.get("key")
    if not new and isinstance(key, str) and key:
        if not public_key(repo):
            state.set_read_key(repo.git_dir, secrets.token_urlsafe(32))
        return key
    key = secrets.token_urlsafe(32)
    state.set_key(repo.git_dir, key, secrets.token_urlsafe(32))
    return key


class KeyFile:
    """The two keys, read again when the file changes (`--new-key` while the board runs):
    `current()` the private one, `read_current()` the public read-only one."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._seen: tuple[int, int] | None = None
        self._key = ""
        self._read = ""

    def _refresh(self) -> None:
        try:
            info = self.path.stat()
        except OSError:
            return
        mark = (info.st_mtime_ns, info.st_size)
        if mark == self._seen:
            return
        try:
            data = _parse(self.path)
        except ChantierError:  # a file in the middle of a replace: the last good keys stay
            return
        key, read = data.get("key"), data.get("read_key")
        if isinstance(key, str) and key:
            self._key, self._seen = key, mark
            self._read = read if isinstance(read, str) else ""

    def current(self) -> str:
        self._refresh()
        return self._key

    def read_current(self) -> str:
        self._refresh()
        return self._read


Access = Literal["read", "write"]


def access_of(candidate: str | None, key: str, read_key: str) -> Access | None:
    """What a key opens: `write` (the private key), `read` (the public one), None (neither)."""
    if is_good(candidate, key):
        return "write"
    return "read" if is_good(candidate, read_key) else None


def cookie_access(raw: str | None, name: str, key: str, read_key: str) -> Access | None:
    """What a `Cookie` header opens: the private cookie wins over the read-only one."""
    if is_good(cookie_value(raw, name), key):
        return "write"
    return "read" if is_good(cookie_value(raw, read_name(name)), read_key) else None


def read_name(name: str) -> str:
    """The cookie of the public key: the server's name and `_read`, so the two never overwrite."""
    return f"{name}{READ_SUFFIX}"


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

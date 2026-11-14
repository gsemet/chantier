"""The board's key: the file in the git folder, the cookie, the check."""

from __future__ import annotations

import hmac
import json
import os
import secrets
from http.cookies import SimpleCookie
from pathlib import Path

from chantier.core import clock
from chantier.core.errors import EXIT_EXTERNAL, ChantierError
from chantier.core.files import read_text, write_json
from chantier.core.repo import Repo

COOKIE = "chantier_board"
HEADER = "x-chantier-board-key"
YEAR_S = 365 * 24 * 3600


def key_path(repo: Repo) -> Path:
    """`<git common dir>/chantier/board.json`: never in a working tree, never pushed."""
    return repo.git_dir / "chantier" / "board.json"


def read_key(path: Path) -> str:
    try:
        key = json.loads(read_text(path)).get("key")
    except (OSError, ValueError, AttributeError) as e:
        raise ChantierError(f"board not started: {path} is unreadable: {e}", EXIT_EXTERNAL) from e
    if not isinstance(key, str) or not key:
        raise ChantierError(f"board not started: {path} holds no key", EXIT_EXTERNAL)
    return key


def load_or_create(repo: Repo, new: bool = False) -> str:
    """The board's key; made at the first start, replaced by `--new-key`."""
    path = key_path(repo)
    if path.is_file() and not new:
        return read_key(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    key = secrets.token_urlsafe(32)
    write_json(path, {"key": key, "created": clock.now()})
    os.chmod(path, 0o600)
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
            except ChantierError:
                return ""
        return self._key


def is_good(candidate: str | None, key: str) -> bool:
    return (
        bool(candidate)
        and bool(key)
        and hmac.compare_digest((candidate or "").encode("utf-8"), key.encode("utf-8"))
    )


def cookie_value(raw: str | None) -> str | None:
    """The key a request's `Cookie` header carries."""
    if not raw:
        return None
    jar: SimpleCookie = SimpleCookie()
    try:
        jar.load(raw)
    except ValueError:
        return None
    return jar[COOKIE].value if COOKIE in jar else None


def set_cookie(key: str) -> str:
    return f"{COOKIE}={key}; Max-Age={YEAR_S}; Path=/; HttpOnly; SameSite=Strict"

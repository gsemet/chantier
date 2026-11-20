"""The in-project planning folder, as a store: plain files under `.agents/changes/`."""

from __future__ import annotations

import contextlib
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from chantier.core.errors import (
    EXIT_CONFLICT,
    EXIT_EXTERNAL,
    EXIT_PRECONDITION,
    EXIT_USAGE,
    ChantierError,
)
from chantier.core.files import (
    ensure_gitignore,
    read_text,
    retry,
    try_lock,
    unlock,
    write_bytes,
    write_file,
    write_json,
)
from chantier.store.base import LOCAL_FILES, READ_ONLY, guard, is_published

LOCK_WAIT_S = 30  # how long `lock()` waits for another holder
LOCK_FILE = ".lifecycle.lock"


class FolderStore:
    """Writes the files of the planning folder directly, atomically, under the lifecycle lock.
    It publishes nothing and refuses nothing. Building one creates no file."""

    features = frozenset({LOCAL_FILES})

    def __init__(self, changes: Path):
        self.root = changes

    @property
    def config_path(self) -> Path | None:
        return None

    def _p(self, rel: str, root_ok: bool = False) -> Path:
        return guard(self.root, rel, root_ok)

    def read_text(self, rel: str) -> str:
        return read_text(self._p(rel))

    def exists(self, rel: str) -> bool:
        return self._p(rel, True).exists()

    def listdir(self, rel: str) -> list[str]:
        return sorted(p.name for p in self._p(rel, True).iterdir())

    def write_text(self, rel: str, text: str) -> None:
        write_file(self._p(rel), text)

    def write_json(self, rel: str, data: Any, *, ensure_ascii: bool = True) -> None:
        write_json(self._p(rel), data, ensure_ascii=ensure_ascii)

    def write_bytes(self, rel: str, data: bytes) -> None:
        write_bytes(self._p(rel), data)

    def make_folder(self, rel: str, exist_ok: bool) -> None:
        self._p(rel).mkdir(parents=True, exist_ok=exist_ok)

    def write_config(self, data: bytes) -> None:
        raise ChantierError(READ_ONLY, EXIT_PRECONDITION)

    def move(self, rel_src: str, rel_dst: str) -> None:
        source, destination = self._p(rel_src), self._p(rel_dst)
        if not source.exists():
            raise ChantierError(f"CR folder not found: {source}", EXIT_USAGE)
        if destination.exists() or destination.is_symlink():
            raise ChantierError(f"refusing to overwrite CR folder: {destination}", EXIT_CONFLICT)
        if source == destination or source in destination.parents:
            raise ChantierError(f"invalid CR move: {source} to {destination}", EXIT_USAGE)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            retry(source.rename, destination)
        except OSError as e:
            raise ChantierError(
                f"cannot move CR folder {source} to {destination}: {e}", EXIT_EXTERNAL
            ) from e

    def remove(self, rel: str) -> None:
        path = self._p(rel)
        retry(path.rmdir if path.is_dir() and not path.is_symlink() else path.unlink)

    @contextlib.contextmanager
    def lock(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        self.ensure_gitignore()
        with open(self.root / LOCK_FILE, "a+") as lock:
            deadline = time.monotonic() + LOCK_WAIT_S
            while not try_lock(lock):
                if time.monotonic() > deadline:
                    raise ChantierError("CR lifecycle is locked for over 30 s")
                time.sleep(0.05)
            try:
                yield
            finally:
                unlock(lock)

    def ensure_gitignore(self) -> None:
        """The planning folder's own `.gitignore`: written here, never refused."""
        ensure_gitignore(self.root)

    def published(self, rel: str) -> bool:
        self._p(rel, True)
        return is_published(rel)

    def check_publish(
        self, rels: list[str], *, config: bool = False, command: str | None = None
    ) -> None:
        """Returns: no backend refuses yet. The paths are checked to stay in the folder."""
        for rel in rels:
            self._p(rel, True)

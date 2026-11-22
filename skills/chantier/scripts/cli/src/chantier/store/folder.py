"""The in-project planning folder, as a store: plain files under `.agents/changes/`."""

from __future__ import annotations

import contextlib
import os
import stat
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from chantier.core import files as core_files
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
    rel_in,
    retry,
    retry_held,
    try_lock,
    unlock,
    write_bytes,
    write_file,
    write_json,
)
from chantier.store.base import LOCAL_FILES, READ_ONLY, guard, is_published

LOCK_WAIT_S = 30  # how long `lock()` waits for another holder
LOCK_FILE = ".lifecycle.lock"
_REPARSE = 0x400  # FILE_ATTRIBUTE_REPARSE_POINT: a Windows symlink or junction


class FolderStore:
    """Writes the files of the planning folder directly, atomically, under the lifecycle lock.
    It publishes nothing and refuses nothing. Building one creates no file."""

    features = frozenset({LOCAL_FILES})

    def __init__(self, changes: Path):
        self.root = changes
        self._real: Path | None = None  # `root.resolve()`, once: the guard runs on each read
        self._scope = threading.local()  # the folders `reading()` of a thread has checked

    @property
    def config_path(self) -> Path | None:
        return None

    def _p(self, rel: str, root_ok: bool = False) -> Path:
        if self._real is None:
            self._real = self.root.resolve()
        return guard(self.root, rel, root_ok, self._real)

    @contextlib.contextmanager
    def reading(self) -> Iterator[None]:
        """One read-only pass over the folder (a board state): a folder it has checked for links
        is not checked again until the pass ends. Nothing lasts across passes, and a thread
        outside a pass checks on every read."""
        if getattr(self._scope, "seen", None) is not None:
            yield
            return
        self._scope.seen = set()
        try:
            yield
        finally:
            self._scope.seen = None

    def _r(self, rel: str, root_ok: bool = False, content: bool = False) -> Path:
        """`_p` for a read: a `rel` of plain names is checked lexically and by one `lstat` per
        component under the root, the leaf included (a component already checked in the same
        `reading()` pass is skipped); a symlink or junction on the way, or anything but plain
        names, gets the full guard (`resolve`). Writes keep `_p`."""
        parts = rel.split("/")
        if any(p in ("", ".", "..") or ":" in p or "\\" in p or "\x00" in p for p in parts):
            return self._p(rel, root_ok)
        seen: set[str] | None = getattr(self._scope, "seen", None)
        base = os.fspath(self.root)
        prefix = ""
        for part in parts:
            prefix = f"{prefix}/{part}" if prefix else part
            if seen is not None and prefix in seen:
                continue
            try:
                st = os.lstat(f"{base}/{prefix}")
            except OSError:
                break  # absent: nothing below it can be a link, the read itself reports it
            if stat.S_ISLNK(st.st_mode) or getattr(st, "st_file_attributes", 0) & _REPARSE:
                return self._p(rel, root_ok)
            if seen is not None:
                seen.add(prefix)
        return self.root / rel

    def read_text(self, rel: str, errors: str = "strict") -> str:
        return read_text(self._r(rel, content=True), errors)

    def read_bytes(self, rel: str, limit: int | None = None) -> bytes:
        path = self._r(rel, content=True)
        if limit is None:
            return retry(path.read_bytes)
        return retry(self._head, path, limit)

    @staticmethod
    def _head(path: Path, limit: int) -> bytes:
        with path.open("rb") as f:
            return f.read(limit)

    def exists(self, rel: str) -> bool:
        return self._r(rel, True).exists()

    def is_file(self, rel: str) -> bool:
        return self._r(rel, True).is_file()

    def is_dir(self, rel: str) -> bool:
        return self._r(rel, True).is_dir()

    def listdir(self, rel: str) -> list[str]:
        return sorted(p.name for p in self._r(rel, True).iterdir())

    def glob(self, rel: str, pattern: str) -> list[str]:
        """The names directly in the folder `rel` that match `pattern` (`Path.glob`'s rules)."""
        return sorted(p.name for p in self._r(rel, True).glob(pattern))

    def stat(self, rel: str) -> tuple[int, int] | None:
        try:
            st = self._r(rel, True).stat()
        except OSError:
            return None
        return st.st_size, st.st_mtime_ns

    def walk(self, rel: str) -> Iterator[tuple[str, list[str], list[str]]]:
        """As `os.walk`, top-down: the folder's rel (`.` for the root), its folder names (edit
        in place to prune) and its file names. A symlinked folder is listed, never entered; an
        absent folder gives nothing. The guard runs once, on `rel`."""
        top = self._r(rel, True)
        base, cut = rel_in(self.root, top), len(os.fspath(top))
        for folder, dirs, files in os.walk(top):
            tail = folder[cut:].replace(os.sep, "/").strip("/")
            yield (
                (base if base != "." else "") + ("/" if base != "." and tail else "") + tail or ".",
                dirs,
                files,
            )

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
            retry_held(source.rename, destination)
        except OSError as e:
            if isinstance(e, PermissionError) and core_files.on_windows():
                wait = f"{core_files.HELD_WAIT_S:.3f}".rstrip("0").rstrip(".")
                raise ChantierError(
                    f"cannot move CR folder {source} to {destination}: refused for {wait} s, "
                    "the folder is likely held; nothing moved. On Windows a folder cannot move "
                    "while a process holds it: a shell or a program whose working directory is "
                    "inside it, or a file of it open in an editor or a viewer. Leave it (cd "
                    "elsewhere, close the file) and run the command again; the board need not "
                    f"stop. ({e})",
                    EXIT_EXTERNAL,
                ) from e
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

"""The plan's store: the protocol every backend implements, the feature words, the path guard and
the `.gitignore` meaning of the files that stay local."""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import AbstractContextManager
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Protocol

from chantier.core.errors import EXIT_USAGE, ChantierError
from chantier.core.files import IGNORED

PUBLISHES = "publishes"
LOCAL_FILES = "local-files"
REFUSES_WITHOUT_PUBLISHER = "refuses-without-publisher"
FEATURES = (PUBLISHES, LOCAL_FILES, REFUSES_WITHOUT_PUBLISHER)
CONFIG_FILES = ("chantier.yaml", "chantier.yml")  # the project's configuration file, by name
READ_ONLY = (
    "the configuration is read-only with no planning surface: edit chantier.yaml by hand "
    "(the board writes only a planning surface's file)"
)


class PlanStore(Protocol):
    """The planning folder's reads and writes, behind one interface. A read goes through the
    same guard as a write and reads the files on each call; an index may come later behind this
    interface, rebuilt from the files. A missing file or folder raises what the direct read
    raises (`FileNotFoundError`); only a path outside the root raises the store's refusal."""

    root: Path
    features: frozenset[str]

    @property
    def config_path(self) -> Path | None: ...

    def read_text(self, rel: str, errors: str = "strict") -> str: ...
    def read_bytes(self, rel: str, limit: int | None = None) -> bytes: ...
    def exists(self, rel: str) -> bool: ...
    def is_file(self, rel: str) -> bool: ...
    def is_dir(self, rel: str) -> bool: ...
    def listdir(self, rel: str) -> list[str]: ...
    def glob(self, rel: str, pattern: str) -> list[str]: ...
    def stat(self, rel: str) -> tuple[int, int] | None: ...
    def walk(self, rel: str) -> Iterator[tuple[str, list[str], list[str]]]: ...
    def write_text(self, rel: str, text: str) -> None: ...
    def write_json(self, rel: str, data: Any, *, ensure_ascii: bool = True) -> None: ...
    def write_bytes(self, rel: str, data: bytes) -> None: ...
    def make_folder(self, rel: str, exist_ok: bool) -> None: ...
    def write_config(self, data: bytes) -> None: ...
    def move(self, rel_src: str, rel_dst: str) -> None: ...
    def remove(self, rel: str) -> None: ...
    def lock(self) -> AbstractContextManager[None]: ...
    def reading(self) -> AbstractContextManager[None]:
        """One read pass: no content is cached, only the link check of a folder, until the pass ends."""
        ...

    def ensure_gitignore(self) -> None: ...
    def published(self, rel: str) -> bool: ...
    def check_publish(
        self, rels: list[str], *, config: bool = False, command: str | None = None
    ) -> None: ...


def outside_error(label: str, where: str, value: str | Path) -> ChantierError:
    return ChantierError(f"{label} must be inside {where}: {value}", EXIT_USAGE)


def inside_path(
    root: Path, value: str | Path, label: str, where: str, resolved_root: Path | None = None
) -> Path:
    """The resolved path of `value` (absolute, or read from `root`), which must be strictly
    inside `root`. A caller that checks many paths gives `resolved_root` (`root.resolve()`)."""
    path = Path(value).expanduser()
    path = (path if path.is_absolute() else root / path).resolve()
    root = resolved_root or root.resolve()
    if path == root or not path.is_relative_to(root):
        raise outside_error(label, where, value)
    return path


def guard(root: Path, rel: str, root_ok: bool = False, resolved_root: Path | None = None) -> Path:
    """`root / rel`, once `rel` is known to stay in the planning folder: no absolute path, no
    drive, no NUL, nothing that resolves outside (`..`, a symlink out)."""
    if (
        "\x00" in rel
        or rel.startswith(("/", "\\"))
        or re.match(r"^[A-Za-z]:", rel)
        or Path(rel).is_absolute()
    ):
        raise outside_error("path", "the planning folder", rel)
    if root_ok and rel in ("", "."):
        return root
    inside_path(root, rel, "path", "the planning folder", resolved_root)
    return root / rel


def _matches(pattern: str, parts: list[str], is_dir: bool) -> bool:
    """One `.gitignore` line against a path (its parts): a leading `/` anchors at the root, a
    trailing `/` is a folder and what is under it, `**/` any depth, a middle `**` zero or more
    folders as git does, `*` within a name."""
    dir_only = pattern.endswith("/")
    pattern = pattern.rstrip("/")
    anywhere = False
    if pattern.startswith("/"):
        pattern = pattern[1:]
    elif pattern.startswith("**/"):
        pattern, anywhere = pattern[3:], True
    elif "/" not in pattern:
        anywhere = True
    names = pattern.split("/")
    for k in range(len(names), len(parts) + 1):
        if dir_only and not (k < len(parts) or is_dir):
            continue
        prefix = parts[:k]
        starts = range(k) if anywhere else (0,)
        if any(_fits(names, prefix[i:]) for i in starts):
            return True
    return False


def _fits(names: list[str], parts: list[str]) -> bool:
    """All of `parts` against a pattern's names; a `**` name is zero or more folders."""
    if not names:
        return not parts
    if names[0] == "**":
        return any(_fits(names[1:], parts[i:]) for i in range(len(parts) + 1))
    return bool(parts) and fnmatchcase(parts[0], names[0]) and _fits(names[1:], parts[1:])


def is_published(rel: str) -> bool:
    """False when `rel` is matched by a pattern of `IGNORED`, true otherwise."""
    parts = [p for p in re.split(r"[\\/]", rel) if p and p != "."]
    is_dir = rel.endswith(("/", "\\"))
    return not any(_matches(pattern, parts, is_dir) for pattern in IGNORED)

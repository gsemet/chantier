"""The plan's store: the protocol every backend implements, the feature words, the path guard and
the `.gitignore` meaning of the files that stay local."""

from __future__ import annotations

import re
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
    """The planning folder's writes (and the reads their callers need), behind one interface."""

    root: Path
    features: frozenset[str]

    @property
    def config_path(self) -> Path | None: ...

    def read_text(self, rel: str) -> str: ...
    def exists(self, rel: str) -> bool: ...
    def listdir(self, rel: str) -> list[str]: ...
    def write_text(self, rel: str, text: str) -> None: ...
    def write_json(self, rel: str, data: Any, *, ensure_ascii: bool = True) -> None: ...
    def write_bytes(self, rel: str, data: bytes) -> None: ...
    def make_folder(self, rel: str, exist_ok: bool) -> None: ...
    def write_config(self, data: bytes) -> None: ...
    def move(self, rel_src: str, rel_dst: str) -> None: ...
    def remove(self, rel: str) -> None: ...
    def lock(self) -> AbstractContextManager[None]: ...
    def ensure_gitignore(self) -> None: ...
    def published(self, rel: str) -> bool: ...
    def check_publish(
        self, rels: list[str], *, config: bool = False, command: str | None = None
    ) -> None: ...


def outside_error(label: str, where: str, value: str | Path) -> ChantierError:
    return ChantierError(f"{label} must be inside {where}: {value}", EXIT_USAGE)


def inside_path(root: Path, value: str | Path, label: str, where: str) -> Path:
    """The resolved path of `value` (absolute, or read from `root`), which must be strictly
    inside `root`."""
    path = Path(value).expanduser()
    path = (path if path.is_absolute() else root / path).resolve()
    root = root.resolve()
    if path == root or not path.is_relative_to(root):
        raise outside_error(label, where, value)
    return path


def guard(root: Path, rel: str, root_ok: bool = False) -> Path:
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
    inside_path(root, rel, "path", "the planning folder")
    return root / rel


def _matches(pattern: str, parts: list[str], is_dir: bool) -> bool:
    """One `.gitignore` line against a path (its parts): a leading `/` anchors at the root, a
    trailing `/` is a folder and what is under it, `**/` any depth, `*` within a name."""
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
        tail = prefix[-len(names) :] if anywhere else prefix
        if (anywhere or k == len(names)) and all(map(fnmatchcase, tail, names)):
            return True
    return False


def is_published(rel: str) -> bool:
    """False when `rel` is matched by a pattern of `IGNORED`, true otherwise."""
    parts = [p for p in re.split(r"[\\/]", rel) if p and p != "."]
    is_dir = rel.endswith(("/", "\\"))
    return not any(_matches(pattern, parts, is_dir) for pattern in IGNORED)

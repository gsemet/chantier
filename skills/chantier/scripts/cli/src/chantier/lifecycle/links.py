"""`validate`'s reading of the links between the planning folder's Markdown files: a relative link
to a `.md` file inside the folder that does not exist. Read-only."""

from __future__ import annotations

import posixpath
import re
from pathlib import Path
from urllib.parse import unquote

from chantier.core.files import rel_in
from chantier.core.repo import Repo
from chantier.lifecycle.layout_check import Finding
from chantier.store import PlanStore

SKIPPED = ("5-archives", "6-trash")  # closed CRs are history
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
CODE_SPAN = re.compile(r"(`+)(?:(?!\1).)+?\1")
TARGET = r"(<[^>\n]*>|[^)\s]*)(?:\s+(?:\"[^\"]*\"|'[^']*'))?"
INLINE = re.compile(r"(?<!!)\[[^\]]*\]\(\s*" + TARGET + r"\s*\)")
DEFINITION = re.compile(r"^ {0,3}\[[^\]]+\]:\s*" + TARGET + r"\s*$")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _prose(text: str) -> list[str]:
    """The lines outside fenced code blocks, with their code spans blanked."""
    lines: list[str] = []
    fence = ""
    for line in text.splitlines():
        m = FENCE.match(line)
        if fence:
            if m and m[1][0] == fence[0] and len(m[1]) >= len(fence):
                fence = ""
        elif m:
            fence = m[1]
        else:
            lines.append(CODE_SPAN.sub(" ", line))
    return lines


def targets(text: str) -> list[str]:
    """The link targets of a Markdown text, as written (angle brackets and title stripped), each
    once, in order."""
    found: list[str] = []
    for line in _prose(text):
        for m in [*INLINE.finditer(line), *DEFINITION.finditer(line)]:
            raw = m[1].removeprefix("<").removesuffix(">")
            if raw and raw not in found:
                found.append(raw)
    return found


def _resolved(here: Path, base: Path, target: str) -> list[str] | None:
    """The planning-folder-relative segments a relative `.md` target points at, or None when the
    link is not checked (a scheme, an absolute path, not Markdown, leaving the folder)."""
    path = unquote(re.split(r"[#?]", target, maxsplit=1)[0])
    if not path.lower().endswith(".md") or SCHEME.match(path) or path.startswith(("/", "\\")):
        return None
    joined = posixpath.normpath(posixpath.join(*here.relative_to(base).parts, path))
    parts = joined.split("/")
    return None if parts[0] == ".." else parts


def _listing(store: PlanStore, cache: dict[Path, set[str]], folder: Path) -> set[str]:
    if folder not in cache:
        try:
            cache[folder] = set(store.listdir(rel_in(store.root, folder)))
        except OSError:
            cache[folder] = set()
    return cache[folder]


def _exists(store: PlanStore, cache: dict[Path, set[str]], base: Path, parts: list[str]) -> bool:
    """Each segment looked up by its exact name in its folder's listing, never by `exists()`,
    which a case-insensitive file system answers differently."""
    folder = base
    for part in parts:
        if part not in _listing(store, cache, folder):
            return False
        folder = folder / part
    return True


def _markdown_files(store: PlanStore, base: Path) -> list[Path]:
    found: list[Path] = []
    for root, dirs, files in store.walk("."):
        top = root == "."
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and not (top and d in SKIPPED))
        found += [
            base / root / f for f in sorted(files) if f.lower().endswith(".md") and f != "STATUS.md"
        ]
    return found


def broken_links(repo: Repo) -> list[Finding]:
    """Every relative link to a Markdown file of the planning folder that resolves to nothing."""
    base = repo.changes.resolve()
    cache: dict[Path, set[str]] = {}
    found: list[Finding] = []
    store = repo.store
    for file in _markdown_files(store, base):
        for target in targets(store.read_text(rel_in(store.root, file), "replace")):
            parts = _resolved(file.parent, base, target)
            if parts and not _exists(store, cache, base, parts):
                found.append(Finding("gap", repo.rel(file), f"link to {target} does not resolve"))
    return found

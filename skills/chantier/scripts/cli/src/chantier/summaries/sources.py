"""The Markdown files a CR's summary covers, their checksums, and what changed since."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from chantier.core.files import rel_in
from chantier.store import PlanStore

COVERED = ("01-intent.md", "02-answers.md", "03-change-spec.md", "delivery.md")
INTAKE = "intake"  # its top-level `*.md` files are covered too
BOM = b"\xef\xbb\xbf"

How = Literal["changed", "new", "gone"]


@dataclass(frozen=True)
class Change:
    """A covered file that differs from what the summary recorded."""

    path: str
    how: How


def covered_files(store: PlanStore, folder: Path) -> list[str]:
    """The covered files present in a CR folder, by path relative to it (forward slashes), sorted:
    `intake/*.md` (that folder's top level only), the intent, the answers, the specification and
    the delivery."""
    rel = rel_in(store.root, folder)
    names = [name for name in COVERED if store.is_file(f"{rel}/{name}")]
    intake = f"{rel}/{INTAKE}"
    if store.is_dir(intake):
        names += [
            f"{INTAKE}/{n}" for n in store.glob(intake, "*.md") if store.is_file(f"{intake}/{n}")
        ]
    return sorted(names)


def checksum(store: PlanStore, path: Path) -> str:
    """SHA-256 of a file with a leading byte-order mark dropped and `\\r\\n` read as `\\n`, so a
    checkout on another system does not make a summary late. A file that is not UTF-8 is hashed
    as the bytes it is, with the same two rules."""
    data = store.read_bytes(rel_in(store.root, path)).removeprefix(BOM).replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def checksums(store: PlanStore, folder: Path) -> dict[str, str]:
    """Each covered file of the folder with its checksum."""
    return {name: checksum(store, folder / name) for name in covered_files(store, folder)}


def diff(recorded: dict[str, str], current: dict[str, str]) -> list[Change]:
    """What changed between the recorded checksums and the current ones, sorted by path."""
    changes = [
        Change(name, "changed" if name in recorded else "new")
        for name, digest in current.items()
        if recorded.get(name) != digest
    ]
    changes += [Change(name, "gone") for name in recorded if name not in current]
    return sorted(changes, key=lambda c: c.path)

"""The Markdown files a CR's summary covers, their checksums, and what changed since."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from chantier.core.files import retry

COVERED = ("01-intent.md", "02-answers.md", "03-change-spec.md", "delivery.md")
INTAKE = "intake"  # its top-level `*.md` files are covered too
BOM = b"\xef\xbb\xbf"

How = Literal["changed", "new", "gone"]


@dataclass(frozen=True)
class Change:
    """A covered file that differs from what the summary recorded."""

    path: str
    how: How


def covered_files(folder: Path) -> list[str]:
    """The covered files present in a CR folder, by path relative to it (forward slashes), sorted:
    `intake/*.md` (that folder's top level only), the intent, the answers, the specification and
    the delivery."""
    names = [name for name in COVERED if (folder / name).is_file()]
    intake = folder / INTAKE
    if intake.is_dir():
        names += [f"{INTAKE}/{p.name}" for p in intake.glob("*.md") if p.is_file()]
    return sorted(names)


def checksum(path: Path) -> str:
    """SHA-256 of a file with a leading byte-order mark dropped and `\\r\\n` read as `\\n`, so a
    checkout on another system does not make a summary late. A file that is not UTF-8 is hashed
    as the bytes it is, with the same two rules."""
    data = retry(path.read_bytes).removeprefix(BOM).replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def checksums(folder: Path) -> dict[str, str]:
    """Each covered file of the folder with its checksum."""
    return {name: checksum(folder / name) for name in covered_files(folder)}


def diff(recorded: dict[str, str], current: dict[str, str]) -> list[Change]:
    """What changed between the recorded checksums and the current ones, sorted by path."""
    changes = [
        Change(name, "changed" if name in recorded else "new")
        for name, digest in current.items()
        if recorded.get(name) != digest
    ]
    changes += [Change(name, "gone") for name in recorded if name not in current]
    return sorted(changes, key=lambda c: c.path)

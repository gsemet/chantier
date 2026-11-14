"""Reading and writing a CR's `summary.json`."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.files import read_text, write_json
from chantier.core.records import SUMMARY_FILE, SUMMARY_SCHEMA, CrSummary


class UnreadableSummary(ChantierError):
    """A `summary.json` that is not valid JSON or does not match the model."""

    def __init__(self, why: str):
        super().__init__(
            f"{SUMMARY_FILE} unreadable ({why}); repair or remove it", EXIT_PRECONDITION
        )
        self.why = why


def _why(error: Exception) -> str:
    """One line that names what is wrong."""
    if isinstance(error, ValidationError):
        first = error.errors()[0]
        place = ".".join(str(part) for part in first["loc"])
        return f"{place}: {first['msg']}".strip(": ")
    return " ".join(str(error).split())


def read(folder: Path) -> CrSummary | None:
    """The CR's summary, or None when it has no `summary.json`; raises `UnreadableSummary`."""
    path = folder / SUMMARY_FILE
    if not path.is_file():
        return None
    try:
        return CrSummary.model_validate_json(read_text(path))
    except (ValueError, OSError) as e:
        raise UnreadableSummary(_why(e)) from e


def read_or_new(folder: Path) -> CrSummary:
    """The CR's summary, or an empty one of the current schema."""
    return read(folder) or CrSummary(schema=SUMMARY_SCHEMA)


def write(folder: Path, summary: CrSummary) -> None:
    """Store the summary: UTF-8, indented, atomic."""
    write_json(folder / SUMMARY_FILE, summary.to_data(), ensure_ascii=False)

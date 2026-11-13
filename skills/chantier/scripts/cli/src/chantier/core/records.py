"""The JSON records chantier keeps, as pydantic models, and the ids of batches and CRs.

One model per record: `batch.json` (with its settings and CR entries), an `events.jsonl` line,
`seat.json`, `.long-gate.run` and `restored.json`. Every model keeps the keys it does not
declare (`extra="allow"`) and is written with the keys that were set only, so a key this version
does not know survives a read and a write, and an absent key stays absent."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from chantier.core.errors import ChantierError
from chantier.core.files import read_json, read_text

DEFAULT_MAX_ROUNDS = 3


class Record(BaseModel):
    """What every record has in common: unknown keys are kept."""

    model_config = ConfigDict(extra="allow")

    def to_data(self) -> dict[str, Any]:
        """The record as JSON data: the keys that were set, and no other."""
        return self.model_dump(mode="json", exclude_unset=True)


class BatchSettings(Record):
    max_rounds: int = DEFAULT_MAX_ROUNDS


class CrEntry(Record):
    id: str
    rounds: int | None = None


class BatchRecord(Record):
    """A `batch.json`. Batches written before the words running and paused recorded
    `status: "open"` and `status: "landed"` (with a `landed` time): they read as running and
    paused."""

    id: str = ""
    status: str = "running"
    crs: list[CrEntry] = []
    settings: BatchSettings | None = None
    foreman_epoch: int = 0
    chief_transcript: str | None = None
    chief_transcripts: list[str] = []

    @model_validator(mode="before")
    @classmethod
    def _old_words(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if data.get("status") == "landed":
            data["status"] = "paused"
            if "landed" in data:
                data["paused"] = data.pop("landed")
        elif data.get("status") == "open":
            data["status"] = "running"
        return data


class EventRecord(Record):
    """A line of `events.jsonl`."""

    t: str
    actor: str
    kind: str
    cr: str | None = None


class SeatRecord(Record):
    """`seat.json`: the Chief of Staff session of the repository."""

    session: str | None = None
    transcript: str | None = None
    env: str | None = None
    title: str | None = None
    link: str | None = None


class RunRecord(Record):
    """`.long-gate.run`: what the running long gate is."""

    cr: str = ""
    run: str = ""
    head: str = ""
    log: str = ""
    command: str = ""
    pg: int | None = None


class RestoredRecord(Record):
    """`restored.json`: the highest number `restore` took off a folder."""

    last_number: int


def read_batch_json(path: Path) -> dict[str, Any]:
    """A `batch.json` as data, in today's words. Nothing is written here; the next write through
    `Batch` stores the new words."""
    data = read_json(path)
    if not isinstance(data, dict):
        return {}
    try:
        return BatchRecord.model_validate(data).to_data()
    except ValidationError as e:
        if any(err["loc"][:1] == ("settings",) for err in e.errors()):
            raise ChantierError("invalid batch settings; refusing to run") from e
        raise ChantierError(f"{path} is not a valid batch record: {e}") from e


# The statuses a live Driver owns; the others are queued, ready, blocked, cancelled, merged.
# A batch is running or paused (a closed batch has no folder).
LIVE = {"working"}


def chief_sessions(d: dict[str, Any]) -> list[str]:
    """Every session that was the batch's Chief of Staff, the current one last; an old batch has
    only `chief_transcript`."""
    rec = BatchRecord.model_validate(d)
    return list(rec.chief_transcripts or ([rec.chief_transcript] if rec.chief_transcript else []))


def round_limit(d: dict[str, Any], c: dict[str, Any]) -> int:
    """The batch's limit, or the one the user granted this CR (`order rounds`)."""
    settings = BatchSettings.model_validate(d.get("settings") or {})
    return CrEntry.model_validate(c).rounds or settings.max_rounds


def read_restored_number(path: Path) -> int:
    """The number `restore` last took off a folder; 0 when there is none or the file is
    unreadable."""
    try:
        return RestoredRecord.model_validate_json(read_text(path)).last_number
    except (OSError, ValueError):
        return 0


def write_restored_number(path: Path, number: int) -> None:
    path.write_text(
        json.dumps(RestoredRecord(last_number=number).to_data()) + "\n", encoding="utf-8"
    )


def read_events(folder: Path) -> list[dict[str, Any]]:
    """The batch's `events.jsonl`, in order; a half-written last line is skipped."""
    path = folder / "events.jsonl"
    out = []
    for line in read_text(path).splitlines() if path.exists() else []:
        try:
            out.append(json.loads(line))
        except ValueError:  # the last line of a process killed while appending
            continue
    return out


def normalize_batch(batch: str) -> str:
    """`4`, `04` and `batch-04` all name `batch-04`; anything else is left as given."""
    match = re.fullmatch(r"(?:batch-)?(\d+)", batch.strip())
    return f"batch-{int(match.group(1)):02d}" if match else batch


def normalize_cr(value):
    """`165`, `CR-165` and `cr-165` all name `CR-165`; anything else (`stack`, `-`, an `O-k`
    order, a QA folder) is left as given."""
    if not isinstance(value, str):
        return value
    match = re.fullmatch(r"(?:cr-)?(\d+)", value.strip(), re.I)
    return f"CR-{match.group(1)}" if match else value

"""The JSON records chantier keeps, as pydantic models, and the ids of batches and CRs.

One model per record: `batch.json` (with its settings and CR entries), an `events.jsonl` line,
`seat.json`, `.long-gate.run` and `restored.json`. Every model keeps the keys it does not
declare (`extra="allow"`) and is written with the keys that were set only, so a key this version
does not know survives a read and a write, and an absent key stays absent."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, overload

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

    def unset(self, name: str) -> None:
        """Take a key out of the record: it reads as its default and is no longer written."""
        field = type(self).model_fields.get(name)
        if field is not None:
            self.__dict__[name] = field.get_default(call_default_factory=True)
            self.model_fields_set.discard(name)
        elif self.__pydantic_extra__ is not None:
            self.__pydantic_extra__.pop(name, None)

    def append(self, name: str, value: Any) -> None:
        """Add to a list key by assigning it, so that the key counts as set and is written."""
        setattr(self, name, [*getattr(self, name), value])


class BatchSettings(Record):
    default_branch: str | None = None
    remote: str | None = None
    max_rounds: int = DEFAULT_MAX_ROUNDS


class CrEntry(Record):
    """A CR of the batch, as `batch.json` lists it."""

    id: str
    title: str = ""
    kind: str = "change"
    status: str = "queued"
    order: int = 0
    path: str | None = None
    specification: str = "03-change-spec.md"
    round: int = 0
    agent: str | None = None
    pr: str | None = None
    head: str | None = None
    branch: str = ""
    worktree: str = ""
    notes: list[str] = []
    updated: str | None = None
    after: list[str] = []
    fix_for: str | None = None
    blocked_reason: str | None = None
    cost_usd: float | None = None
    cost_unpriced: dict[str, int] = {}
    released: str | None = None
    drafts: list[str] = []
    merged_at: str | None = None
    merged_pr: str | None = None
    archive_stamp: str | None = None
    archive_seen: bool | None = None
    procedure: str | None = None
    approvals: list[str] = []
    rounds: int | None = None
    attempts: int = 0
    stacked: bool = False


class ReleaseGrant(Record):
    """What the user allowed the batch's release CR to do without asking."""

    autonomous: int = 0
    fixes: bool = False
    published: int = 0
    cr: str | None = None


class OrderRecord(Record):
    """An order of the user, as `batch.json` keeps it until the Foreman ends it."""

    id: str
    kind: str
    cr: str = "-"
    note: str = ""
    sent: str | None = None
    done: str | None = None
    applied: bool | None = None
    agent: str | None = None
    fix_for: str | None = None
    release: bool = False


class AskRecord(Record):
    """What the Foreman had to tell the Chief of Staff."""

    id: str
    text: str = ""
    sent: str | None = None
    read: str | None = None


class ClaimRecord(Record):
    """A steering transcript, from the time it claimed the batch."""

    transcript: str
    since: str | None = None


class BatchRecord(Record):
    """A `batch.json`. Batches written before the words running and paused recorded
    `status: "open"` and `status: "landed"` (with a `landed` time): they read as running and
    paused."""

    id: str = ""
    version: str | None = None
    created: str | None = None
    status: str = "running"
    host: str = ""
    mode: str | None = None
    slots: int = 4
    budget_usd: float | None = None
    spent_usd: float | None = None
    unpriced: dict[str, int] = {}
    foreman: str | None = None
    foreman_epoch: int = 0
    foreman_transcript: str | None = None
    foreman_transcripts: list[str] = []
    foreman_claims: list[ClaimRecord] = []
    steering: str | None = None
    chief_transcript: str | None = None
    chief_transcripts: list[str] = []
    stack_agent: str | None = None
    heartbeat: str | None = None
    heartbeat_stopped: str | None = None
    settings: BatchSettings | None = None
    orders: list[OrderRecord] = []
    asks: list[AskRecord] = []
    crs: list[CrEntry] = []
    release: ReleaseGrant | None = None
    playbook: dict[str, Any] | None = None
    paused: str | None = None
    summary: list[str] = []
    closing: bool = False

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
    """A line of `events.jsonl`. What else it says depends on its kind (`head`, `result`, `note`,
    ...): those keys read as attributes, and as None where the line does not have them."""

    t: str
    actor: str
    kind: str
    cr: str | None = None

    if TYPE_CHECKING:

        def __getattr__(self, name: str) -> Any: ...

    else:

        def __getattr__(self, name: str) -> Any:
            if name.startswith("_"):
                return super().__getattr__(name)
            return (self.__pydantic_extra__ or {}).get(name)


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


def read_batch_json(path: Path) -> BatchRecord:
    """A `batch.json`, in today's words. Nothing is written here; the next write through
    `Batch` stores the new words."""
    data = read_json(path)
    if not isinstance(data, dict):
        return BatchRecord()
    try:
        return BatchRecord.model_validate(data)
    except ValidationError as e:
        if any(err["loc"][:1] == ("settings",) for err in e.errors()):
            raise ChantierError("invalid batch settings; refusing to run") from e
        raise ChantierError(f"{path} is not a valid batch record: {e}") from e


# The statuses a live Driver owns; the others are queued, ready, blocked, cancelled, merged.
# A batch is running or paused (a closed batch has no folder).
LIVE = {"working"}


def chief_sessions(d: BatchRecord) -> list[str]:
    """Every session that was the batch's Chief of Staff, the current one last; an old batch has
    only `chief_transcript`."""
    return list(d.chief_transcripts or ([d.chief_transcript] if d.chief_transcript else []))


def round_limit(d: BatchRecord, c: CrEntry) -> int:
    """The batch's limit, or the one the user granted this CR (`order rounds`)."""
    return c.rounds or (d.settings or BatchSettings()).max_rounds


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


def read_events(folder: Path) -> list[EventRecord]:
    """The batch's `events.jsonl`, in order; a half-written last line is skipped."""
    path = folder / "events.jsonl"
    out = []
    for line in read_text(path).splitlines() if path.exists() else []:
        try:
            out.append(EventRecord.model_validate_json(line))
        except ValueError:  # the last line of a process killed while appending
            continue
    return out


def normalize_batch(batch: str) -> str:
    """`4`, `04` and `batch-04` all name `batch-04`; anything else is left as given."""
    match = re.fullmatch(r"(?:batch-)?(\d+)", batch.strip())
    return f"batch-{int(match.group(1)):02d}" if match else batch


@overload
def normalize_cr(value: str) -> str: ...
@overload
def normalize_cr(value: None) -> None: ...
def normalize_cr(value: str | None) -> str | None:
    """`165`, `CR-165` and `cr-165` all name `CR-165`; anything else (`stack`, `-`, an `O-k`
    order, a QA folder) is left as given."""
    if not isinstance(value, str):
        return value
    match = re.fullmatch(r"(?:cr-)?(\d+)", value.strip(), re.I)
    return f"CR-{match.group(1)}" if match else value

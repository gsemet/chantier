"""`chantier journal add`: the one entry by which an outside poller (the user's own program, never
started by chantier) appends an `issue@1` line to this project's journal.

It checks the poller's payload with its own input model (the closed lists of trackers and events
live here, so a new word is a change of this module, never an `issue@2`), finds the CR folders
whose `issue:` line names the issue, and goes through `journal.append`, the one writer path. An
event on an issue no CR names is refused: nobody waits for it."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, StrictBool, StringConstraints, ValidationError
from pydantic import field_validator as validator

from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.repo import Repo
from chantier.hub import interests, journal
from chantier.hub.interest import ISSUE
from chantier.hub.schemas import PUBLISHED

TYPE = "issue@1"
TEXT_MAX = 300


class IssueInput(BaseModel):
    """What the poller may send: its list and nothing else (not published)."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    tracker: Literal["jira", "github", "gitlab", "other"]
    ref: Annotated[str, StringConstraints(min_length=1)]
    event: Literal["opened", "commented", "changed", "closed", "reopened"]
    at: str
    text: Annotated[str, StringConstraints(min_length=1, max_length=TEXT_MAX)]
    wakes: StrictBool = True

    @validator("at")
    @classmethod
    def _iso_time(cls, v: str) -> str:
        datetime.fromisoformat(v)
        return v

    @validator("text")
    @classmethod
    def _one_line(cls, v: str) -> str:
        if "\r" in v or "\n" in v:
            raise ValueError("text is one line")
        return v


def needs_action(args: argparse.Namespace) -> list[str]:
    raise ChantierError("journal takes add", EXIT_USAGE)


def _payload(raw: str) -> Any:
    """The payload: the `--json` value, or with `-` the whole of stdin, decoded `utf-8-sig`."""
    try:
        if raw == "-":
            raw = sys.stdin.buffer.read().decode("utf-8-sig")
        return json.loads(raw)
    except ValueError as e:  # a JSON error or a decoding error
        raise ChantierError(
            f"journal add: --json is not JSON: {(str(e).splitlines() or [''])[0]}", EXIT_USAGE
        ) from e


def _checked(payload: Any) -> IssueInput:
    try:
        return IssueInput.model_validate(payload)
    except ValidationError as e:
        first = e.errors()[0]
        where = ".".join(str(p) for p in first["loc"]) or "payload"
        raise ChantierError(
            f"journal add: {TYPE} payload refused: {where}: {first['msg']}", EXIT_USAGE
        ) from e


def add(args: argparse.Namespace) -> list[str]:
    """Append one `issue@1` line, or print the seq of the line already there."""
    if args.type != TYPE:
        raise ChantierError(
            f"journal add: {args.type} is not written from outside; an outside poller writes "
            f"{TYPE}",
            EXIT_PRECONDITION,
        )
    given = _checked(_payload(args.json))
    repo = Repo.find()
    found, failed = interests.collect_each(repo, {ISSUE})
    if failed:
        raise ChantierError(
            f"journal add: the CRs' issue: lines could not be read ({failed[0][1]}): "
            "nothing written",
            EXIT_PRECONDITION,
        )
    folders = [i.by for i in found if i.ref == given.ref]
    if not folders:
        raise ChantierError(
            f"journal add: {given.ref} is no CR's issue (chantier interests --kind issue lists "
            "them): nothing written",
            EXIT_PRECONDITION,
        )
    event = {"type": TYPE, "audience": [journal.PROJECT], **given.model_dump(), "folders": folders}
    written = journal.append(repo, [event], "poller")
    if written:
        return [
            f"journal: seq {written[0]['seq']} {TYPE} {given.event} on {given.ref} "
            f"({', '.join(folders)})"
        ]
    key = PUBLISHED[TYPE].key
    assert key is not None
    want = key(event)
    entries = journal.read(repo.store, repo.changes)[0]
    seq = next(
        e["seq"] for e in entries if e.get("type") == TYPE and e.get("audience") and key(e) == want
    )
    return [f"journal: already there (seq {seq})"]

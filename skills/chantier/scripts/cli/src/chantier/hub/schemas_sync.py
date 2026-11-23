"""The published models of the surface writer's `sync-*@1` lines (see `schemas.py`)."""

from __future__ import annotations

from chantier.hub.schemas_base import Payload, Sha


class SyncConflict1(Payload):
    upstream: Sha
    local: Sha
    files: list[str]
    projects: list[str]


class SyncBlocked1(Payload):
    reason: str
    text: str


class SyncLate1(Payload):
    since: str
    paths: int
    ahead: int


class SyncResumed1(Payload):
    after: str


class Arrived1(Payload):
    """`arrived@1`, told by the writer and by `file` and `triage` (see `schemas.py`)."""

    project: str
    folder: str
    stage: str
    before: str | None
    via: str
    upstream: Sha | None

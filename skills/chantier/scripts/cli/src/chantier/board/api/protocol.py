"""Protocol 1: one model per frame kind and per op's and topic's arguments, and the published
JSON Schema built from them (`protocol.json`, checked by a test). The results' `data` are
described in `docs/server-api.md`, not here."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool

PROTOCOL = 1
STRICT = ConfigDict(extra="forbid", frozen=True)


class _Model(BaseModel):
    model_config = STRICT


class _Open(BaseModel):  # a `hello` from a newer client may carry fields this server lacks
    model_config = ConfigDict(extra="ignore", frozen=True)


def _args() -> Any:
    return Field(default_factory=dict[str, Any])


# Frames from the client.
class Hello(_Open):
    t: Literal["hello"]
    protocol: int
    client: str = Field(max_length=100)
    key: str | None = None


class Call(_Model):
    t: Literal["call"]
    id: str = Field(max_length=64)
    op: str
    args: dict[str, Any] = _args()


class Sub(_Model):
    t: Literal["sub"]
    id: str = Field(max_length=64)
    topic: str
    args: dict[str, Any] = _args()


class Unsub(_Model):
    t: Literal["unsub"]
    id: str = Field(max_length=64)


# Frames from the server.
class ServerInfo(_Model):
    version: str
    pid: int
    served: str
    surface: bool


class Welcome(_Model):
    t: Literal["welcome"]
    protocol: Literal[1]
    server: ServerInfo
    ops: list[str]
    topics: list[str]
    now: str


class Result(_Model):
    t: Literal["result"]
    id: str
    ok: bool
    status: int
    data: dict[str, Any] | None
    error: str | None = None
    now: str


class Event(_Model):
    t: Literal["event"]
    sub: str
    topic: str
    rev: str
    data: dict[str, Any]
    now: str


class Tick(_Model):
    t: Literal["tick"]
    now: str


class Error(_Model):
    t: Literal["error"]
    code: str
    error: str


class PollSub(_Model):
    key: str
    topic: str
    args: dict[str, Any] = _args()
    rev: str | None = None


class Poll(_Model):
    """The body of `POST /api/v1/poll`."""

    subs: list[PollSub]


FRAMES: dict[str, type[BaseModel]] = {
    "hello": Hello,
    "call": Call,
    "sub": Sub,
    "unsub": Unsub,
    "welcome": Welcome,
    "result": Result,
    "event": Event,
    "tick": Tick,
    "error": Error,
}


# Arguments of the ops and the topics.
class NoArgs(_Model):
    pass


class ProjectArgs(_Model):
    project: str


class StateArgs(_Model):
    project: str
    rev: str | None = None


class TreeArgs(_Model):
    project: str
    path: str = ""


class PathArgs(_Model):
    project: str
    path: str


class PrsArgs(_Model):
    project: str
    batch: str | None = None


class DashboardArgs(_Model):
    project: str
    range: Literal["10", "20", "all"] = "10"


class SeatArgs(_Model):
    session: str
    project: str | None = None


class NewArgs(_Model):
    project: str
    text: str
    slug: str | None = None
    title: str | None = None


class MoveArgs(_Model):
    project: str
    to: str
    items: list[str] | None = None
    group: str | None = None


class LabelsArgs(_Model):
    project: str
    items: list[str]
    add: str | list[str]


class GroupArgs(_Model):
    project: str
    items: list[str]
    name: str


class UngroupArgs(_Model):
    project: str
    name: str


class BacklogFileArgs(_Model):
    project: str
    item: str
    path: str
    text: str
    base_sha256: str


class ConfigPutArgs(_Model):
    project: str
    changes: Any = None
    base_sha256: str | None = None
    dry_run: StrictBool = False


class EventsArgs(_Model):
    project: str
    after: int | None = None


OP_ARGS: dict[str, type[BaseModel]] = {
    "board.get": NoArgs,
    "project.state": StateArgs,
    "project.tree": TreeArgs,
    "project.file": PathArgs,
    "costs.get": ProjectArgs,
    "costs.recompute": ProjectArgs,
    "prs.get": PrsArgs,
    "dashboard.get": DashboardArgs,
    "seats.register": SeatArgs,
    "backlog.new": NewArgs,
    "backlog.move": MoveArgs,
    "backlog.labels": LabelsArgs,
    "backlog.group": GroupArgs,
    "backlog.ungroup": UngroupArgs,
    "backlog.file": BacklogFileArgs,
    "backlog.next_batch": ProjectArgs,
    "journal.get": ProjectArgs,
    "journal.rescan": ProjectArgs,
    "config.get": ProjectArgs,
    "config.put": ConfigPutArgs,
    "writer.sync": NoArgs,
}
TOPIC_ARGS: dict[str, type[BaseModel]] = {
    "board": NoArgs,
    "project": ProjectArgs,
    "costs": ProjectArgs,
    "prs": PrsArgs,
    "journal": ProjectArgs,
    "events": EventsArgs,
}
OPS = tuple(sorted(OP_ARGS))
TOPICS = tuple(sorted(TOPIC_ARGS))


def schemas() -> dict[str, Any]:
    """The JSON Schema of every frame (`frame.<kind>`), of the long-poll's body (`http.poll`)
    and of every op's (`op.<name>`) and topic's (`topic.<name>`) arguments."""
    found: dict[str, Any] = {}
    for kind, model in FRAMES.items():
        found[f"frame.{kind}"] = model.model_json_schema()
    found["http.poll"] = Poll.model_json_schema()
    for name, model in OP_ARGS.items():
        found[f"op.{name}"] = model.model_json_schema()
    for name, model in TOPIC_ARGS.items():
        found[f"topic.{name}"] = model.model_json_schema()
    return found


def canonical() -> str:
    """The text of `protocol.json`: keys sorted, UTF-8 (no escapes), LF, a final newline."""
    return json.dumps(schemas(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"

"""The API's WebSocket binding against one real server (`127.0.0.1`, port 0, in a thread) with the
library's own sync client: the handshake and its refusals, a subscription and its events, the
limits, the key's replacement, and the 1001 close when the server stops. One server for the
module, the times shortened by the seam; the last test stops it."""

from __future__ import annotations

import contextlib
import json
import shutil
import socket
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from api_client import settled
from conftest import SEEDED_COMMON_DIRS, _key
from websockets.exceptions import ConnectionClosed, InvalidStatus  # noqa: TID253
from websockets.sync.client import ClientConnection, connect  # noqa: TID253

from chantier.board import key as keys
from chantier.board import reads
from chantier.board.api import protocol, times
from chantier.board.api.push import PushLoop, PushThread
from chantier.board.app import make_server
from chantier.board.context import Context
from chantier.board.projects import Projects
from chantier.board.seats import Seats
from chantier.core.repo import Repo
from chantier.hub import state

OK, MISSING, NO_KEY, BUSY, TOO_LARGE, TOO_MANY, SERVER_FAULT = 200, 404, 401, 503, 413, 429, 500
TRY_AGAIN = 1013
GOING_AWAY, KEY_REPLACED, TIMED_OUT, OTHER_PROTOCOL, BAD_FRAME = 1001, 4401, 4408, 4426, 4400
LIMIT = 32
WAIT_S = 3.0
HELLO = {"t": "hello", "protocol": 1, "client": "test/1"}


class Served:
    def __init__(self, ctx: Context, server: Any, port: int, repo: Repo, key: str) -> None:
        self.ctx, self.server, self.port, self.repo, self.key = ctx, server, port, repo, key
        self.clients = contextlib.ExitStack()  # every socket a test opened, closed at the end

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}/api/v1/ws"

    def open(self, **kw: Any) -> ClientConnection:
        ws: ClientConnection = self.clients.enter_context(
            connect(self.url, compression=None, open_timeout=WAIT_S, **kw)
        )
        return ws

    def welcomed(self, how: str = "header") -> ClientConnection:
        ws = self.open(additional_headers={keys.HEADER: self.key} if how == "header" else None)
        ws.send(json.dumps(HELLO if how == "header" else {**HELLO, "key": self.key}))
        assert next_of(ws, "welcome")["protocol"] == 1
        return ws


def next_of(
    ws: ClientConnection, kind: str, match: Callable[[dict[str, Any]], bool] | None = None
) -> dict[str, Any]:
    """The next frame of this kind (the ticks and the other kinds are passed over)."""
    while True:
        frame: dict[str, Any] = json.loads(ws.recv(timeout=WAIT_S))
        if frame["t"] == kind and (match is None or match(frame)):
            return frame


def closed_with(ws: ClientConnection) -> int:
    with pytest.raises(ConnectionClosed) as stopped:
        while True:
            ws.recv(timeout=WAIT_S)
    assert stopped.value.rcvd is not None
    return stopped.value.rcvd.code


@pytest.fixture(scope="module")
def served(repo_template: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Served]:
    work = tmp_path_factory.mktemp("ws") / "proj"
    shutil.copytree(repo_template, work)
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(work)
        mp.setitem(SEEDED_COMMON_DIRS, _key(work), str(work / ".git"))
        mp.setenv(times.TEST_ENV, "0.2:1:0.3:1")
        found = Repo.find(readonly=True)
        projects = Projects(found, None, [])
        secret = keys.load_or_create(found)
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        box: list[Any] = []
        ctx = Context(
            projects,
            keys.KeyFile(keys.key_path(found)),
            Seats(projects),
            "t",
            lambda: setattr(box[0], "should_exit", True),
            None,
            sock.getsockname()[:2],
        )
        box.append(make_server(ctx))
        ctx.push = PushLoop(ctx)
        push = PushThread(ctx.push, ctx.stop)
        push.start()
        thread = threading.Thread(target=box[0].run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        while not box[0].started:
            thread.join(0.01)
        for _ in range(3):  # the live reading settles: the project's rev is steady after that
            reads.state_of(ctx, projects.all()[0], ask=True)
        stub = Served(ctx, box[0], sock.getsockname()[1], found, secret)
        yield stub
        stub.clients.close()
        box[0].should_exit = True
        thread.join(WAIT_S)
        push.stop()
        sock.close()


def test_a_socket_says_hello_gets_welcome_and_watches_a_project(served: Served) -> None:
    ws = served.welcomed()
    ws.send(json.dumps({"t": "call", "id": "c", "op": "no.such", "args": {}}))
    assert next_of(ws, "result")["status"] == MISSING  # the connection stays
    ws.send(json.dumps({"t": "call", "id": "b", "op": "board.get", "args": {}}))
    got = next_of(ws, "result")
    assert (got["id"], got["ok"], got["data"]["protocols"]) == ("b", True, [1])
    args = {"project": served.ctx.projects.home_id}
    ws.send(json.dumps({"t": "sub", "id": "p", "topic": "project", "args": args}))
    assert next_of(ws, "result")["status"] == OK
    first = next_of(ws, "event")  # the first event comes after the sub's result
    assert (first["sub"], first["topic"]) == ("p", "project")
    mine = served.repo.changes / "1-inbox" / "idea" / "intake"
    mine.mkdir(parents=True)
    (mine / "request.md").write_text("an idea\n", encoding="utf-8")
    settled(served.ctx)
    moved = next_of(ws, "event", lambda f: f["rev"] != first["rev"])
    assert moved["data"]["rev"] == moved["rev"]
    ws.send(json.dumps({"t": "unsub", "id": "p"}))
    assert next_of(ws, "result")["status"] == OK
    ws.send(json.dumps({"t": "unsub", "id": "p"}))
    assert next_of(ws, "result")["status"] == MISSING
    ws.close()


def test_the_welcome_names_the_ops_and_topics_and_hello_carries_the_key_when_no_header_does(
    served: Served,
) -> None:
    ws = served.open()
    ws.send(json.dumps({**HELLO, "key": served.key, "future": 1}))  # an unknown field is ignored
    welcome = next_of(ws, "welcome")
    assert welcome["ops"] == list(protocol.OPS) and welcome["topics"] == list(protocol.TOPICS)
    assert welcome["server"]["pid"] > 0
    assert next_of(ws, "tick")["now"]
    ws.close()


@pytest.mark.parametrize(
    ("hello", "kind", "code"),
    [
        ({**HELLO, "protocol": 2}, "protocol", OTHER_PROTOCOL),
        ({**HELLO, "key": "wrong"}, "key", KEY_REPLACED),
        (HELLO, "key", KEY_REPLACED),
        ({"t": "call", "id": "x", "op": "board.get"}, "frame", BAD_FRAME),
    ],
)
def test_a_hello_that_is_refused_says_why_and_closes(
    served: Served, hello: dict[str, Any], kind: str, code: int
) -> None:
    ws = served.open()
    ws.send(json.dumps(hello))
    frame = json.loads(ws.recv(timeout=WAIT_S))
    assert (frame["t"], frame["code"]) == ("error", kind)
    if kind == "protocol":
        assert (
            "protocol 1; the client speaks protocol 2: use a client of chantier t" in frame["error"]
        )
    assert closed_with(ws) == code


def test_a_socket_with_no_hello_is_closed_and_a_foreign_cookie_is_refused(served: Served) -> None:
    ws = served.open()
    assert closed_with(ws) == TIMED_OUT
    cookie = keys.set_cookie(served.key).split(";")[0]
    with pytest.raises(InvalidStatus) as refused:
        served.open(additional_headers={"Cookie": cookie}, origin="http://127.0.0.1:1")
    assert refused.value.response.status_code == NO_KEY
    own = served.open(
        additional_headers={"Cookie": cookie}, origin=f"http://127.0.0.1:{served.port}"
    )
    own.send(json.dumps(HELLO))
    assert next_of(own, "welcome")
    own.close()
    with pytest.raises(InvalidStatus) as bad:
        served.open(additional_headers={keys.HEADER: "wrong"})
    assert bad.value.response.status_code == NO_KEY


def test_subscriptions_are_limited_to_32_and_waiting_sockets_to_16(served: Served) -> None:
    ws = served.welcomed()
    for n in range(LIMIT + 1):
        ws.send(json.dumps({"t": "sub", "id": f"s{n}", "topic": "board", "args": {}}))
    statuses = {f["id"]: f["status"] for f in (next_of(ws, "result") for _ in range(LIMIT + 1))}
    assert statuses.pop(f"s{LIMIT}") == TOO_MANY and set(statuses.values()) == {200}
    ws.close()
    waiting = [served.open() for _ in range(times.MAX_WAITING)]
    with pytest.raises(InvalidStatus) as full:
        served.open()
    assert full.value.response.status_code == BUSY
    for ws in waiting:
        ws.close()


def test_a_body_over_the_limit_is_refused_with_413_before_it_is_read(served: Served) -> None:
    head = (
        "POST /api/v1/call/board.get HTTP/1.1\r\nHost: x\r\nContent-Type: application/json\r\n"
        f"Content-Length: {times.MAX_FRAME + 1}\r\nConnection: close\r\n\r\n"
    )
    with socket.create_connection(("127.0.0.1", served.port), timeout=WAIT_S) as conn:
        conn.sendall(head.encode())
        assert conn.recv(64).startswith(b"HTTP/1.1 413")


def test_a_subscription_whose_first_reading_fails_answers_500_and_frees_its_slot(
    served: Served, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = served.welcomed()

    def broken(*_: Any, **__: Any) -> None:
        raise OSError("the record cannot be read")

    with monkeypatch.context() as patch:
        patch.setattr(served.ctx.push, "subscribe", broken)
        ws.send(json.dumps({"t": "sub", "id": "x", "topic": "board", "args": {}}))
        assert next_of(ws, "result")["status"] == SERVER_FAULT
    ws.send(json.dumps({"t": "sub", "id": "x", "topic": "board", "args": {}}))  # the id is free
    assert next_of(ws, "result")["status"] == OK
    ws.close()


def test_the_65th_welcomed_client_is_told_busy_and_closed_with_1013(served: Served) -> None:
    deadline = time.monotonic() + WAIT_S
    while any(c.welcomed for c in served.ctx.sockets) and time.monotonic() < deadline:
        time.sleep(0.02)  # the sockets of the tests before are gone
    full = [served.welcomed() for _ in range(times.MAX_CLIENTS)]
    ws = served.open(additional_headers={keys.HEADER: served.key})
    ws.send(json.dumps(HELLO))
    frame = json.loads(ws.recv(timeout=WAIT_S))
    assert (frame["t"], frame["code"]) == ("error", "busy")
    assert closed_with(ws) == TRY_AGAIN
    for each in full:
        each.close()


def test_a_replaced_key_closes_the_sockets_that_used_it(served: Served) -> None:
    ws = served.welcomed()
    state.set_key(served.repo.git_dir, "a-new-key")
    try:
        assert closed_with(ws) == KEY_REPLACED
    finally:
        state.set_key(served.repo.git_dir, served.key)


def test_a_stopping_server_closes_each_socket_with_1001(served: Served) -> None:
    ws = served.welcomed()
    served.ctx.stop()  # `_run`'s stop path
    assert closed_with(ws) == GOING_AWAY

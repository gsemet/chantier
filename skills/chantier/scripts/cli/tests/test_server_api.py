"""The server's API (protocol 1), called in-process on a prepared batch: the ops' arguments, the
topics through the push loop and the long-poll, the key and origin rules, CORS, the relative
`Location`, the PRs topic's rule. No sleep: the loop is driven with a clock, the hold with a short
time."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import Chantier
from test_board_prs import Board, served

from chantier.board import key as keys
from chantier.board import routes
from chantier.board.api import ops, protocol, times, topics
from chantier.board.api.push import PushLoop, Want
from chantier.board.context import Request

OK, BAD, NO_KEY, NOT_FOUND, TOO_MANY, UNSUPPORTED = 200, 400, 401, 404, 429, 415
PREFLIGHT, SEE_OTHER, SUBS_LIMIT, TWO, ACCEPTED, CONFLICT = 204, 303, 32, 2, 202, 409
TERRA = "gpt-6.1-terra"
HOST = "board.local:8080"


@pytest.fixture
def board(repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch) -> Board:
    monkeypatch.setenv(times.TEST_ENV, "0.5:0.05:1:1")
    found = served(repo, chantier, monkeypatch)
    found.ctx.push = PushLoop(found.ctx)
    return found


def loop_of(b: Board) -> PushLoop:
    found: PushLoop = b.ctx.push
    assert found is not None
    return found


def http(
    b: Board, method: str, path: str, body: object = None, key: bool = True, **headers: str
) -> tuple[int, dict[str, Any], dict[str, str]]:
    head = {"host": HOST, "content-type": "application/json", **headers}
    if key:
        head[keys.HEADER] = b.key
    raw = b"" if body is None else json.dumps(body).encode()
    reply = routes.handle(b.ctx, Request(method, path, {}, head, raw))
    data = json.loads(reply.body) if reply.body.startswith(b"{") else {}
    return reply.status, data, reply.headers


def call(b: Board, op: str, args: object = None) -> tuple[int, dict[str, Any]]:
    status, data, _ = http(b, "POST", f"/api/v1/call/{op}", {} if args is None else args)
    return status, data


def warm(b: Board) -> None:
    """Two looks start the live reading and let its mark settle: the rev moves until then."""
    for _ in range(3):
        call(b, "project.state", {"project": b.id})


def _required(op: str) -> list[str]:
    schema = protocol.OP_ARGS[op].model_json_schema()
    return list(schema.get("required", []))


def test_every_op_refuses_what_its_arguments_do_not_allow(board: Board) -> None:
    for op in protocol.OPS:  # one batch for all: a board takes a quarter second to prepare
        assert call(board, op, {"nothing_like_it": 1})[0] == BAD, op
        if _required(op):
            assert call(board, op, {})[0] == BAD, op
            assert call(board, op, {_required(op)[0]: 5})[0] == BAD, op


def test_an_unknown_op_a_bad_body_an_unknown_project(board: Board) -> None:
    assert call(board, "no.such")[0] == NOT_FOUND
    assert http(board, "POST", "/api/v1/call/board.get", [1])[0] == BAD
    assert call(board, "project.state", {"project": "nope"})[0] == NOT_FOUND


def test_the_reads_and_the_state_rev(board: Board) -> None:
    status, data = call(board, "board.get")
    assert (status, data["data"]["protocols"]) == (OK, [1])
    args = {"project": board.id}
    warm(board)
    state = call(board, "project.state", args)[1]["data"]
    again = call(board, "project.state", {**args, "rev": state["rev"]})[1]["data"]
    assert again == {"changed": False, "rev": state["rev"]}
    assert call(board, "project.tree", args)[0] == OK
    assert call(board, "project.file", {**args, "path": "no/such.md"})[0] == NOT_FOUND


def test_a_topic_sends_once_then_only_on_a_change(board: Board) -> None:
    warm(board)
    loop, seen = loop_of(board), list[dict[str, Any]]()
    sub = loop.subscribe("project", {"project": board.id}, seen.append, sub_id="a")
    assert not isinstance(sub, ops.Result) and len(seen) == 1
    first = seen[0]
    assert (first["sub"], first["topic"]) == ("a", "project")
    loop.poll(0.0)
    kept = len(seen)
    loop.poll(10.0)
    loop.poll(20.0)
    assert len(seen) == kept  # nothing moved
    board.edit(title="moved")
    loop.poll(30.0)
    assert len(seen) == kept + 1 and seen[-1]["rev"] != first["rev"]
    assert loop.due(30.1) is False and loop.due(31.0) is True
    loop.unsubscribe(sub)
    assert loop.watching() == 0


def test_clients_that_ask_the_same_share_one_reading(board: Board) -> None:
    loop, a, b = loop_of(board), list[dict[str, Any]](), list[dict[str, Any]]()
    loop.subscribe("project", {"project": board.id}, a.append, sub_id="a")
    loop.subscribe("project", {"project": board.id}, b.append, sub_id="b")
    board.edit(title="moved")
    loop.poll(0.0)
    assert len(a) == len(b) == TWO and a[-1]["rev"] == b[-1]["rev"]


@pytest.mark.parametrize(
    ("name", "args", "status"),
    [
        ("nope", {}, NOT_FOUND),
        ("project", {"project": "nope"}, NOT_FOUND),
        ("project", {}, BAD),
        ("board", {"x": 1}, BAD),
    ],
)
def test_a_subscription_is_refused(
    board: Board, name: str, args: dict[str, Any], status: int
) -> None:
    got = loop_of(board).subscribe(name, args, lambda e: None)
    assert isinstance(got, ops.Result) and got.status == status
    assert loop_of(board).watching() == 0


def test_the_long_poll_answers_at_once_then_holds_empty(board: Board) -> None:
    warm(board)
    body: dict[str, Any] = {
        "subs": [{"key": "p", "topic": "project", "args": {"project": board.id}, "rev": None}]
    }
    status, data, _ = http(board, "POST", "/api/v1/poll", body)
    assert status == OK and [e["key"] for e in data["events"]] == ["p"]
    body["subs"][0]["rev"] = data["events"][0]["rev"]
    status, data, _ = http(board, "POST", "/api/v1/poll", body)
    assert (status, data["events"]) == (OK, [])
    assert loop_of(board).watching() == 0
    body["subs"][0]["topic"] = "nope"
    assert http(board, "POST", "/api/v1/poll", body)[0] == NOT_FOUND
    many = {"subs": [{"key": str(i), "topic": "board", "args": {}} for i in range(SUBS_LIMIT + 1)]}
    assert http(board, "POST", "/api/v1/poll", many)[0] == TOO_MANY
    held = loop_of(board).hold([Want("k", "board", {}, None)], 0.0)
    assert not isinstance(held, ops.Result) and [e["key"] for e in held] == ["k"]


def test_the_prs_topic_reads_no_forge_once_every_pr_is_done(board: Board) -> None:
    loop, seen = loop_of(board), list[dict[str, Any]]()
    args = {"project": board.id}
    assert not isinstance(loop.subscribe("prs", args, seen.append, sub_id="p"), ops.Result)
    assert board.calls
    board.forge = {40 + i: {"state": "merged"} for i in range(4)}
    board.now += 3600
    loop.poll(0.0)
    done_calls = len(board.calls)
    assert seen[-1]["data"]["all_done"] is True
    for n in range(1, 4):
        board.now += 3600
        loop.poll(10.0 * n)
    assert len(board.calls) == done_calls  # every PR done: no new read until the links change


KEYS = [
    ("no key", {}, False, NO_KEY),
    ("header", {}, True, OK),
    ("header, another origin", {"origin": "http://evil.example"}, True, OK),
    ("cookie, own origin", {"cookie": "KEY", "origin": f"http://{HOST}"}, False, OK),
    ("cookie, no origin", {"cookie": "KEY"}, False, OK),
    ("cookie, other origin", {"cookie": "KEY", "origin": "http://evil.example"}, False, NO_KEY),
    ("cookie, cross-site", {"cookie": "KEY", "sec-fetch-site": "cross-site"}, False, NO_KEY),
    (
        "cookie, proxy host",
        {"cookie": "KEY", "origin": "https://pub.example", "x-forwarded-host": "pub.example"},
        False,
        OK,
    ),
    ("not json", {"content-type": "text/plain"}, True, UNSUPPORTED),
]


def test_the_key_and_the_origin(board: Board) -> None:
    cookie = keys.set_cookie(board.key).split(";")[0]
    for name, headers, key, status in KEYS:
        sent = {k: (cookie if v == "KEY" else v) for k, v in headers.items()}
        got, _, answer = http(board, "POST", "/api/v1/call/board.get", {}, key, **sent)
        assert got == status, name
        assert answer["Access-Control-Allow-Origin"] == "*"
        assert "Access-Control-Allow-Credentials" not in answer


def test_an_old_route_answers_404_even_for_a_post_a_cookie_carries(board: Board) -> None:
    cookie = keys.set_cookie(board.key).split(";")[0]
    for path in ("/api/seats", "/api/projects/x/backlog/new", "/api/writer/sync"):
        for kind in ("text/plain", "application/json"):
            head = {"cookie": cookie, "content-type": kind}
            got, _, _ = http(board, "POST", path, {}, False, origin="http://evil.example", **head)
            assert got == NOT_FOUND, (path, kind)  # 404 for any origin: nothing to protect
            got, _, _ = http(board, "POST", path, {}, False, **head)
            assert got == NOT_FOUND, (path, kind)


def test_a_topic_that_fails_unexpectedly_is_skipped_and_the_loop_goes_on(
    board: Board, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    loop, seen = loop_of(board), list[dict[str, Any]]()
    assert not isinstance(loop.subscribe("board", {}, seen.append, sub_id="b"), ops.Result)

    def broken(*_: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(topics, "read", broken)
    loop.poll(0.0)  # no error leaves the pass: the push thread would end the server
    assert "skipped board: boom" in capsys.readouterr().err
    assert loop.watching() == 1


def test_long_polls_held_at_once_are_capped(board: Board) -> None:
    loop = loop_of(board)
    with loop._lock:  # the cap's counter, as MAX_POLLS holds would leave it
        loop._polls = times.MAX_POLLS
    body: dict[str, Any] = {"subs": [{"key": "b", "topic": "board", "args": {}, "rev": None}]}
    status, data, _ = http(board, "POST", "/api/v1/poll", body)
    assert status == TOO_MANY and "long-polls" in data["error"]
    with loop._lock:
        loop._polls = 0
    assert http(board, "POST", "/api/v1/poll", body)[0] == OK
    assert loop._polls == 0  # a hold gives its place back


def test_the_preflight_needs_no_key(board: Board) -> None:
    status, _, answer = http(board, "OPTIONS", "/api/v1/call/board.get", key=False)
    assert status == PREFLIGHT and answer["Access-Control-Allow-Origin"] == "*"
    assert keys.HEADER in answer["Access-Control-Allow-Headers"].lower()


def test_the_key_in_the_url_goes_to_a_relative_location(board: Board) -> None:
    req = Request("GET", "/pre/fix/projects/x", {"k": board.key, "a": "1"}, {"host": HOST})
    reply = routes.handle(board.ctx, req)
    assert reply.status == SEE_OTHER and reply.headers["Location"] == "./x?a=1"

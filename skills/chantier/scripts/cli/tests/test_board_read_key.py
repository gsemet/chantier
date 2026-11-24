"""The board's two keys: the private one acts, the public read-only one shows the board and acts on
nothing. In-process through the routes, on a prepared board; the WebSocket's side is in
`test_server_api_ws.py`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from api_client import settled
from batch_helpers import changes, record, write_record
from conftest import PLUGIN_ROOT, Chantier
from test_board_history import entry
from test_board_prs import Board, served

from chantier.board import address, guard, reads, routes
from chantier.board import key as keys
from chantier.board.api import auth, ops, protocol, times, topics
from chantier.board.api.push import PushLoop
from chantier.board.context import Request
from chantier.hub import state

OK, FORBIDDEN, NO_KEY, NOT_FOUND, SEE_OTHER = 200, 403, 401, 404, 303
HOST = "board.local:8080"
LAN = "192.168.1.20"
REFUSED = "refused: the read-only key acts on nothing: use the private link"
NOT_READS = sorted(set(protocol.OP_ARGS) - ops.READ_OPS)
READS = sorted(ops.READ_OPS)


@pytest.fixture
def board(repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch) -> Board:
    monkeypatch.setenv(times.TEST_ENV, "0.5:0.05:1:1")
    found = served(repo, chantier, monkeypatch)
    found.ctx.push = PushLoop(found.ctx)
    return found


def _read_key(b: Board) -> str:
    found = b.ctx.key.read_current()
    assert found and found != b.key
    return found


def _http(
    b: Board, method: str, path: str, body: object = None, **headers: str
) -> tuple[int, dict[str, Any], dict[str, str]]:
    head = {"host": HOST, "content-type": "application/json", **headers}
    raw = b"" if body is None else json.dumps(body).encode()
    reply = routes.handle(b.ctx, Request(method, path, {}, head, raw))
    data = json.loads(reply.body) if reply.body.startswith(b"{") else {}
    return reply.status, data, reply.headers


def _call(b: Board, secret: str, op: str, args: object = None) -> tuple[int, dict[str, Any]]:
    got = _http(
        b, "POST", f"/api/v1/call/{op}", {} if args is None else args, **{keys.HEADER: secret}
    )
    return got[0], got[1]


def _args(b: Board, op: str) -> dict[str, Any]:
    fill = {"project": b.id, "path": "no/such.md"}
    required = protocol.OP_ARGS[op].model_json_schema().get("required", [])
    return {name: fill[name] for name in required if name in fill}


@pytest.mark.parametrize("op", NOT_READS)
def test_every_op_outside_the_allow_list_is_refused_to_the_read_key_and_writes_nothing(
    board: Board, op: str
) -> None:
    before = board.planning()
    status, data = _call(board, _read_key(board), op, _args(board, op))
    assert (status, data["error"]) == (FORBIDDEN, REFUSED)
    assert board.planning() == before


def test_an_op_added_later_is_refused_to_the_read_key_with_no_edit_here(board: Board) -> None:
    assert _call(board, _read_key(board), "future.op", {})[0] == FORBIDDEN
    assert _call(board, board.key, "future.op", {})[0] == NOT_FOUND


@pytest.mark.parametrize("op", READS)
def test_every_op_of_the_allow_list_answers_the_read_key(board: Board, op: str) -> None:
    status, data = _call(board, _read_key(board), op, _args(board, op))
    assert status == (NOT_FOUND if op == "project.file" else OK), data
    assert _call(board, board.key, op, _args(board, op))[0] == status


def test_the_allow_list_holds_only_ops_that_exist() -> None:
    assert set(protocol.OP_ARGS) >= ops.READ_OPS and set(protocol.TOPICS) >= topics.READ_TOPICS


def test_the_poll_answers_the_read_key_for_a_read_topic_and_refuses_the_others(
    board: Board,
) -> None:
    secret = {keys.HEADER: _read_key(board)}
    for topic in protocol.TOPICS:
        body: dict[str, Any] = {"subs": [{"key": "a", "topic": topic, "args": {}, "rev": None}]}
        status, data, _ = _http(board, "POST", "/api/v1/poll", body, **secret)
        if topic in topics.READ_TOPICS:
            assert status != FORBIDDEN, topic
        else:
            assert (status, data["error"]) == (FORBIDDEN, REFUSED), topic
    reading: dict[str, Any] = {"subs": [{"key": "a", "topic": "board", "args": {}, "rev": None}]}
    assert _http(board, "POST", "/api/v1/poll", reading, **secret)[0] == OK


def test_both_keys_pass_in_the_header_and_the_cookies_and_the_answer_says_which(
    board: Board,
) -> None:
    read, name = _read_key(board), board.ctx.cookie
    own = {"origin": f"http://{HOST}"}
    cases = [
        ({keys.HEADER: board.key}, "write"),
        ({keys.HEADER: read}, "read"),
        ({"cookie": f"{name}={board.key}", **own}, "write"),
        ({"cookie": f"{name}_read={read}", **own}, "read"),
        ({"cookie": f"{name}_read={read}; {name}={board.key}", **own}, "write"),  # private wins
        ({"cookie": f"{name}={read}", **own}, None),  # a key in the other's cookie is no key
        ({"cookie": f"{name}_read={board.key}", **own}, None),
        ({keys.HEADER: "wrong"}, None),
    ]
    for headers, access in cases:
        status, _, answer = _http(board, "POST", "/api/v1/call/board.get", {}, **headers)
        assert status == (OK if access else NO_KEY), headers
        assert answer.get(auth.ACCESS) == access, headers
        assert answer["Access-Control-Expose-Headers"] == auth.ACCESS
        request = Request("GET", "/", {}, {"host": HOST, **headers})
        assert guard.access(request, board.key, name, read) == access
    # the header and a cookie of the other kind: the private key still wins
    mixed = {keys.HEADER: read, "cookie": f"{name}={board.key}", **own}
    assert _http(board, "POST", "/api/v1/call/board.get", {}, **mixed)[2][auth.ACCESS] == "write"


def test_the_exchange_of_a_link_sets_only_the_cookie_of_the_key_it_held(board: Board) -> None:
    read, name = _read_key(board), board.ctx.cookie
    for secret, cookie in ((read, f"{name}_read"), (board.key, name)):
        reply = routes.handle(board.ctx, Request("GET", "/", {"k": secret}, {"host": HOST}))
        assert reply.status == SEE_OTHER
        got = reply.all_headers()["Set-Cookie"]
        assert got.startswith(f"{cookie}={secret};")
        assert (f"{name}_read=" in got) == (cookie != name)
    wrong = routes.handle(board.ctx, Request("GET", "/", {"k": "nope"}, {"host": HOST}))
    assert wrong.status == NO_KEY


def test_the_page_and_the_file_route_take_either_key_and_a_write_needs_the_private_one(
    board: Board,
) -> None:
    read = _read_key(board)
    for secret in (read, board.key):
        head = {"host": HOST, keys.HEADER: secret}
        assert routes.handle(board.ctx, Request("GET", "/api/board", {}, head)).status == OK
        file = f"/api/v1/projects/{board.id}/file"
        got = routes.handle(board.ctx, Request("GET", file, {"path": "no/such.md"}, head))
        assert got.status == NOT_FOUND  # reached the route: the file is not there
    head = {"host": HOST, keys.HEADER: read, "content-type": "application/json"}
    put = routes.handle(board.ctx, Request("PUT", "/api/board", {}, head, b"{}"))
    assert (put.status, put.body.decode().strip()) == (FORBIDDEN, REFUSED)


def test_the_welcome_frame_carries_the_access() -> None:
    assert "access" in protocol.Welcome.model_json_schema()["required"]


def test_the_read_key_never_sees_the_private_key_in_the_boards_data(
    board: Board, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(address, "_default_route_address", lambda: LAN)
    board.ctx.bound = ("0.0.0.0", 8765)
    read = _read_key(board)
    private = _call(board, board.key, "board.get")[1]["data"]["local_url"]
    shown = _call(board, read, "board.get")[1]["data"]["local_url"]
    assert private.endswith(f"?k={board.key}") and shown.endswith(f"?k={read}")
    seen: list[dict[str, Any]] = []
    sub = board.ctx.push.subscribe("board", {}, seen.append, access="read")
    assert not isinstance(sub, ops.Result) and seen and board.key not in json.dumps(seen)
    assert board.key not in json.dumps(reads.for_read_key(board.ctx, {"local_url": private}))


def test_a_server_json_with_only_a_key_gets_a_read_key_and_keeps_its_key(
    board: Board,
) -> None:
    git_dir = board.ctx.projects.home.git_dir
    home = board.ctx.projects.home
    state.modify(git_dir, lambda data: data.pop("read_key", None))
    assert keys.public_key(home) == ""
    assert keys.load_or_create(home) == board.key
    first = keys.public_key(home)
    assert first and first != board.key
    assert keys.load_or_create(home) == board.key and keys.public_key(home) == first
    assert board.ctx.key.read_current() == first  # read again when the file changes
    # a lost read key is put back by the server's tick
    state._asserted[git_dir] = {"pid": 1}
    state.modify(git_dir, lambda data: data.pop("read_key"))
    state.reassert_server(git_dir, board.key, first)
    assert keys.public_key(home) == first
    # `--new-key` replaces both
    assert keys.load_or_create(home, new=True) != board.key
    assert keys.public_key(home) not in ("", first)
    assert board.ctx.key.current() != board.key and board.ctx.key.read_current() != first


def test_a_new_key_closes_nothing_but_old_links_stop_working(board: Board) -> None:
    old_read = _read_key(board)
    keys.load_or_create(board.ctx.projects.home, new=True)
    assert _call(board, old_read, "board.get")[0] == NO_KEY
    assert _call(board, board.key, "board.get")[0] == NO_KEY
    assert _call(board, board.ctx.key.read_current(), "board.get")[0] == OK


MIN_SHIPPED = 20
OLD_WORDS = ("the board's key", "revokes the key")


def test_shipped_texts_name_the_two_keys(tmp_path: Path) -> None:
    web = PLUGIN_ROOT / "skills/chantier/scripts/cli/src/chantier/clients/web/js/i18n"
    shipped = [
        PLUGIN_ROOT / "AGENTS.md",
        *(PLUGIN_ROOT / "docs").glob("*.md"),
        *(PLUGIN_ROOT / "skills/chantier/references").glob("*.md"),
        *web.glob("*.js"),
    ]
    assert len(shipped) > MIN_SHIPPED
    found = [p.name for p in shipped if any(w in p.read_text(encoding="utf-8") for w in OLD_WORDS)]
    assert found == []
    prepared = tmp_path / "old.md"
    prepared.write_text("holders of the board's key; --new-key revokes the key", encoding="utf-8")
    assert all(w in prepared.read_text(encoding="utf-8") for w in OLD_WORDS)


def test_the_read_key_sees_the_activity_and_the_open_prs_with_no_cost_and_no_round(
    board: Board,
) -> None:
    data = record(board.repo)
    for c in data["crs"]:
        c.update(cost_usd=9.87, cost_unpriced={"opus": 4}, round=3)
    write_record(board.repo, data)
    archives = changes(board.repo) / "5-archives" / "batches"
    archives.mkdir(parents=True, exist_ok=True)
    done = entry("CR-9", ended="2026-11-20T10:00:00Z", cost_usd=7.77, rounds=5)
    done["cost_unpriced"] = {"sonnet": 3}
    closed = {"schema": 1, "batch": "batch-00", "state": "closed", "crs": [done]}
    (archives / "batch-00.json").write_text(json.dumps(closed), encoding="utf-8")
    settled(board.ctx)
    seen: list[dict[str, Any]] = []
    sub = board.ctx.push.subscribe("board", {}, seen.append, access="read")
    assert not isinstance(sub, ops.Result) and seen
    shown = seen[0]["data"]
    line = next(p for p in shown["projects"] if p["id"] == board.id)
    assert shown["activity"] and line["open_prs"]  # the check below is not empty
    for part in (shown["activity"], line["open_prs"]):
        text = json.dumps(part)
        for word in ("cost", "rounds", "round", "unpriced", "7.77", "9.87"):
            assert word not in text, word

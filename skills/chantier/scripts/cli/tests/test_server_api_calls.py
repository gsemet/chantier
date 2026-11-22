"""The good calls of the API: every op's data against the old route's answer or the store, the
`events` topic's cursor, the long-poll woken by a change, the 409 with no live writer, a write from
each cell of the key matrix, the forge read shared by three watchers of the PRs topic."""

from __future__ import annotations

import hashlib
import json
import threading
from typing import Any

import pytest
from conftest import Surface
from test_board_prs import Board
from test_server_api import (
    ACCEPTED,
    CONFLICT,
    HOST,
    NO_KEY,
    NOT_FOUND,
    OK,
    TERRA,
    UNSUPPORTED,
    board,  # noqa: F401 - the fixture
    call,
    http,
    loop_of,
    warm,
)

from chantier.board import key as keys
from chantier.board import reads
from chantier.board.api import ops, protocol, times
from chantier.board.context import Context
from chantier.board.griller import Registry
from chantier.board.projects import Projects
from chantier.board.seats import Seats
from chantier.core.repo import Repo
from chantier.hub import journal as forge_journal
from chantier.hub import state as hub_state
from chantier.hub.board_text import board_text
from chantier.playbook import edit

MANY_LINES, THREE, FIVE = 5, 3, 5


def _same(a: dict[str, Any], b: dict[str, Any], *drop: str) -> None:
    skip = {"now", *drop}
    assert {k: v for k, v in a.items() if k not in skip} == {
        k: v for k, v in b.items() if k not in skip
    }


def _repo(b: Board) -> Repo:
    project = reads.found(b.ctx, b.id)
    assert project is not None
    return project.repo


class Good:
    """Good calls on one board: each answers its status and `ok`, and records its op."""

    def __init__(self, b: Board) -> None:
        self.b, self.seen = b, set[str]()
        self.args: dict[str, Any] = {"project": b.id}

    def __call__(self, op: str, args: object = None, status: int = OK) -> dict[str, Any]:
        self.seen.add(op)
        got, body = call(self.b, op, self.args if args is None else args)
        assert (got, body["ok"]) == (status, True), body
        data: dict[str, Any] = body["data"]
        return data


def test_a_good_call_of_every_op_answers_the_data_its_route_gave_or_the_store_holds(
    board: Board,  # noqa: F811
) -> None:
    good, home = Good(board), board.id
    warm(board)
    assert good("board.get", {})["protocols"] == [1]
    assert "rev" in good("project.state")
    assert "now" in good("costs.get")
    assert "now" in good("prs.get")
    dash = good("dashboard.get", {**good.args, "range": "10"})
    assert dash["range"] == "10" and "now" in dash
    assert good("history.get", {"project": home, "period": "day", "tz": "Europe/Paris"})["today"]
    _same(good("config.get"), edit.config_view(_repo(board)))
    change = {"host": "copilot", "role": "coder", "key": "model", "value": TERRA}
    dry = {**good.args, "changes": [change], "dry_run": True}
    status, put = call(board, "config.put", dry)  # in-project the file is read-only: 409
    good.seen.add("config.put")
    assert status == CONFLICT and put["data"]["ok"] is False
    assert good("costs.recompute", status=ACCEPTED)["computing"] is True
    tree = good("project.tree", {**good.args, "path": ""})
    assert isinstance(tree["files"], list)
    assert good("seats.register", {"project": home, "session": "s1"})["seats"] == 1
    assert board.ctx.seats.count() == 1
    status, body = call(board, "writer.sync", {})  # in-project: no writer to ask
    good.seen.add("writer.sync")
    assert (status, body["data"]["code"], body["data"]["writer"]) == (
        CONFLICT,
        "off",
        {"state": "off"},
    )
    board.ctx.griller = Registry()  # the board's own, made at its start
    item = {**good.args, "item": "nowhere"}
    assert good("griller.get", item)["conversation"] is None
    assert good("griller.stop", item)["stopped"] is False
    assert good("griller.end", item)["ended"] is True
    status, _ = call(board, "griller.send", {**item, "text": "hi", "from": "p"})
    good.seen.add("griller.send")
    assert status == NOT_FOUND  # no such item: refused before anything starts
    _written(good)
    assert good.seen == set(protocol.OPS)


def _written(good: Good) -> None:
    repo, args = _repo(good.b), good.args
    new = good("backlog.new", {**args, "text": "# Fresh idea\n\nWith a body."})
    item = new["item"]
    assert (repo.changes / "1-inbox" / item / "intake" / "request.md").is_file()
    good("backlog.labels", {**args, "items": [item], "add": ["urgent", "web"]})
    good("backlog.group", {**args, "items": [item], "name": "g"})
    good("backlog.ungroup", {**args, "name": "g"})
    moved = good("backlog.move", {**args, "items": [item], "to": "P1"})
    assert moved["results"][0]["ok"] and (repo.changes / "2-backlog" / "P1" / item).is_dir()
    request = repo.changes / "2-backlog" / "P1" / item / "intake" / "request.md"
    base = hashlib.sha256(request.read_bytes()).hexdigest()
    path = "intake/request.md"
    edited = good(
        "backlog.file",
        {**args, "item": item, "path": path, "text": "Edited\n", "base_sha256": base},
    )
    assert request.read_text(encoding="utf-8") == "Edited\n"
    assert edited["sha256"] == hashlib.sha256(b"Edited\n").hexdigest()
    text = good("project.file", {**args, "path": f"2-backlog/P1/{item}/{path}"})
    assert text["text"] == "Edited\n" and text["sha256"] == edited["sha256"]
    good("backlog.move", {**args, "items": [item], "to": "3-ready"})
    assert (repo.changes / "3-ready" / item).is_dir()
    assert good("backlog.next_batch")["results"][0]["ok"]
    shown = good("journal.get")
    assert shown["count"] == len(shown["entries"]) and shown["count"] >= MANY_LINES
    assert good("journal.rescan")["count"] == 0 and good("journal.get")["count"] == 0


def test_the_events_topic_carries_the_journal_lines_after_its_cursor(board: Board) -> None:  # noqa: F811
    repo, loop = _repo(board), loop_of(board)

    def add(text: str) -> None:
        forge_journal.append(repo, [forge_journal.board_event("new", [text], "x")], "board")

    add("old0")
    add("old1")
    args = {"project": board.id}
    fresh, whole, from_one = (list[dict[str, Any]]() for _ in range(3))
    loop.subscribe("events", args, fresh.append, sub_id="fresh")
    loop.subscribe("events", {**args, "after": 0}, whole.append, sub_id="whole")
    loop.subscribe("events", {**args, "after": 1}, from_one.append, sub_id="one")
    assert fresh[0]["data"]["lines"] == []  # by default only new lines come
    assert [e["seq"] for e in whole[0]["data"]["lines"]] == [1, 2] and whole[0]["rev"] == "2"
    assert [e["seq"] for e in from_one[0]["data"]["lines"]] == [2]
    add("n0")
    add("n1")
    loop.poll(0.0)
    assert [e["seq"] for e in fresh[-1]["data"]["lines"]] == [3, 4] and fresh[-1]["rev"] == "4"
    count = len(fresh)
    loop.poll(10.0)
    assert len(fresh) == count  # each line once: no change, no event
    add("last")
    loop.poll(20.0)
    (last,) = fresh[-1]["data"]["lines"]
    said = board_text({**last, "text": "x"})  # the payload's own `text` is the sentence's
    assert last["seq"] == FIVE and last["text"] == said  # its type's sentence
    with (repo.changes / forge_journal.FILE).open("a", encoding="utf-8") as f:
        line = {"v": 2, "seq": 6, "t": "2030-01-01T00:00:00Z", "type": "later@1"}
        f.write(json.dumps(line) + "\n")
    loop.poll(30.0)
    (unknown,) = fresh[-1]["data"]["lines"]
    assert unknown["seq"] == FIVE + 1 and "text" not in unknown  # a type not published: none


def test_a_change_during_the_hold_answers_the_long_poll_before_the_hold_ends(
    board: Board,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(times.TEST_ENV, "0.5:30:1:1")  # a hold far longer than the test
    warm(board)
    loop = loop_of(board)
    sub = {"key": "p", "topic": "project", "args": {"project": board.id}, "rev": None}
    first = http(board, "POST", "/api/v1/poll", {"subs": [sub]})[1]["events"][0]["rev"]
    answers: list[tuple[int, dict[str, Any], dict[str, str]]] = []
    held = threading.Thread(
        target=lambda: answers.append(
            http(board, "POST", "/api/v1/poll", {"subs": [{**sub, "rev": first}]})
        )
    )
    held.start()
    while loop.watching() == 0:  # the request is holding
        held.join(0.01)
    board.edit(title="moved")
    loop.poll(1000.0)  # the push thread's pass
    held.join(10)
    assert not held.is_alive()
    status, data, _ = answers[0]
    assert status == OK and [e["key"] for e in data["events"]] == ["p"]
    assert data["events"][0]["rev"] != first and loop.watching() == 0


def _surface_ctx() -> Context:
    found = Repo.find(project="demo", readonly=True)
    projects = Projects(found, found.surface, [])
    return Context(
        projects, keys.KeyFile(keys.key_path(found)), Seats(projects), "t", lambda: None, None
    )


def test_a_write_with_no_live_writer_answers_409_and_writes_nothing(surface: Surface) -> None:
    ctx = _surface_ctx()
    args = {"project": "demo"}
    inbox = surface.project / "changes" / "1-inbox"
    assert ops.call(ctx, "backlog.new", {**args, "text": "# kept"}).status == OK  # a writer lives
    hub_state.modify(surface.root / ".git", lambda data: data.pop(hub_state.WRITER, None))
    before = sorted(p.name for p in inbox.iterdir())
    for op, more in (
        ("backlog.new", {"text": "# refused"}),
        ("backlog.move", {"items": ["kept"], "to": "P1"}),
    ):
        got = ops.call(ctx, op, {**args, **more})
        assert (got.status, got.ok) == (CONFLICT, False), op
        assert got.error and "writer" in got.error, op
    assert sorted(p.name for p in inbox.iterdir()) == before
    sync = ops.call(ctx, "writer.sync", {})
    assert sync.status == CONFLICT and sync.data and sync.data["code"] == "off"


def test_a_write_from_each_cell_of_the_key_matrix(board: Board) -> None:  # noqa: F811
    cookie = keys.set_cookie(board.key, board.ctx.cookie).split(";")[0]
    own = {"cookie": cookie, "origin": f"http://{HOST}"}
    foreign = {"origin": "http://evil.example"}
    cases = [
        ("header, another origin", foreign, True, OK),
        ("header, not json", {"content-type": "text/plain"}, True, UNSUPPORTED),
        ("cookie, own origin (in-project)", own, False, OK),
        ("cookie, another origin", {"cookie": cookie, **foreign}, False, NO_KEY),
        ("no key", {}, False, NO_KEY),
    ]
    for n, (name, headers, key, status) in enumerate(cases):
        body = {"project": board.id, "text": f"# matrix {n}"}
        got, _, _ = http(board, "POST", "/api/v1/call/backlog.new", body, key, **headers)
        assert got == status, name
    filed = sorted(p.name for p in (_repo(board).changes / "1-inbox").iterdir())
    assert filed == ["matrix-0", "matrix-2"]  # only the two that passed wrote


def test_three_watchers_of_the_prs_cost_one_forge_read_per_ten_seconds(board: Board) -> None:  # noqa: F811
    loop, seen = loop_of(board), list[dict[str, Any]]()
    for name in "abc":
        loop.subscribe("prs", {"project": board.id}, seen.append, sub_id=name)
    assert len(board.calls) == 1 and len(seen) == THREE  # three watchers, one read
    for step in range(1, 25):  # 2 s a pass for 48 s: the loop's clock and the reader's
        board.now = float(step * 2)
        loop.poll(board.now)
    assert len(board.calls) == 1 + 4  # at 10, 20, 30 and 40 s, never more

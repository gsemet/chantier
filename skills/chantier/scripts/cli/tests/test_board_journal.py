"""The board's backlog writes leave one `board@1` line each in their project's forge journal, which
the Chief of Staff's watcher reads; a refusal, a drop on the same column and a rescan leave none."""

from __future__ import annotations

import hashlib
import json
import shutil
from http import HTTPStatus
from typing import Any

import pytest

from chantier.board import key as keys
from chantier.board import routes
from chantier.board.context import Context, Request
from chantier.board.projects import Projects
from chantier.board.seats import Seats
from chantier.core.repo import Repo
from chantier.hub import journal as forge_journal

SLUG = "an-idea"
STEPS: list[tuple[str, str, dict[str, Any], str, bool]] = [
    ("backlog/new", "POST", {"text": "an idea"}, "new", True),
    ("backlog/move", "POST", {"items": [SLUG], "to": "P2"}, "move", True),
    ("backlog/move", "POST", {"items": [SLUG], "to": "P1"}, "move", True),
    ("backlog/move", "POST", {"items": [SLUG], "to": "P2"}, "move", True),
    ("backlog/move", "POST", {"items": [SLUG], "to": "P1"}, "move", True),
    ("backlog/labels", "POST", {"items": [SLUG], "add": "x"}, "label", False),
    ("backlog/group", "POST", {"items": [SLUG], "name": "g"}, "group", False),
    ("backlog/ungroup", "POST", {"name": "g"}, "ungroup", False),
    ("backlog/move", "POST", {"items": [SLUG], "to": "3-ready"}, "move", True),
    ("backlog/next-batch", "POST", {}, "next-batch", False),
]


def _write_call(surface: Any) -> Any:
    """The board's write routes called in-process on a surface of two projects: `demo`, `other`."""
    shutil.copytree(surface.clone, surface.root / "projects" / "other" / ".repo")
    (surface.root / "projects" / "other" / "checkout.yml").write_text("repo: .repo\n")
    repo_ = Repo.find(project="demo", readonly=True)
    projects = Projects(repo_, repo_.surface, [])
    secret = keys.load_or_create(repo_)
    ctx = Context(projects, keys.KeyFile(keys.key_path(repo_)), Seats(projects), "t", lambda: None)

    def call(method: str, route: str, body: dict[str, Any], project: str = "demo") -> Any:
        head = {keys.HEADER: secret, "content-type": "application/json", "host": "board"}
        path = f"/api/projects/{project}/{route}"
        reply_ = routes.handle(ctx, Request(method, path, {}, head, json.dumps(body).encode()))
        return reply_.status, json.loads(reply_.body)

    return call


def _lines(repo: Repo) -> list[dict[str, Any]]:
    return [e for e in forge_journal.read(repo.changes)[0] if e["type"] == "board@1"]


def test_each_backlog_write_adds_one_board_line_to_its_projects_forge_journal(
    surface: Any,
) -> None:
    call = _write_call(surface)
    demo = Repo.find(project="demo", readonly=True)
    for route, method, data, action, wakes in STEPS:
        before = len(_lines(demo))
        code, answer = call(method, route, data)
        assert code == HTTPStatus.OK, answer
        assert len(_lines(demo)) == before + 1
        line, entry = _lines(demo)[-1], answer["journal"][0]
        assert (line["source"], line["action"], line["wakes"]) == ("board", action, wakes)
        assert (line["items"], line["text"]) == (entry["items"], entry["text"])
    moves = [e for e in _lines(demo) if e["action"] == "move"]
    assert (moves[1]["items"], moves[1]["text"]) == (moves[3]["items"], moves[3]["text"])
    assert moves[1]["seq"] != moves[3]["seq"]  # two identical moves are two lines


def test_a_refusal_a_rescan_and_another_project_leave_no_line_here(surface: Any) -> None:
    call = _write_call(surface)
    demo = Repo.find(project="demo", readonly=True)
    for route, method, data, *_ in STEPS[:2] + STEPS[-2:-1]:
        assert call(method, route, data)[0] == HTTPStatus.OK
    shown = demo.changes / "3-ready" / SLUG / "intake" / "request.md"
    sha = hashlib.sha256(shown.read_bytes()).hexdigest()
    edit = {"item": SLUG, "path": "intake/request.md", "text": "edited\n", "base_sha256": sha}
    before = len(_lines(demo))
    assert call("PUT", "backlog/file", {**edit, "base_sha256": "0" * 64})[0] == HTTPStatus.CONFLICT
    assert call("POST", "backlog/move", {"items": ["nope"], "to": "P1"})[0] == HTTPStatus.CONFLICT
    same = {"items": [SLUG], "to": "3-ready"}  # a drop on the item's own column
    assert call("POST", "backlog/move", same)[0] == HTTPStatus.OK
    assert call("POST", "journal/rescan", {})[0] == HTTPStatus.OK
    assert len(_lines(demo)) == before
    assert call("PUT", "backlog/file", edit)[0] == HTTPStatus.OK
    assert _lines(demo)[-1]["action"] == "edit" and _lines(demo)[-1]["wakes"] is True
    other = Repo.find(project="other", readonly=True)
    assert forge_journal.read(other.changes)[0] == []
    assert call("POST", "backlog/new", {"text": "elsewhere"}, "other")[0] == HTTPStatus.OK
    assert [e["action"] for e in _lines(other)] == ["new"]
    assert not any(e.get("items") == ["elsewhere"] for e in _lines(demo))


def test_a_board_event_its_model_refuses_leaves_the_write_and_names_the_skipped_line(
    surface: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    # a prepared refusal: an event builder patched to add a field its model does not hold
    build = forge_journal.board_event
    monkeypatch.setattr(forge_journal, "board_event", lambda *a: {**build(*a), "unexpected": 1})
    call = _write_call(surface)
    demo = Repo.find(project="demo", readonly=True)
    code, answer = call("POST", "backlog/new", {"text": "an idea"})
    assert code == HTTPStatus.OK and answer["ok"] is True
    assert answer["error"].startswith("skipped: journal payload board@1:")
    assert (demo.changes / "1-inbox" / SLUG).exists() and answer["journal"]
    assert _lines(demo) == []


def test_the_new_route_files_a_title_above_the_text_and_refuses_a_paragraph_without_one(
    surface: Any,
) -> None:
    call = _write_call(surface)
    demo = Repo.find(project="demo", readonly=True)
    paragraph = "a long request " * 10
    code, answer = call("POST", "backlog/new", {"text": paragraph})
    assert code != HTTPStatus.OK and "has no short title" in answer["error"], answer
    assert not (demo.changes / "1-inbox").exists() or not list((demo.changes / "1-inbox").iterdir())
    code, answer = call("POST", "backlog/new", {"text": paragraph, "title": "A short title"})
    assert code == HTTPStatus.OK, answer
    filed = demo.changes / "1-inbox" / "a-short-title" / "intake" / "request.md"
    assert filed.read_bytes() == b"# A short title\n\n" + paragraph.encode()
    assert call("POST", "backlog/new", {"text": "x", "title": 7})[0] != HTTPStatus.OK

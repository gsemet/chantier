"""The board's Griller through the published API: the four ops, the topic and the write guard
(`board/write_api.py`), on the engine's stand-in (`test_board_griller.py`)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from api_client import call_op
from test_board_griller import (  # noqa: F401 - in_project is the fixture
    WAIT_S,
    World,
    _send,
    in_project,
)

from chantier.board.api import protocol, topics
from chantier.board.context import Context
from chantier.board.key import KeyFile
from chantier.board.projects import open_projects
from chantier.board.seats import Seats
from chantier.lifecycle import backlog

BAD_REQUEST = 400


class Api:
    def __init__(self, w: World, tmp: Path) -> None:
        projects = open_projects()
        self.w = w
        self.ctx = Context(
            projects, KeyFile(tmp / "key.json"), Seats(projects), "0", lambda: None, None
        )
        (tmp / "key.json").write_text('{"key": "k"}', encoding="utf-8")
        self.ctx.key = KeyFile(tmp / "key.json")
        self.ctx.griller = w.reg
        self.project = projects.all()[0].id

    def __call__(self, op: str, **args: Any) -> tuple[int, Any]:
        return call_op(self.ctx, self.ctx.key.current(), op, {"project": self.project, **args})


def _api(w: World, tmp: Path) -> Api:
    api = Api(w, tmp)
    assert api("backlog.new", text="other idea", slug="other")[0] == 200  # noqa: PLR2004
    return api


def test_the_board_refuses_its_own_writes_on_the_item_during_its_turn_and_writes_the_others(
    in_project: World,  # noqa: F811
    tmp_path: Path,
) -> None:
    w, api = in_project, _api(in_project, tmp_path)
    assert api("backlog.group", items=["idea", "other"], name="g")[0] == 200  # noqa: PLR2004
    summary = (w.folder / "summary.json").read_bytes()
    request = (w.folder / "request.md").read_bytes()
    sha = backlog.sha256_of(request)
    w.reg._turn = (api.project, "idea", "now", threading.Thread())
    moving = f"a Griller turn runs on {api.project}/idea: stop it before moving the item"
    changing = f"a Griller turn runs on {api.project}/idea: stop it before changing the item"
    alone: list[tuple[str, dict[str, Any], str]] = [
        ("backlog.move", {"items": ["idea"], "to": "P1"}, moving),
        ("backlog.move", {"items": ["idea"], "to": "3-ready"}, moving),
        ("backlog.move", {"items": ["idea"], "to": "running-batch"}, moving),
        (
            "backlog.file",
            {"item": "idea", "path": "request.md", "text": "x", "base_sha256": sha},
            changing,
        ),
        ("backlog.labels", {"items": ["idea"], "add": "a-label"}, changing),
        ("backlog.group", {"items": ["idea"], "name": "h"}, changing),
    ]
    for op, args, line in alone:
        status, body = api(op, **args)
        assert (status, line in str(body["error"])) == (409, True), op
    assert (w.folder / "summary.json").read_bytes() == summary
    assert (w.folder / "request.md").read_bytes() == request
    status, body = api("backlog.ungroup", name="g")  # the group holds `other` too
    assert status == 409 and [r["ok"] for r in body["results"]] == [False, True]  # noqa: PLR2004
    # another item of the same call is written, the busy one listed as refused
    status, body = api("backlog.labels", items=["idea", "other"], add="mine")
    assert status == 409 and [r["ok"] for r in body["results"]] == [False, True]  # noqa: PLR2004
    assert [e["items"] for e in w.lines() if e["action"] == "label"] == [["other"]]
    status, body = api("backlog.move", items=["idea", "other"], to="P2")
    assert status == 409 and (w.project.repo.changes / "2-backlog/P2/other").is_dir()  # noqa: PLR2004
    assert w.folder.is_dir()  # `idea` did not move
    status, body = api("backlog.group", items=["idea", "other"], name="g2")
    assert status == 409 and [r["ok"] for r in body["results"]] == [False, True, True]  # noqa: PLR2004


def test_the_four_ops_and_the_topic_run_a_turn_through_the_published_api(
    in_project: World,  # noqa: F811
    tmp_path: Path,
) -> None:
    w, api = in_project, _api(in_project, tmp_path)
    status, got = api("griller.get", item="idea")
    assert (status, got["available"], got["conversation"], got["running"]) == (
        200,
        True,
        None,
        None,
    )
    assert api("griller.send", item="nowhere", text="hi", **{"from": "p"})[0] == 404  # noqa: PLR2004
    assert api("griller.send", item="idea", text="", **{"from": "p"})[0] == BAD_REQUEST
    assert api("griller.send", item="idea", text="hi")[0] == BAD_REQUEST  # no `from`
    status, sent = api("griller.send", item="idea", text="hello", **{"from": "page-9"})
    assert status == 202 and sent["turn"]["from"] == "page-9"  # noqa: PLR2004
    w.reg.join(WAIT_S)
    got = api("griller.get", item="idea")[1]
    assert [t["state"] for t in got["conversation"]["turns"]] == ["done"]
    first = topics.read(
        api.ctx, "griller", protocol.TOPIC_ARGS["griller"](project=api.project, item="idea"), None
    )
    assert first is not None and first[1] is not None and first[1]["conversation"]
    assert topics.read(
        api.ctx,
        "griller",
        protocol.TOPIC_ARGS["griller"](project=api.project, item="idea"),
        first[0],
    ) == (first[0], None)  # no change, no value
    assert api("griller.stop", item="idea")[1]["stopped"] is False
    assert api("griller.end", item="idea")[1]["ended"] is True
    assert api("griller.get", item="idea")[1]["conversation"] is None


def test_an_in_project_run_works_from_the_main_checkout_and_writes_under_the_changes_folder(
    in_project: World,  # noqa: F811
) -> None:
    turn = _send(in_project, "an idea")
    repo = in_project.project.repo
    assert turn.answer == f"standin cwd={repo.session_root}"
    assert repo.session_root == repo.root and repo.changes == repo.root / ".agents" / "changes"
    assert (repo.root / ".agents/changes/1-inbox/idea/02-answers.md").is_file()
    chat = in_project.reg._chats[(in_project.project.id, "idea")]
    assert in_project.reg.running() is None and chat.proc is None

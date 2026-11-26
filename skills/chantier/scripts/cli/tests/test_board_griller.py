"""The board's Griller engine (`board/griller.py`), called directly: the refusals in-process, the
command line it builds (never run), and six child runs of `griller_standin.py` through the
`command()` seam. A planning surface's layout for the first three runs, the in-project one for the
others. The API and the board's write guard are not here."""

from __future__ import annotations

import json
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Any, NamedTuple

import pytest
from conftest import PLUGIN_ROOT, SKILL, Surface, live_writer

from chantier.board import griller
from chantier.board import griller_host as gh
from chantier.board.projects import Project, project_name
from chantier.commands.permissions import rule_matches
from chantier.core.repo import Repo
from chantier.host_rows import load_rows
from chantier.hub import journal
from chantier.hub import state as hub_state

REAL_COMMAND = griller.command
STANDIN = Path(__file__).with_name("griller_standin.py")
ROLE_YAML = "hosts:\n  claude:\n    roles:\n      board-griller:\n"
WAIT_S = 20.0
BAD_REQUEST = 400
SHAPES = 8  # four commands, in Bash and in PowerShell
TWO = 2  # the stand-in's pid and its child's


def _alive(pid: int) -> bool:
    import psutil

    return psutil.pid_exists(pid)


class World(NamedTuple):
    project: Project
    reg: griller.Registry
    folder: Path  # the CR's folder, the inbox item `idea`
    tmp: Path  # the stand-in's files, outside the planning folder

    def prompts(self) -> list[str]:
        lines = (self.tmp / "log.jsonl").read_text(encoding="utf-8").splitlines()
        return [json.loads(ln)["prompt"] for ln in lines]

    def lines(self) -> list[dict[str, Any]]:
        repo = self.project.repo
        return [e for e in journal.read(repo.store, repo.changes)[0] if e["type"] == "board@1"]


def _world(tmp: Path, monkeypatch: pytest.MonkeyPatch, repo: Repo) -> World:
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    project = Project(project_name(repo), repo)
    folder = repo.changes / "1-inbox" / "idea"
    folder.mkdir(parents=True)
    (folder / "request.md").write_text("an idea\n", encoding="utf-8")

    def command(run: gh.Run) -> list[str]:
        mine = [str(STANDIN), "--folder", str(run.folder), "--session", run.session]
        for flag, name in (("--log", "log.jsonl"), ("--pids", "pids"), ("--confirm", "confirm")):
            mine += [flag, str(tmp / name)]
        return [sys.executable, *mine]

    monkeypatch.setattr(griller, "command", command)
    monkeypatch.setattr(griller, "MOVE_CHECK_S", 0.4)
    return World(project, griller.Registry(), folder, tmp)


def _send(w: World, text: str, sender: str = "page-1") -> griller.Turn:
    turn = w.reg.send(w.project, "idea", text, sender)
    w.reg.join(WAIT_S)
    return turn


def _turns(w: World) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = w.reg.get(w.project, "idea")["conversation"]["turns"]
    return turns


@pytest.fixture
def in_project(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    return _world(tmp_path, monkeypatch, Repo.find(readonly=True))


@pytest.fixture
def on_surface(surface: Surface, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    return _world(tmp_path, monkeypatch, Repo.find(readonly=True))


# --- in-process: what the engine offers and refuses, and the command line (no child) -----------


@pytest.mark.parametrize(
    ("host", "yaml", "outcome"),
    [
        ("claude", "", (None, "claude-opus-5-5")),
        ("claude", "model: claude-sonnet-5-5\n", (None, "claude-sonnet-5-5")),
        (
            "claude",
            "agent: my-own\n",
            ('remove "agent" for board-griller under hosts.claude.roles', None),
        ),
        ("copilot", "", (griller.NOT_PROVED_COPILOT, None)),
        (None, "", (griller.NO_HOST, None)),
    ],
)
def test_the_action_is_offered_with_the_roles_model_or_refused_with_one_line(
    in_project: World,
    monkeypatch: pytest.MonkeyPatch,
    host: str | None,
    yaml: str,
    outcome: tuple[str | None, str | None],
) -> None:
    reason, model = outcome
    repo = in_project.project.repo
    if yaml:
        body = "".join(f"        {ln}\n" for ln in yaml.splitlines())
        (repo.root / "chantier.yaml").write_text(ROLE_YAML + body, encoding="utf-8")
    if host is None:
        monkeypatch.delenv("CHANTIER_HOST")
    else:
        monkeypatch.setenv("CHANTIER_HOST", host)
    got = griller.availability(in_project.project)
    assert got["model"] == model and got["available"] is (reason is None)
    assert (reason is None and got["reason"] is None) or str(reason) in str(got["reason"])
    if host == "claude" and reason:
        assert "(repository)" in got["reason"]  # the layer `config_view` reports


def _refused(w: World, item: str, text: str = "hello", sender: str = "p") -> griller.Refused:
    with pytest.raises(griller.Refused) as e:
        w.reg.send(w.project, item, text, sender)
    return e.value


def _put(w: World, stage: str, name: str) -> None:
    folder = w.project.repo.changes / stage / name
    folder.mkdir(parents=True)
    (folder / "summary.json").write_text("{}", encoding="utf-8")


@pytest.mark.parametrize(
    ("stage", "name", "status", "line"),
    [
        ("4-batch/2-actives", "7-batched", 409, "batched is in 4-batch/2-actives"),
        ("5-archives/batch-1", "9-archived", 409, "archived is in 5-archives/batch-1"),
        ("6-trash", "trashed", 409, "trashed is in 6-trash"),
        ("", "", 404, "no item 'nowhere' in project"),
    ],
)
def test_an_item_outside_the_backlog_is_refused_with_its_stage(
    in_project: World, stage: str, name: str, status: int, line: str
) -> None:
    item = name.split("-", 1)[-1] or "nowhere"
    if stage:
        _put(in_project, stage, name)
    refused = _refused(in_project, item)
    assert (refused.status, line in refused.text) == (status, True)
    assert not (in_project.tmp / "log.jsonl").exists()  # nothing started


def test_the_other_refusals_come_in_their_order(
    on_surface: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    w, repo = on_surface, on_surface.project.repo
    monkeypatch.setenv("CHANTIER_HOST", "copilot")
    assert griller.NOT_PROVED_COPILOT in _refused(w, "idea", "").text  # the host before the text
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    hub_state.modify(repo.git_dir, lambda data: data.pop(hub_state.WRITER, None))
    assert "writer: " in _refused(w, "idea").text  # a surface's writer not running
    live_writer(repo.git_dir)
    w.reg._turn = ("other", "thing", "now", threading.Thread())  # one runs, on another item
    busy = _refused(w, "idea")
    assert (busy.status, busy.text) == (
        409,
        "a Griller turn runs on other/thing: wait for it or stop it",
    )
    w.reg._turn = None
    for text, sender in (("", "p"), ("  ", "p"), ("x" * 8001, "p"), ("ok", "p" * 65)):
        assert _refused(w, "idea", text, sender).status == BAD_REQUEST


def test_claude_code_with_its_limits_not_proved_is_refused_and_a_second_send_is_too(
    in_project: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    w = in_project
    monkeypatch.delitem(gh.HEADLESS, "claude")
    refused = _refused(w, "idea")
    assert (refused.status, refused.text) == (409, griller.NOT_PROVED)
    monkeypatch.undo()
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    w.reg._turn = ("demo", "idea", "now", threading.Thread())  # a turn started a moment ago
    start = griller._Start(w.project, "idea", w.folder, griller.availability(w.project), "x", "p")
    with pytest.raises(griller.Refused, match="a Griller turn runs on demo/idea"):
        w.reg._start(start)  # the check is the start's own, under the one lock
    assert w.reg._chats == {}


def _run_of(w: World) -> gh.Run:
    avail = griller.availability(w.project)
    start = griller._Start(w.project, "idea", w.folder, avail, "hello", "p")
    return griller._run_of(start, "the-id", True)


@pytest.mark.parametrize("model", ["", "claude-sonnet-5-5"])
def test_the_command_line_holds_the_four_shapes_the_model_and_a_clean_environment(
    in_project: World, model: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    if model:
        (in_project.project.repo.root / "chantier.yaml").write_text(
            f"{ROLE_YAML}        model: {model}\n", encoding="utf-8"
        )
    run = _run_of(in_project)
    argv = gh._claude(run, "claude")
    assert argv[argv.index("--model") + 1] == (model or "claude-opus-5-5")
    assert argv[argv.index("--agent") + 1] == "chantier:board-griller"
    assert "--session-id" in argv and "--resume" not in argv
    assert argv[argv.index("--plugin-dir") + 1] == str(run.plugin_root) == str(PLUGIN_ROOT)
    rules = gh.allow_list(run)
    cli, cr = run.cli_command, run.folder.as_posix()
    shapes = [r for r in rules if r.startswith(("Bash(", "PowerShell("))]
    assert len(shapes) == SHAPES and all(cli in r for r in shapes)
    assert [r for r in rules if r.startswith(("Write(", "Edit("))] == [
        f"Write(//{cr.lstrip('/')}/**)",
        f"Edit(//{cr.lstrip('/')}/**)",
    ]
    reads = {r.split("//", 1)[1] for r in rules if r.startswith("Read(")}
    assert any(str(SKILL).replace("\\", "/").lstrip("/") in r for r in reads)
    root = str(run.cwd.resolve().as_posix()).lstrip("/")
    for tool in ("Read", "Grep", "Glob"):  # the working folder and the skill, for each reader
        mine = [r for r in rules if r.startswith(f"{tool}(")]
        assert len(mine) == len(run.readable) and any(root in r for r in mine)
    assert not any(
        str(run.plugin_root.resolve().as_posix()).lstrip("/") + "/**" in r for r in rules
    )

    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    monkeypatch.setenv("CHANTIER_BATCH", "batch-9")
    env = griller.environment(run)
    assert (
        not {k for k in env if k.upper() in griller.CLEARED_ENV}
        and env["CHANTIER_HOST"] == "claude"
    )


def test_the_allow_list_matches_the_four_commands_and_no_other(in_project: World) -> None:
    run = _run_of(in_project)
    rules = gh.allow_list(run)
    cli, cr = run.cli_command, run.folder.as_posix()

    def allowed(tool: str, command: str) -> bool:
        return any(rule_matches(r, tool, command) for r in rules)

    for tool in ("Bash", "PowerShell"):
        assert allowed(tool, f"{cli} rules") and allowed(tool, f"{cli} access --x")
        assert allowed(tool, f"{cli} summary lint {cr}")
        assert allowed(tool, f'{cli} summary set {cr} --title "t" --summary "s"')
        for bad in (
            f"{cli} gate {cr} x",
            f"{cli} lease hold",
            f"{cli} triage {cr} P1",
            "git status",
            "curl https://example.com",
            f"{cli} summary set {cr}-x --title t",
            f"{cli} summary lint {cr}-x",
            f"{cli} summary set {cr}/../sibling --title t",
            f"{cli} summary set {cr} --project other",
            f"{cli} summary set {cr}/x --title t",
        ):
            assert not allowed(tool, bad), bad


@pytest.mark.parametrize(
    ("resumable", "saved", "first"),
    [(True, False, False), (False, True, False), (False, False, True)],
)
def test_a_cut_first_run_is_resumed_only_when_the_host_saved_its_conversation(
    resumable: bool, saved: bool, first: bool
) -> None:
    chat = griller.Conversation(resumable=resumable, turns=[griller.Turn(1, "p", "hi")])
    assert griller._first(chat, saved) is first
    assert griller._first(griller.Conversation(), saved) is True


def test_a_result_with_no_json_is_a_failed_turn_with_the_last_lines() -> None:
    answer, error = gh.result(b"", b"warming up\nboom: no sign-in\n", 1)
    assert answer is None and error == "warming up\nboom: no sign-in"
    assert gh.result(b'{"result": "hi", "is_error": false}', b"", 0) == ("hi", None)
    assert gh.result(b'{"result": "bad key", "is_error": true}', b"", 1) == (None, "bad key")


def test_the_refusal_words_are_those_of_the_host_reference() -> None:
    row = next(r for r in load_rows("copilot") if r.capability == "board-griller")
    assert griller.NOT_PROVED_COPILOT.partition(": ")[2] in " ".join(row.means)
    assert "grill" in journal.WAKING_ACTIONS  # the journal line wakes the watcher


# --- the child runs -------------------------------------------------------------------------


def test_two_turns_resume_one_conversation_and_wake_the_watcher_once_each(
    on_surface: World,
) -> None:
    w = on_surface
    first = _send(w, "my idea is X")
    assert first.state == "done" and first.answer is not None
    assert first.answer.startswith(
        f"standin cwd={w.project.repo.session_root}"
    )  # the surface's checkout
    assert first.wrote == ["02-answers.md"] and (w.folder / "02-answers.md").is_file()
    second = _send(w, "yes [grilled]", sender="page-2")
    assert second.sender == "page-2" and second.grilled == "next batch"
    one, two = w.prompts()
    assert one.startswith("chantier board-griller for the board, in the project ")
    assert "The CR's folder: " in one and one.endswith("\nmy idea is X")
    assert two == "yes [grilled]"  # the typed text alone, unchanged
    sessions = {json.loads(ln)["session"] for ln in (w.tmp / "log.jsonl").read_text().splitlines()}
    assert len(sessions) == 1  # one conversation id
    lines = w.lines()
    assert [(e["action"], e["wakes"], e["items"]) for e in lines] == [("grill", True, ["idea"])] * 2
    assert "grilled enough, destination next batch, already recorded" in lines[1]["text"]
    assert "cut" not in lines[0]["text"]
    assert not (w.project.repo.changes / "board-journal.jsonl").exists()
    w.reg.end("demo", "idea")
    assert w.reg.get(w.project, "idea")["conversation"] is None


def test_a_failing_run_is_failed_with_its_own_words_and_writes_no_line(in_project: World) -> None:
    turn = _send(in_project, "[fail]")
    assert (turn.state, turn.error) == ("failed", "standin: the host said boom")
    assert turn.wrote == [] and in_project.lines() == []


@pytest.mark.parametrize("how", ["stop", "limit"])
def test_a_stop_and_the_time_limit_end_the_tree_and_keep_what_was_written(
    in_project: World, monkeypatch: pytest.MonkeyPatch, how: str
) -> None:
    w = in_project
    if how == "limit":
        monkeypatch.setattr(griller, "TURN_LIMIT_S", 1.5)
    w.reg.send(w.project, "idea", "write then [child]", "p")
    deadline = time.monotonic() + WAIT_S
    while not (w.tmp / "pids").is_file() and time.monotonic() < deadline:
        time.sleep(0.05)
    pids = [int(p) for p in (w.tmp / "pids").read_text().split()]
    assert len(pids) == TWO and all(map(_alive, pids))
    assert w.reg.busy(w.project.id, "idea") and w.reg.running()["item"] == "idea"  # type: ignore[index]
    with pytest.raises(griller.Refused, match="stop the turn first"):
        w.reg.end(w.project.id, "idea")
    if how == "stop":
        assert w.reg.stop(w.project.id, "idea") is True
    w.reg.join(WAIT_S)
    assert w.reg.stop(w.project.id, "idea") is False  # none runs now
    turn = _turns(w)[0]
    assert turn["state"] == ("stopped" if how == "stop" else "timed-out")
    assert turn["wrote"] == ["02-answers.md"]
    assert not any(map(_alive, pids))
    (line,) = w.lines()
    assert line["text"].endswith("; cut") and "02-answers.md" in line["text"]


def test_a_folder_moved_by_another_session_ends_the_turn_and_leaves_no_stray_folder(
    in_project: World,
) -> None:
    w = in_project
    w.reg.send(w.project, "idea", "[move]", "p")
    w.reg.join(WAIT_S)
    turn = _turns(w)[0]
    assert (w.tmp / "confirm").is_file()  # the old path was made again before the cleanup
    assert turn["state"] == "failed" and "idea is now in 2-backlog/P1" in turn["error"]
    assert not w.folder.exists()  # no stray folder at the old path
    assert (w.project.repo.changes / "2-backlog" / "P1" / "idea" / "request.md").is_file()
    assert "stray.md" not in turn["wrote"]  # `wrote` is listed at the new path
    assert turn["wrote"] == ["02-answers.md"]
    (line,) = w.lines()
    assert line["text"].endswith("; cut") and line["wakes"] is True


def test_a_missing_cli_is_the_turns_error(
    in_project: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(griller, "command", REAL_COMMAND)  # the real one, and no `claude`
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    turn = _send(in_project, "hi")
    assert (turn.state, turn.error) == ("failed", "claude: not found on this machine")

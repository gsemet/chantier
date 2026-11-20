"""The board's Configuration routes, called in-process on a prepared state: the writes, the
refusals and the read-only case."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from api_client import call_route
from conftest import Surface

from chantier.board import config_api
from chantier.board import key as keys
from chantier.board.context import Context
from chantier.board.projects import Projects
from chantier.board.seats import Seats
from chantier.core.repo import Repo
from chantier.hub import journal as forge_journal
from chantier.playbook import models

OK, BAD, CONFLICT = 200, 400, 409
MINE = "projects/demo/.repo/chantier.yaml"
TERRA = "gpt-6.1-terra"
TOWARDS = "hosts:\n  copilot:\n    roles:\n      coder:\n        model: gpt-6.1-sol\n"
MINE_FILE = "# mine\nboard:\n  port: 8123 # kept\n"
BOTH = {"project": "board:\n  port: 1\n", "yml": "board:\n  port: 2\n"}
RESETS = (
    "hosts:\n  copilot:\n    roles:\n      coder:\n        model: default\n"
    "      inspector:\n        model: ~\n"
)


def _board(repo_: Repo, monkeypatch: pytest.MonkeyPatch) -> Callable[..., tuple[int, Any]]:
    """The board's ops called in-process on one project, with the key a page sends."""
    projects = Projects(repo_, repo_.surface, [])
    secret = keys.load_or_create(repo_)
    ctx = Context(
        projects, keys.KeyFile(keys.key_path(repo_)), Seats(projects), "t", lambda: None, None
    )

    def call(method: str, body: object = None) -> tuple[int, Any]:
        return call_route(ctx, secret, method, projects.home_id, "config", body)

    return call


def _on_surface(monkeypatch: pytest.MonkeyPatch) -> Callable[..., Any]:
    return _board(Repo.find(project="demo", readonly=True), monkeypatch)


def _change(role: str, key: str, value: str | None, host: str | None = "copilot") -> dict[str, Any]:
    return {"host": host, "role": role, "key": key, "value": value}


def _row(view: dict[str, Any], host: str, role: str) -> dict[str, Any]:
    return next(r for r in view["hosts"][host]["roles"] if r["role"] == role)


def _put_file(folder: Path, text: str, name: str = "chantier.yaml") -> None:
    (folder / name).write_text(text, encoding="utf-8", newline="\n")


CASES = [
    ("write", {"project": MINE_FILE}, [("coder", "model", TERRA)], OK),
    ("unknown model", {}, [("coder", "model", "gpt-nope")], CONFLICT),
    ("other key", {}, [("coder", "skills", "x")], BAD),
    ("no host", {}, [("coder", "model", TERRA, None)], BAD),
    ("default", {}, [("coder", "model", "default")], CONFLICT),
    ("both files", BOTH, [("coder", "model", TERRA)], CONFLICT),
    ("refused start", {}, [("coder", "agent", "mine"), ("coder", "model", TERRA)], OK),
    ("overridden", {"repo": TOWARDS}, [("coder", "model", TERRA)], OK),
]  # fmt: skip


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_the_configuration_is_written_or_refused_through_the_cli(
    surface: Surface, monkeypatch: pytest.MonkeyPatch, case: tuple[Any, ...]
) -> None:
    name, files, changes, status = case
    for where, text in files.items():
        folder = surface.clone if where == "repo" else surface.project
        _put_file(folder, text, "chantier.yml" if where == "yml" else "chantier.yaml")
    call = _on_surface(monkeypatch)
    before = call("GET")[1]
    body = {"changes": [_change(*c) for c in changes], "base_sha256": before["sha256"]}
    code, answer = call("PUT", {**body, "dry_run": False})
    path = surface.project / "chantier.yaml"
    written = path.read_bytes() if path.is_file() else None
    assert code == status, (name, answer)
    if status != OK:
        assert answer["ok"] is False and answer["error"]
        assert written == (files.get("project", "").encode() or None)
        return
    assert written is not None
    assert answer["sha256"] == hashlib.sha256(written).hexdigest()
    assert answer["lines"][-1] == "applies at the next batch" and len(answer["journal"]) == 1
    row = _row(answer["view"], "copilot", "coder")
    if name == "write":
        assert b"# mine" in written and b"# kept" in written and TERRA.encode() in written
        assert answer["journal"][0]["text"] == f"coder.model = {TERRA} (copilot)"
        assert row["start"] == "generic" and row["overridden_by"] is None
    elif name == "refused start":
        assert row["start"] == "refused" and "cannot start a named agent" in row["refusal"]
    else:  # the repository's file wins, and the surface's file is written all the same
        assert TERRA.encode() in written
        assert row["overridden_by"] == MINE and row["model"]["effective"]["id"] == "gpt-6.1-sol"
        assert answer["journal"][0]["text"].endswith(f", overridden by {MINE}")


ROLE = "hosts.copilot.roles.coder."
SAVES = [
    ("agent", ROLE + "agent", ["mine", "plugin"]),
    ("model", ROLE + "model", [TERRA, "gpt-6.1-sol"]),
    ("slots", "batch.slots", [7, 8]),
    ("parallel", "specifying.parallel", [3, 4]),
]  # fmt: skip


@pytest.mark.parametrize(("name", "key", "values"), SAVES, ids=[c[0] for c in SAVES])
def test_a_save_writes_one_config_line_per_changed_key_and_a_dry_run_none(
    surface: Surface, monkeypatch: pytest.MonkeyPatch, name: str, key: str, values: list[Any]
) -> None:
    call = _on_surface(monkeypatch)
    found = Repo.find(project="demo", readonly=True)

    def lines() -> list[dict[str, Any]]:
        return [e for e in forge_journal.read(found.changes)[0] if e["type"] == "config@1"]

    def change(value: Any) -> dict[str, Any]:
        if name in ("slots", "parallel"):
            return {"key": key, "value": value}
        return _change("coder", name, value)

    def save(value: Any, dry: bool = False) -> None:
        sha = call("GET")[1]["sha256"]
        code, answer = call("PUT", {"changes": [change(value)], "base_sha256": sha, "dry_run": dry})
        assert code == OK, answer

    save(values[0], dry=True)
    assert lines() == []
    save(values[0])
    (one,) = lines()
    assert (one["source"], one["type"], one["key"], one["batch"]) == (
        "board",
        "config@1",
        key,
        None,
    )
    assert one["new"] is not None and one["old"] != one["new"]
    save(values[0])  # the effective value is where it was: no line
    assert len(lines()) == 1
    save(values[1])
    second = lines()[1]
    assert (second["key"], second["old"]) == (key, one["new"]) and second["new"] != one["new"]


def test_a_dry_run_and_a_stale_hash_write_nothing_and_the_view_shows_resets_and_plans(
    surface: Surface, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _put_file(surface.project, TOWARDS.replace("sol", "terra"))
    _put_file(surface.clone, RESETS)
    plans = {"pro": True, "pro_plus": True, "max": False, "business": True, "enterprise": True}
    ids = [m.id for m in models.MODELS["copilot"][:2]]
    small = [{"id": ids[0], "plans": plans}, {"id": ids[1], "plans": None}]
    monkeypatch.setattr(models, "copilot_catalog", lambda: small)
    call = _on_surface(monkeypatch)
    _, view = call("GET")
    assert _row(view, "copilot", "coder")["model"]["layers"]["repository"] == "reset"
    assert _row(view, "copilot", "inspector")["model"]["layers"]["repository"] == "reset"
    assert _row(view, "copilot", "coder")["overridden_by"] == MINE
    by_id = {m["id"]: m for m in view["hosts"]["copilot"]["catalog"]}
    assert (by_id[ids[0]]["plans"], by_id[ids[1]]["plans"]) == (plans, None)
    assert all("plans" not in m for m in view["hosts"]["claude"]["catalog"])
    coder = (
        "Implements one round of one chantier CR in its worktree; never commits. "
        "Started by a Driver."
    )
    for host in ("claude", "copilot"):
        shown = [r["description"] for r in view["hosts"][host]["roles"]]
        assert all(shown) and not any("Prompt starts with" in d for d in shown)
        assert _row(view, host, "coder")["description"] == coder
    # an agent file with no description: its row shows null and the view still answers 200
    plugin = tmp_path / "plugin"
    (plugin / "agents").mkdir(parents=True)
    (plugin / "agents" / "coder.md").write_text("---\nname: coder\n---\nbody\n", encoding="utf-8")
    monkeypatch.setenv("CHANTIER_PLUGIN_ROOT", str(plugin))
    code, bare = call("GET")
    assert code == OK and _row(bare, "claude", "coder")["description"] is None
    monkeypatch.delenv("CHANTIER_PLUGIN_ROOT")
    path = surface.project / "chantier.yaml"
    before = path.read_bytes()
    body = {"changes": [_change("coder", "model", None)], "base_sha256": view["sha256"]}
    code, answer = call("PUT", {**body, "dry_run": True})
    assert code == OK and answer["dry_run"] and answer["journal"] == []
    assert path.read_bytes() == before
    code, answer = call("PUT", {**body, "base_sha256": "0" * 64, "dry_run": False})
    assert code == CONFLICT and "changed since" in answer["error"] and answer["stale"] is True
    assert path.read_bytes() == before
    bad = {"changes": [_change("coder", "model", "no-such-model")], "base_sha256": view["sha256"]}
    code, answer = call("PUT", {**bad, "dry_run": True})
    assert code == CONFLICT and "stale" not in answer


def test_with_no_planning_surface_the_configuration_is_read_only(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    call = _board(Repo.find(readonly=True), monkeypatch)
    code, view = call("GET")
    assert code == OK and view["writable"] is False and view["sha256"] is None
    code, answer = call("PUT", {"changes": [_change("coder", "model", TERRA)], "base_sha256": None})
    assert code == CONFLICT and "read-only" in answer["error"]


def test_a_config_event_its_model_refuses_leaves_the_save_and_names_the_skipped_line(
    surface: Surface, monkeypatch: pytest.MonkeyPatch
) -> None:
    # a prepared refusal: an event builder patched to add a field its model does not hold
    build = config_api._event
    monkeypatch.setattr(config_api, "_event", lambda *a: {**build(*a), "unexpected": 1})
    call = _on_surface(monkeypatch)
    found = Repo.find(project="demo", readonly=True)
    sha = call("GET")[1]["sha256"]
    change = {"key": "batch.slots", "value": 7}
    code, answer = call("PUT", {"changes": [change], "base_sha256": sha})
    assert code == OK and answer["ok"] is True
    assert answer["error"].startswith("skipped: journal payload config@1:")
    assert answer["sha256"] != sha and answer["journal"]
    assert [e for e in forge_journal.read(found.changes)[0] if e["type"] == "config@1"] == []

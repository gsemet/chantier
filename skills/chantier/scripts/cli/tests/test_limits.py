"""The two limits `specifying.parallel` and `batch.slots`: their checks, the layers, `open`, the
playbook's `limits:` line, the board's save with its forge-journal line, and `status`."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import FROM_AGENTS_MD, changes, host
from conftest import PLUGIN_ROOT, Chantier, Surface
from test_board_config import CONFLICT, MINE, OK, TERRA, _board, _change, _on_surface, _put_file

from chantier.core import clock
from chantier.core import repo as repo_module
from chantier.core.errors import EXIT_PRECONDITION
from chantier.core.repo import Repo
from chantier.hub import journal
from chantier.playbook import config, limits

FOUND_MIN = 6
DEFAULTS = PLUGIN_ROOT / "config" / "chantier.defaults.yml"
SECTION = {"batch.slots": "batch", "specifying.parallel": "specifying"}
SPECIFYING_BAD = 'specifying: "parallel" is a whole number, 1 or more, found "{}"'
BATCH_BAD = 'batch: "slots" is a whole number, 0 or more, found "{}"'


def _problems(text: str) -> list[str]:
    tree, problems = config.parse_text(text, "chantier.yaml")
    assert tree is not None, problems
    found: list[str] = []
    config.check(tree, {}, lambda line, msg: found.append(f"chantier.yaml:{line}: {msg}"))
    return found


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("specifying:\n  parallel: 2\nbatch:\n  slots: 0\n", None),
        ("specifying:\n  parallel: default\nbatch:\n  slots: ~\n", None),
        ("specifying:\n  parallel: 0\n", SPECIFYING_BAD.format("0")),
        ("specifying:\n  parallel: two\n", SPECIFYING_BAD.format("two")),
        ("batch:\n  slots: -1\n", BATCH_BAD.format("-1")),
        ("batch:\n  slots: 2.5\n", BATCH_BAD.format("2.5")),
    ],
)
def test_the_two_limits_are_checked_like_long_gate(text: str, expected: str | None) -> None:
    problems = _problems(text)
    if expected is None:
        assert problems == []
    else:
        assert any(expected in p for p in problems), problems


def _shipped(key: str) -> int:
    """The value the shipped defaults file gives, read at the head under test."""
    tree, problems = config.parse_text(DEFAULTS.read_text("utf-8"), str(DEFAULTS))
    value = limits.held(tree, key)
    assert isinstance(value, int), problems
    return value


SLOTS, PARALLEL = _shipped("batch.slots"), _shipped("specifying.parallel")


def _lay(surface: Surface, layer: str, text: str) -> None:
    folder = surface.clone if layer == "repository" else surface.project
    _put_file(folder, text)


def _cli(chantier: Chantier, *args: object) -> tuple[int, list[str], str]:
    return chantier("--project", "demo", *args)


def _limits_line(chantier: Chantier) -> str:
    _, out, _ = _cli(chantier, "playbook")
    return next(x for x in out if x.startswith("limits:"))


def _as_chief(monkeypatch: pytest.MonkeyPatch) -> None:
    host(monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "uuid-chief")


def _open(chantier: Chantier, *args: object) -> tuple[int, list[str], str]:
    return _cli(chantier, "open", *FROM_AGENTS_MD, "--mode", "stack", *args)


def test_the_playbook_line_names_the_layer_the_markers_and_the_limit(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    _, out, _ = chantier("playbook")
    first = f"limits: specifying {PARALLEL}, markers 0; batch slots {SLOTS}"
    assert first in out
    (repo / "chantier.yaml").write_text(
        "specifying:\n  parallel: 1\nbatch:\n  slots: 6\n", encoding="utf-8"
    )
    folder = changes(repo) / "1-inbox" / "a-cr"
    (folder / "work" / "specifying").mkdir(parents=True)
    line = next(x for x in chantier("playbook")[1] if x.startswith("limits:"))
    assert line.startswith("limits: specifying 1 [repository], markers 1 (a-cr); batch slots 6")
    assert line.endswith("; specifying at the limit")


def _lacking(tmp_path: Path, key: str = "batch.slots") -> Path:
    """A plugin copy whose shipped defaults lack one limit (a case the shipped file cannot
    hold)."""
    plugin = tmp_path / "plugin"
    (plugin / "config").mkdir(parents=True)
    for folder in ("agents", "com.github.copilot"):
        shutil.copytree(PLUGIN_ROOT / folder, plugin / folder)
    section, sub = key.split(".")
    lines = DEFAULTS.read_text("utf-8").splitlines(keepends=True)
    gone = (f"{section}:", f"  {sub}:")
    kept = [x for x in lines if not x.startswith(gone)]
    assert len(kept) == len(lines) - 2
    (plugin / "config" / DEFAULTS.name).write_text("".join(kept), encoding="utf-8")
    return plugin


NO_VALUE = "no batch.slots: no plugin defaults file and no chantier.yaml sets it; give --slots"
MATRIX = [
    # (id, user layers, plugin, open args) -> (playbook line, open refusal or (slots, label))
    ("shipped", {}, "plugin", (),
     f"batch slots {SLOTS}", (SLOTS, "")),
    ("surface project", {"surface project": "batch:\n  slots: 6\n"}, "plugin", (),
     "batch slots 6 [surface project]", (6, " [surface project]")),
    ("repository", {"repository": "batch:\n  slots: 7\n"}, "plugin", (),
     "batch slots 7 [repository]", (7, " [repository]")),
    ("--slots wins", {"surface project": "batch:\n  slots: 6\n"}, "plugin", ("--slots", 3),
     "batch slots 6 [surface project]", (3, "")),
    ("zero", {"surface project": "batch:\n  slots: 0\n"}, "plugin", (),
     "batch slots 0 [surface project]", "batch.slots is 0 in"),
    ("zero, repository", {"repository": "batch:\n  slots: 0\n"}, "plugin", (),
     "batch slots 0 [repository]", "batch.slots is 0 in"),
    ("no plugin", {}, "none", (),
     "specifying parallel: not set, markers 0; batch slots: not set", NO_VALUE),
    ("lacking key", {}, "lacking", (),
     'the shipped defaults lack "batch.slots"', 'the shipped defaults lack "batch.slots"'),
    ("lacking parallel", {}, "lacking-parallel", (),
     'the shipped defaults lack "specifying.parallel"',
     'the shipped defaults lack "specifying.parallel"'),
]  # fmt: skip


@pytest.mark.parametrize("case", MATRIX, ids=[c[0] for c in MATRIX])
def test_open_and_the_playbook_take_the_limits_from_the_layers(
    surface: Surface,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    case: tuple[Any, ...],
) -> None:
    _, files, plugin, args, shown, expected = case
    _as_chief(monkeypatch)
    for layer, text in files.items():
        _lay(surface, layer, text)
    if plugin == "none":
        monkeypatch.setenv("CHANTIER_PLUGIN_ROOT", "")
    elif plugin.startswith("lacking"):
        key = "specifying.parallel" if plugin.endswith("parallel") else "batch.slots"
        monkeypatch.setenv("CHANTIER_PLUGIN_ROOT", str(_lacking(tmp_path, key)))
    code, out, err = _cli(chantier, "playbook")
    text = "\n".join([*out, err])
    if plugin.startswith("lacking"):
        assert code == EXIT_PRECONDITION and shown in text
    else:
        assert code == 0 and shown in next(x for x in out if x.startswith("limits:"))
    code, out, err = _open(chantier, *args)
    if isinstance(expected, str):
        assert code == EXIT_PRECONDITION and expected in err and not record_exists(surface)
        return
    slots, label = expected
    assert code == 0, err
    assert f", {slots} slots{label}, stack" in out[0]
    assert json.loads(_record(surface).read_text("utf-8"))["slots"] == slots


def _record(surface: Surface) -> Path:
    return surface.project / "changes" / "4-batch" / "batch.json"


def record_exists(surface: Surface) -> bool:
    return _record(surface).is_file()


def _put(
    call: Callable[..., tuple[int, Any]],
    changes_: list[dict[str, Any]],
    sha: str | None = None,
    dry: bool = False,
) -> tuple[int, Any]:
    base = sha or call("GET")[1]["sha256"]
    return call("PUT", {"changes": changes_, "base_sha256": base, "dry_run": dry})


def _forge(surface: Surface) -> list[dict[str, Any]]:
    path = surface.project / "changes" / "forge-journal.jsonl"
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text("utf-8").splitlines()]


def _limit(key: str, value: object) -> dict[str, Any]:
    return {"key": key, "value": value}


PUTS = [
    ("batch.slots", "slots 5 -> 6: from the next open"),
    ("specifying.parallel", "specifying 5 -> 6: from the next start"),
]


@pytest.mark.parametrize(("key", "line"), PUTS, ids=[k for k, _ in PUTS])
def test_the_board_saves_a_limit_keeps_comments_journals_one_line_and_removes_it(
    surface: Surface, monkeypatch: pytest.MonkeyPatch, key: str, line: str
) -> None:
    section, sub = key.split(".")
    _put_file(surface.project, f"# mine\nboard:\n  port: 8123\n{section}:\n  {sub}: 5 # kept\n")
    call = _on_surface(monkeypatch)
    view = call("GET")[1]["limits"][key]
    assert (view["effective"], view["layer"], view["overridden_by"]) == (5, "surface project", None)
    code, answer = _put(call, [_limit(key, FOUND_MIN)])
    assert code == OK, answer
    text = (surface.project / "chantier.yaml").read_text("utf-8")
    assert "# mine" in text and "# kept" in text and f"{sub}: {FOUND_MIN}" in text
    assert answer["lines"][1] == line and "applies at the next batch" not in answer["lines"]
    (event,) = _forge(surface)
    assert {k: event[k] for k in ("type", "key", "old", "new", "source", "batch")} == {
        "type": "config@1",
        "key": key,
        "old": 5,
        "new": FOUND_MIN,
        "source": "board",
        "batch": None,
    }
    # the same value again changes nothing; inheriting removes the key and moves to the default
    code, answer = _put(call, [_limit(key, FOUND_MIN)], answer["sha256"])
    assert code == OK and len(_forge(surface)) == 1
    code, answer = _put(call, [_limit(key, None)], answer["sha256"])
    text = (surface.project / "chantier.yaml").read_text("utf-8")
    assert code == OK and sub not in text and "# mine" in text
    shipped = _shipped(key)
    assert [(e["old"], e["new"]) for e in _forge(surface)] == [(5, 6), (6, shipped)]


@pytest.mark.parametrize(
    "value", [0, -1, 2.5, "x", True], ids=["zero-parallel", "neg", "float", "str", "bool"]
)
def test_the_board_refuses_a_bad_limit_and_writes_nothing(
    surface: Surface, monkeypatch: pytest.MonkeyPatch, value: object
) -> None:
    call = _on_surface(monkeypatch)
    key = "specifying.parallel" if value == 0 else "batch.slots"
    code, answer = _put(call, [_limit(key, value)])
    assert code != OK and answer["ok"] is False
    assert not (surface.project / "chantier.yaml").exists() and _forge(surface) == []


def test_a_stale_hash_is_409_and_a_dry_run_writes_no_file_and_no_journal_line(
    surface: Surface, monkeypatch: pytest.MonkeyPatch
) -> None:
    _put_file(surface.project, "batch:\n  slots: 5\n")
    path = surface.project / "chantier.yaml"
    before = path.read_bytes()
    call = _on_surface(monkeypatch)
    code, answer = _put(call, [_limit("batch.slots", 6)], "0" * 64)
    assert code == CONFLICT and answer["stale"] is True
    code, answer = _put(call, [_limit("batch.slots", 6)], dry=True)
    assert code == OK and answer["dry_run"] is True and answer["journal"] == []
    assert path.read_bytes() == before and _forge(surface) == []


def test_a_put_of_both_limits_and_a_role_edit_writes_three_lines_and_status_follows_the_orders(
    surface: Surface, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    _as_chief(monkeypatch)
    monkeypatch.setattr(clock, "_fixed", [])
    assert _open(chantier)[0] == 0
    monkeypatch.setenv("CHANTIER_BATCH", "batch-01")
    call = _on_surface(monkeypatch)

    def told() -> list[str]:
        out = _cli(chantier, "status")[1]
        return [x for x in out if "config changed" in x or "specifying" in x]

    clock.fix("2030-01-01T00:00:00Z")
    both = [
        _limit("batch.slots", FOUND_MIN),
        _change("coder", "model", TERRA),
        _limit("specifying.parallel", 2),
    ]
    code, answer = _put(call, both)
    assert code == OK, answer
    assert [(e["key"], e["old"], e["new"], e["batch"]) for e in _forge(surface)] == [
        ("batch.slots", SLOTS, FOUND_MIN, "batch-01"),
        ("hosts.copilot.roles.coder.model", "gpt-6.1-sol", TERRA, "batch-01"),
        ("specifying.parallel", PARALLEL, 2, "batch-01"),
    ]
    assert answer["lines"][1:] == [
        f"slots {SLOTS} -> {FOUND_MIN}: batch-01 keeps {SLOTS} until an order slots",
        f"specifying {PARALLEL} -> 2: from the next start",
        "applies at the next batch",
    ]
    first = (
        f"config changed on the board: batch.slots {SLOTS} -> {FOUND_MIN}; "
        f"batch-01 keeps {SLOTS} until an order slots"
    )
    assert told() == [first]  # the specifying change is told by no status line
    # a newer line replaces the older one
    clock.fix("2030-01-01T00:00:05Z")
    assert _put(call, [_limit("batch.slots", FOUND_MIN + 1)])[0] == OK
    newer = (
        f"config changed on the board: batch.slots {FOUND_MIN} -> {FOUND_MIN + 1}; "
        f"batch-01 keeps {FOUND_MIN} until an order slots"
    )
    assert told() == [newer]
    # an order slots recorded after it ends the line
    clock.fix("2030-01-01T00:00:10Z")
    assert _cli(chantier, "order", "slots", "--note", FOUND_MIN + 1)[0] == 0
    assert told() == []


def test_the_view_says_the_repository_overrides_and_such_a_save_journals_nothing(
    surface: Surface, monkeypatch: pytest.MonkeyPatch
) -> None:
    _put_file(surface.clone, "batch:\n  slots: 7\n")
    call = _on_surface(monkeypatch)
    view = call("GET")[1]["limits"]
    assert view["batch.slots"]["overridden_by"] == MINE
    assert (view["batch.slots"]["effective"], view["batch.slots"]["layer"]) == (7, "repository")
    assert view["specifying.parallel"]["overridden_by"] is None
    code, answer = _put(call, [_limit("batch.slots", FOUND_MIN)])
    assert code == OK and "slots: 6" in (surface.project / "chantier.yaml").read_text("utf-8")
    assert answer["view"]["limits"]["batch.slots"]["effective"] == 7  # noqa: PLR2004
    assert _forge(surface) == []  # the effective value did not move


def test_with_no_planning_surface_a_limit_is_read_only_and_writes_nothing(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(repo_module, "PROJECT", None)  # an earlier `--project demo` leaves it
    call = _board(Repo.find(readonly=True), monkeypatch)
    code, view = call("GET")
    assert code == OK and view["writable"] is False and "limits" in view
    code, answer = _put(call, [_limit("batch.slots", FOUND_MIN)], None)
    assert code == CONFLICT and "read-only" in answer["error"]
    assert not (repo / "chantier.yaml").exists()
    assert not (changes(repo) / "forge-journal.jsonl").exists()


def test_config_lines_with_the_same_values_and_time_are_two_lines(
    surface: Surface, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = Repo.find(project="demo", readonly=True)
    one = {"type": "config@1", "key": "specifying.parallel", "old": 4, "new": 2, "batch": None}
    monkeypatch.setattr(clock, "_fixed", [])
    clock.fix("2030-01-01T00:00:00Z")
    journal.append(repo, [one, one], "board")
    assert len(_forge(surface)) == 2  # noqa: PLR2004 - a config line is never deduplicated

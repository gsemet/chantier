"""The long gate's refusals: its `long_gate:` key in chantier.yaml, and `--stop`'s usage."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from batch_helpers import FROM_AGENTS_MD, events, host, name_gate, open_batch, record
from conftest import PLUGIN_ROOT, Chantier, Surface, sh

from chantier.commands import orders_merged
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE
from chantier.core.repo import Repo
from chantier.playbook import config
from chantier.playbook.long_gate import load_long_gate

GATE = "tests"
WHOLE = '"parallel" is a whole number'
KEYS = [
    ("zero", "long_gate:\n  parallel: 0\n", WHOLE),
    ("a word", "long_gate:\n  parallel: two\n", WHOLE),
    ("an unknown key", "long_gate:\n  slots: 2\n", 'unknown key "slots"'),
    (
        "commands that is no map",
        "long_gate:\n  commands: just\n",
        '"commands" is a map from a name',
    ),
]
LINE = 2
PARALLEL = 3


@pytest.fixture
def gated(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Chantier, str]:
    (one,) = open_batch(repo, chantier, monkeypatch, "Gate one")
    assert chantier("take", one, "--epoch", 1)[0] == 0
    cr = record(repo)["crs"][0]  # the Driver makes the worktree
    sh("git", "worktree", "add", "-q", "-b", cr["branch"], cr["worktree"], "HEAD", cwd=repo)
    return repo, chantier, one


def test_a_bad_long_gate_key_is_refused_with_its_line_by_gate_playbook_and_preflight(
    gated: tuple[Path, Chantier, str],
) -> None:
    repo, chantier, one = gated
    yaml = repo / "chantier.yaml"
    for label, text, why in KEYS:
        yaml.write_text(text, encoding="utf-8")
        code, _, err = chantier("gate", one, GATE)
        assert code == EXIT_PRECONDITION and f"chantier.yaml:{LINE}: long_gate:" in err, (
            f"{label}: {code} {err}"
        )
        assert why in err, f"{label}: {code} {err}"
        code, out, _ = chantier("playbook")
        assert code == EXIT_PRECONDITION, label
        assert any(ln.startswith(f"chantier.yaml:{LINE}: long_gate:") for ln in out), label
        pre = chantier("preflight")[1]
        assert any(ln.startswith(f"P12 FAIL chantier.yaml:{LINE}: long_gate:") for ln in pre), label
    yaml.write_text("long_gate:\n  parallel: 2\n", encoding="utf-8")
    code, out, _ = chantier("playbook")
    assert code == 0 and out[0].startswith("playbook: chantier.yaml, valid")
    assert any(ln.startswith("P12 ok") for ln in chantier("preflight")[1])


def test_order_merged_refuses_and_records_nothing_when_the_stopped_gate_does_not_end(
    gated: tuple[Path, Chantier, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, chantier, one = gated
    before = record(repo)
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        lock = Repo.find().changes / ".long-gate.lock"
        lock.write_bytes(f"\0{one} pid {child.pid}".encode())
        monkeypatch.setattr(orders_merged, "STOP_WAIT_S", 0.3)
        code, _, err = chantier("order", "merged", one, "--epoch", 1)
        assert code == EXIT_PRECONDITION
        assert f"order merged {one}: its long gate (pid {child.pid}) did not end" in err, err
        after = record(repo)
        assert after["crs"] == before["crs"] and after["orders"] == before["orders"]
        assert after["crs"][0]["status"] != "merged"
        assert next(repo.glob(".agents/changes/**/2-actives/*"), None) is not None
    finally:
        child.kill()
        child.wait()


def test_gate_stop_takes_no_command_and_gate_needs_one_and_nothing_running_is_not_an_error(
    gated: tuple[Path, Chantier, str],
) -> None:
    _, chantier, one = gated
    assert chantier("gate", one, "--stop", GATE)[0] == EXIT_USAGE
    assert chantier("gate", one)[0] == EXIT_USAGE
    code, out, _ = chantier("gate", one, "--stop")
    assert code == 0 and any("nothing to stop" in ln for ln in out)


def assert_nothing_logged(repo: Path) -> None:
    assert not [e for e in events(repo) if e["kind"] == "gate"]
    logs = [p for d in repo.glob(".agents/changes/**/work/gates") for p in d.iterdir()]
    assert logs == []


def test_gate_runs_only_a_name_the_root_chantier_yaml_gives_and_refuses_in_order(
    gated: tuple[Path, Chantier, str],
) -> None:
    repo, chantier, one = gated
    assert chantier("gate", one)[0] == EXIT_USAGE  # usage first
    code, _, err = chantier("gate", one, "tests")  # then no entry
    assert code == EXIT_PRECONDITION and "names no long gate" in err, err
    assert chantier("gate", one, "--stop", "tests")[0] == EXIT_USAGE
    assert chantier("gate", one, "--first", "tests")[0] == EXIT_USAGE
    assert_nothing_logged(repo)  # usage and no entry: no event, no log
    name_gate(repo, "tests", f'{sys.executable} -c "print(1)"')
    code, _, err = chantier("gate", one, "pytest -q")  # a free command is no name
    assert code == EXIT_USAGE and "is not a long gate named in chantier.yaml" in err, err
    assert "named: tests" in err
    code, _, err = chantier("gate", one, "nope")  # an unknown name
    assert code == EXIT_USAGE and "named: tests" in err, err
    assert_nothing_logged(repo)
    (repo / "chantier.yaml").write_text("long_gate:\n  slots: 2\n", encoding="utf-8")
    assert chantier("gate", one, "tests")[0] == EXIT_PRECONDITION  # a bad key, before a word
    name_gate(repo, "tests", f'{sys.executable} -c "print(1)"')
    code, _, err = chantier("gate", one, "tests")
    assert code == 0, err


def test_the_root_file_of_the_code_repository_wins_over_the_worktrees_own(
    gated: tuple[Path, Chantier, str],
) -> None:
    repo, chantier, one = gated
    root = f'{sys.executable} -c "print(1)"'
    name_gate(repo, "tests", root)
    wt = Path(record(repo)["crs"][0]["worktree"])
    name_gate(wt, "tests", f'{sys.executable} -c "print(2)"')
    sh("git", "add", "chantier.yaml", cwd=wt)
    sh("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "own", cwd=wt)
    code, _, err = chantier("gate", one, "tests")
    assert code == 0, err
    (ran,) = [e for e in events(repo) if e["kind"] == "gate"]
    assert ran["command"] == root and ran["name"] == "tests"


def test_a_surface_layers_commands_are_ignored_but_its_parallel_merges(
    surface: Surface, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    (surface.project / "chantier.yaml").write_text(
        "long_gate:\n  parallel: 3\n  commands:\n    tests: echo no\n", encoding="utf-8"
    )
    found = load_long_gate(Repo.find())
    assert found.commands == {} and found.parallel == PARALLEL and found.ignored
    code, out, err = chantier("playbook")
    assert code == 0, (out, err)
    assert any(ln.startswith("long gate: long_gate.commands in") and "ignored" in ln for ln in out)
    assert any(ln.startswith("long gate: none named") for ln in out)
    (surface.project / "changes" / "1-inbox").mkdir(parents=True, exist_ok=True)
    code, out, _ = chantier("validate")  # exactly one gap: the ignored commands
    assert code == 0 and out[0] == "1 gap(s) in 0 CRs", out
    assert len(out) == LINE and "long_gate.commands ignored" in out[1], out
    code, filed, err = chantier("file", "Gate surface")
    assert code == 0, err
    folder = surface.project.parent.parent / filed[0].removeprefix("filed ").split(";")[0]
    (folder / "03-change-spec.md").write_text("# Gate surface\n\nDo it.\n", encoding="utf-8")
    code, _, err = chantier("open", str(folder), *FROM_AGENTS_MD)
    assert code == 0, err
    data = json.loads((surface.project / "changes/4-batch/batch.json").read_text("utf-8"))
    monkeypatch.setenv("CHANTIER_BATCH", data["id"])
    cr = data["crs"][0]
    sh(
        "git",
        "worktree",
        "add",
        "-q",
        "-b",
        cr["branch"],
        cr["worktree"],
        "HEAD",
        cwd=surface.clone,
    )
    code, _, err = chantier("gate", cr["id"], "tests")  # the surface's command is no entry
    assert code == EXIT_PRECONDITION and "names no long gate" in err, err


@pytest.mark.parametrize(
    ("folder", "name", "line"),
    [
        ("", "scenario", "just scenario"),
        (
            "evals/kit/sandbox",
            "tests",
            "Long gate (before a pull request): `uv run --locked pytest -q`",
        ),
        ("evals/kit/fixture", "tests", "Long gate (before a pull request): `uv run pytest -q`"),
    ],
)
def test_the_repository_and_the_eval_kit_ship_the_long_gate_names_their_rules_use(
    folder: str, name: str, line: str
) -> None:
    root = PLUGIN_ROOT / folder
    tree, problems = config.read_tree(root / "chantier.yaml", "chantier.yaml")
    assert tree is not None and not problems, problems
    commands = config.gate_commands(tree.value["long_gate"][1])
    assert name in commands, commands
    command = commands[name]
    if folder:
        assert f"`{command}`" in line and line in (root / "AGENTS.md").read_text("utf-8")
    else:
        assert command == line
        rules = (PLUGIN_ROOT / "AGENTS.md").read_text("utf-8")
        assert "`chantier gate <cr> scenario`" in rules

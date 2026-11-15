"""The long gate's refusals: its `long_gate:` key in chantier.yaml, and `--stop`'s usage."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from batch_helpers import open_batch, record
from conftest import Chantier, sh

from chantier.commands import orders_merged
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE
from chantier.core.repo import Repo

GATE = "python -c pass"
WHOLE = '"parallel" is a whole number'
KEYS = [
    ("zero", "long_gate:\n  parallel: 0\n", WHOLE),
    ("a word", "long_gate:\n  parallel: two\n", WHOLE),
    ("an unknown key", "long_gate:\n  slots: 2\n", 'unknown key "slots"'),
]
LINE = 2


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

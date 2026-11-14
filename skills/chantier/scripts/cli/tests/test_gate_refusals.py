"""The long gate's refusals: its `long_gate:` key in chantier.yaml, and `--stop`'s usage."""

from __future__ import annotations

from pathlib import Path

import pytest
from batch_helpers import open_batch, record
from conftest import Chantier, sh

from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE

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


def test_gate_stop_takes_no_command_and_gate_needs_one_and_nothing_running_is_not_an_error(
    gated: tuple[Path, Chantier, str],
) -> None:
    _, chantier, one = gated
    assert chantier("gate", one, "--stop", GATE)[0] == EXIT_USAGE
    assert chantier("gate", one)[0] == EXIT_USAGE
    code, out, _ = chantier("gate", one, "--stop")
    assert code == 0 and any("nothing to stop" in ln for ln in out)

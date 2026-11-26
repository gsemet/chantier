"""A role's start reading is its brief: the card `roles.yaml` names for it first, and its bytes at
or below the figure measured on the swapped cards (CR-510). The paths of the run are counted as one
byte each, so the figures hold on every machine."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import PLUGIN_ROOT, SKILL, Chantier
from test_brief import NAMES, ROLES, _run, _world

# role -> the brief's bytes on the claude host, rounded up to the next 100
BRIEF_BYTES: dict[str, int] = {
    "cr-driver": 9_900,
    "release-driver": 9_600,
    "stack-driver": 9_200,
    "qa-driver": 6_100,
    "coder": 4_000,
    "conflict-resolver": 3_900,
    "debugger": 3_700,
    "inspector": 4_400,
    "investigator": 3_900,
    "verifier": 5_500,
    "spec-writer": 3_000,
    "spec-critic": 2_900,
    "board-griller": 2_900,
    "retro-critic": 2_800,
    "demo-explorer": 2_800,
    "chief-of-staff": 24_400,
    "griller": 6_500,
    "foreman": 22_200,
}


@pytest.mark.parametrize("role", NAMES)
def test_each_roles_brief_starts_with_its_card_and_stays_within_its_figure(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    kind = "stack" if role == "stack-driver" else "parallel"
    unit, lease, _ = _world(repo, chantier, monkeypatch, "claude", kind)[role]
    out = _run(chantier, role, unit, lease)
    path = Path(out[-1].removeprefix("Read ").removesuffix(" whole, first."))
    text = path.read_text(encoding="utf-8")
    card = (SKILL / "references" / ROLES[role].card).read_text(encoding="utf-8")
    assert text.startswith(card.rstrip("\n") + "\n\n=== floor\n")
    runs = [f for p in (repo.parent, PLUGIN_ROOT) for f in (p.resolve(), p)]
    for run_path in sorted((str(p) for p in runs), key=len, reverse=True):
        text = text.replace(Path(run_path).as_posix(), ".").replace(run_path, ".")
    total = len(text.encode("utf-8"))
    print(f"brief-bytes role={role} bytes={total}")
    assert total <= BRIEF_BYTES[role], (role, total)

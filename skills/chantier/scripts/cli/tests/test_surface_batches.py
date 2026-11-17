"""The other batches of a planning surface, as one line."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chantier.core.repo import Repo
from chantier.core.surface_batches import other_batches

FOREMAN = {
    "id": "batch-05",
    "status": "running",
    "steering": "foreman",
    "crs": [{"id": "CR-1", "status": "working"}, {"id": "CR-2", "status": "working"}],
    "orders": [{"id": "ORD-1", "kind": "qa"}],
}
PAUSED = {"id": "batch-02", "status": "paused", "steering": "direct"}
HEAD = "other batches on this surface: "
PAUSED_TEXT = "beta batch-02 paused, steering direct (the Chief of Staff), 0 Drivers"


def _surface(tmp_path: Path, batches: dict[str, object]) -> Path:
    for name in ("alpha", "beta", "gamma"):
        (tmp_path / "projects" / name / "changes" / "4-batch").mkdir(parents=True)
    for name, data in batches.items():
        text = data if isinstance(data, str) else json.dumps(data)
        (tmp_path / "projects" / name / "changes" / "4-batch" / "batch.json").write_text(text)
    return tmp_path


def _repo(root: Path, own: str, external: bool) -> Repo:
    folder = root / "projects" / own
    return Repo(root, root / ".git", {}, folder if external else None, root if external else None)


@pytest.mark.parametrize(
    ("batches", "own", "external", "expected"),
    [
        (
            {"alpha": FOREMAN, "beta": PAUSED},
            "gamma",
            True,
            f"{HEAD}alpha batch-05 running, steering Foreman, 3 Drivers; {PAUSED_TEXT}",
        ),
        ({"alpha": FOREMAN, "beta": PAUSED}, "alpha", True, HEAD + PAUSED_TEXT),
        ({"alpha": FOREMAN}, "alpha", True, None),
        ({"alpha": FOREMAN, "beta": PAUSED}, "gamma", False, None),
        ({"alpha": "{not json"}, "gamma", True, HEAD + "alpha: batch.json unreadable"),
        (
            {"alpha": {**FOREMAN, "stack_agent": "s", "closing": True}},
            "gamma",
            True,
            HEAD + "alpha batch-05 closing, steering Foreman, 4 Drivers",
        ),
    ],
)
def test_the_other_batches_of_the_surface_are_one_line(
    tmp_path: Path, batches: dict[str, object], own: str, external: bool, expected: str | None
) -> None:
    root = _surface(tmp_path, batches)
    assert other_batches(_repo(root, own, external)) == expected

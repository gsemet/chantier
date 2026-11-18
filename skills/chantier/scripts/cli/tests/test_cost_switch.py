"""After a steering switch, the receipt's steering outside the budget is the `cost` text's."""

from __future__ import annotations

from pathlib import Path

import pytest
from batch_helpers import record, write_record
from conftest import Chantier
from cost_world import CostWorld, build, later, msg

from chantier.board.costs import compute
from chantier.core.repo import Repo

CHIEF_STEERING = "Chief of Staff, steering the batch (outside the budget): "


@pytest.fixture
def world(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> CostWorld:
    return build(repo, chantier, monkeypatch, tmp_path)


def test_the_receipt_shows_the_steering_outside_the_budget_the_text_prints_after_a_switch(
    world: CostWorld,
) -> None:
    def ts(minutes: int) -> str:
        return later(world, minutes)

    # the Chief of Staff claimed at +5, the Foreman at +10, the Chief of Staff again at +15
    claims = [("uuid-chief", 5), ("uuid-foreman", 10), ("uuid-chief", 15)]
    write_record(
        world.repo,
        {
            **record(world.repo),
            "steering": "direct",
            "chief_transcript": "uuid-chief",
            "chief_transcripts": ["uuid-chief"],
            "foreman_claims": [{"transcript": t, "since": ts(m)} for t, m in claims],
        },
    )
    # calls at +2 (before the first claim) and +12 (in the Foreman's stint) are outside its windows
    world.chief.write_text(
        "".join(msg(f"s{m}", 300, timestamp=ts(m)) for m in (2, 6, 12, 16)), encoding="utf-8"
    )
    line = next(ln for ln in world.cost() if ln.startswith(CHIEF_STEERING))
    steering = compute(Repo.find())["receipt"]["outside"]["steering"]
    assert steering is not None and "(2 calls)" in line and steering["calls"] == 2  # noqa: PLR2004
    assert f"${steering['usd']:.2f} since the batch opened" in line

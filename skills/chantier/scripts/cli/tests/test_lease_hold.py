"""A lease hold's refusals, and the board's read of the leases."""

from __future__ import annotations

from typing import Any

import pytest
from batch_helpers import record, write_record
from test_leases import SECOND, T0, Led, leased  # noqa: F401

from chantier.board.fingerprint import fingerprint
from chantier.board.state import project_state
from chantier.core.errors import EXIT_USAGE
from chantier.core.repo import Repo


@pytest.mark.parametrize(
    "tail",
    [("--minutes", 0), ("--minutes", 91), ("--minutes", "x"), ("--", "echo", "x"), ("--minutes",)],
)
def test_a_hold_outside_one_to_ninety_minutes_or_with_a_command_is_refused(
    leased: Led,  # noqa: F811
    tail: tuple[object, ...],
) -> None:
    repo, chantier, (one, _) = leased
    before = record(repo)
    code, _, err = chantier.bare("lease", one, "hold", "--lease", 1, *tail)
    assert code == EXIT_USAGE, err
    assert record(repo) == before  # nothing recorded
    if "--" in tail:
        assert "runs no command: start your wait yourself" in err


def test_the_board_shows_each_lease_as_facts_and_a_hold_moves_its_rev(
    leased: Led,  # noqa: F811
) -> None:
    repo, chantier, (one, two) = leased
    found = Repo.find(readonly=True)

    def shown() -> tuple[dict[str, Any], Any]:
        batch = project_state("p", found, False, None)["batch"]
        return {r["cr"]: r["lease"] for r in batch["crs"]}, batch["stack_lease"]

    rows, stack = shown()
    assert rows[two] is None and stack is None  # never taken: null
    expires = "2030-01-01T00:10:00Z"
    facts = {"n": 1, "renewed": T0, "expires": expires, "ended": None, "gate": None}
    assert rows[one] == facts  # facts only: never the word `live`, which moves with the clock
    before = fingerprint(found.store, found.changes)
    assert chantier.bare("lease", one, "hold", "--lease", 1)[0] == 0
    assert fingerprint(found.store, found.changes) != before  # a hold moves the record, so the rev
    assert shown()[0][one]["expires"] == "2030-01-01T00:45:00Z"
    data = record(repo)
    data["stack_lease"] = {"n": 2, "taken": T0, "renewed": T0, "expires": expires, "ended": None}
    next(c for c in data["crs"] if c["id"] == one)["lease"]["ended"] = T0  # handed back
    write_record(repo, data)
    rows, stack = shown()
    assert rows[one]["ended"] == T0 and stack["n"] == SECOND

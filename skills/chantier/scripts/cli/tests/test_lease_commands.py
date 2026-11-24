"""Each lease refusal names the exact command, by the unit's kind and the lease's state."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from test_leases import T0, Led, at, leased  # noqa: F401  (leased is a fixture)

from chantier.core import leases
from chantier.core.errors import EXIT_CONFLICT, EXIT_PRECONDITION, ChantierError
from chantier.core.records import BatchRecord, Lease, OrderRecord
from chantier.core.repo import Repo

REPO = cast(Repo, SimpleNamespace())  # a stack's and an order's lease read no gate


def held(taken: str) -> Lease:
    return Lease(n=3, taken=T0, renewed=taken, expires="2030-01-01T00:10:00Z")


@pytest.mark.parametrize(
    ("unit", "live", "words"),
    [
        ("stack", False, "then `take stack --reclaim --epoch <n>`"),
        ("O-1", False, "then `agents set O-1 <id> --reclaim --epoch <n>`"),
        ("stack", True, "`agents set stack - --epoch <n>` ends it; `take stack --reclaim"),
        ("O-1", True, "`agents set O-1 - --epoch <n>` ends it; `agents set O-1 <id> --reclaim"),
    ],
)
def test_check_free_names_the_command_of_the_units_kind(
    monkeypatch: pytest.MonkeyPatch, unit: str, live: bool, words: str
) -> None:
    from chantier.core import clock  # noqa: PLC0415

    monkeypatch.setattr(clock, "_fixed", [])
    clock.fix("2030-01-01T00:05:00Z" if live else "2030-01-01T00:11:00Z")
    d = BatchRecord(id="batch-01", mode="stack", stack_lease=held(T0))
    d.orders = [OrderRecord(id="O-1", kind="qa", lease=held(T0))]
    with pytest.raises(ChantierError) as e:
        leases.check_free(REPO, d, unit, False)
    assert e.value.code == EXIT_CONFLICT and words in str(e.value)
    if live:
        assert "only on the user's word" in str(e.value)


def test_a_cr_refusal_and_the_ship_with_no_lease_name_their_commands(leased: Led) -> None:  # noqa: F811
    _repo, chantier, (one, _) = leased
    resume = ("take", one, "--note", "resume: stuck", "--epoch", 1)
    at(5)
    live = chantier.bare(*resume)[2]
    assert f"`agents set {one} - --epoch <n>` ends it; `take {one} --reclaim ...` only on" in live
    code, _, err = chantier.bare("ship", one, "https://example.invalid/pr/1")
    assert code == EXIT_PRECONDITION and f"ship {one} needs --lease <n>" in err
    assert f"{one}'s lease 1 is live until 00:10:00: its Driver ships it" in err
    assert f"`agents set {one} - --epoch <n>` ends the lease and `ship` with no --lease" in err
    at(11)
    late = chantier.bare(*resume)[2]
    reclaim = f'`take {one} --reclaim --note "resume: lease not confirmed" --epoch <n>`'
    assert f"check with the host that its Driver ended, then {reclaim}" in late
    _, _, err = chantier.bare("ship", one, "https://example.invalid/pr/1")
    assert f"{one}'s lease 1 not confirmed since 00:10 (1 min ago)" in err
    assert f"{reclaim} starts a new Driver, which ships it" in err
    at(5)
    assert chantier.bare("agents", "set", one, "-", "--epoch", 1)[0] == 0
    _, _, err = chantier.bare("ship", one, "https://example.invalid/pr/1")
    assert "needs --lease" not in err  # an ended lease: the stack driver ships with none

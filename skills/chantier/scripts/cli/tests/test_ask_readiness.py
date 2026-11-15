"""The readiness key of an ask: which asks supersede one another (CR-272)."""

from __future__ import annotations

import pytest

from chantier.rails_release import readiness_key

CRS = ["CR-261", "CR-262"]


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("ready-to-merge CR-261 slug https://x gaps: a", ("cr", "CR-261")),
        ("pr-in-draft cr-262 https://x on main: waits for y", ("cr", "CR-262")),
        ("ready-locally 261", ("cr", "CR-261")),
        ("ready-to-merge CR-999 slug https://x", None),
        ("ready-to-merge", None),
        ("question CR-261 which?", None),
        ("blocked CR-261 why", None),
        ("stack-ready-to-merge https://x CR-261=https://y", ("stack", "")),
        ("", None),
    ],
)
def test_readiness_key(text: str, key: tuple[str, str] | None) -> None:
    assert readiness_key(text, CRS) == key

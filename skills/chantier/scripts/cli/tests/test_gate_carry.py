"""The carry check of a long gate over a rebase: what it says when git cannot prove it."""

from __future__ import annotations

from pathlib import Path

import pytest

from chantier.commands import crs
from chantier.commands.crs import carry_check, git_version


@pytest.mark.parametrize(
    ("version", "words"),
    [
        ((2, 37, 1), "git 2.37.1 is older than 2.38"),
        ((2, 30), "git 2.30 is older than 2.38"),
        ((), "git ? is"),
    ],
)
def test_a_git_older_than_2_38_refuses_the_carry_and_says_so(
    monkeypatch: pytest.MonkeyPatch, version: tuple[int, ...], words: str
) -> None:
    monkeypatch.setattr(crs, "git_version", lambda: version)

    def never(*args: str, **kw: object) -> str:
        raise AssertionError(f"no other method: git {args}")

    monkeypatch.setattr(crs, "git", never)
    why = carry_check(Path("."), "origin/main", "head", "gated")
    assert why is not None and words in why and "no merge-tree" in why


@pytest.mark.parametrize(
    ("text", "version"),
    [
        ("git version 2.43.0.windows.1", (2, 43, 0)),
        ("git version 2.38.0", (2, 38, 0)),
        ("git version 2.37.1 (Apple Git-137.1)", (2, 37, 1)),
        ("", ()),
    ],
)
def test_the_git_version_reads_as_numbers(
    monkeypatch: pytest.MonkeyPatch, text: str, version: tuple[int, ...]
) -> None:
    monkeypatch.setattr(crs, "git", lambda *a, **k: text)
    assert git_version() == version

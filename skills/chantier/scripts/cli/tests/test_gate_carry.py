"""The carry check of a long gate over a rebase: what it says when git cannot prove it, and what
it proves on a small prepared repository."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import sh

from chantier.commands import crs
from chantier.commands.crs import Judged, carry_check, git_version
from chantier.core.errors import ChantierError


@pytest.mark.parametrize(
    ("version", "words"),
    [
        ((2, 38, 1), "git 2.38.1 is older than 2.39"),
        ((2, 30), "git 2.30 is older than 2.39"),
        ((), "git ? is"),
    ],
)
def test_a_git_older_than_2_39_refuses_the_carry_and_says_so(
    monkeypatch: pytest.MonkeyPatch, version: tuple[int, ...], words: str
) -> None:
    monkeypatch.setattr(crs, "git_version", lambda: version)

    def never(*args: str, **kw: object) -> str:
        raise AssertionError(f"no other method: git {args}")

    monkeypatch.setattr(crs, "git", never)
    why = carry_check(Path("."), Judged("gated", "base", "gated"), "head", "newbase")
    assert why is not None and words in why and "no patch-id --verbatim" in why


@pytest.mark.parametrize(
    ("text", "version"),
    [
        ("git version 2.43.0.windows.1", (2, 43, 0)),
        ("git version 2.39.0", (2, 39, 0)),
        ("git version 2.37.1 (Apple Git-137.1)", (2, 37, 1)),
        ("", ()),
    ],
)
def test_the_git_version_reads_as_numbers(
    monkeypatch: pytest.MonkeyPatch, text: str, version: tuple[int, ...]
) -> None:
    monkeypatch.setattr(crs, "git", lambda *a, **k: text)
    assert git_version() == version


def commit(wt: Path, name: str, text: str, message: str) -> str:
    (wt / name).write_text(text, encoding="utf-8", newline="\n")
    sh("git", "add", name, cwd=wt)
    sh("git", "-c", "user.name=t", "-c", "user.email=t@e.com", "commit", "-qm", message, cwd=wt)
    return sh("git", "rev-parse", "HEAD", cwd=wt)


def git_at(wt: Path, *args: str) -> str:
    return sh("git", "-c", "user.name=t", "-c", "user.email=t@e.com", *args, cwd=wt)


@pytest.fixture
def shape(tmp_path: Path) -> dict[str, str]:
    """CR-316's shape: X judged on A's branch, then B's branch (A rewritten) to move onto."""
    wt = tmp_path / "w"
    wt.mkdir()
    sh("git", "init", "-q", "-b", "main", str(wt))
    root = commit(wt, "root.txt", "root\n", "root")
    a_tip = commit(wt, "a.txt", "a\n", "A")
    g = commit(wt, "x.txt", "x\n", "X")
    sh("git", "checkout", "-q", "-b", "b", root, cwd=wt)
    b_tip = commit(wt, "a.txt", "a rewritten\n", "A, rewritten")
    sh("git", "checkout", "-q", "-b", "moved", b_tip, cwd=wt)
    git_at(wt, "cherry-pick", g)
    return {
        "wt": str(wt),
        "g": g,
        "a": a_tip,
        "b": b_tip,
        "moved": sh("git", "rev-parse", "HEAD", cwd=wt),
        "root": root,
    }


def _edit(shape: dict[str, str], name: str, text: str, message: str) -> str:
    return commit(Path(shape["wt"]), name, text, message)


def _added(shape: dict[str, str]) -> tuple[str, str]:
    return _edit(shape, "y.txt", "y\n", "after the verdict"), "the rebase changed the patch"


def _spaced(shape: dict[str, str]) -> tuple[str, str]:
    wt = Path(shape["wt"])
    sh("git", "reset", "-q", "--hard", shape["b"], cwd=wt)
    return _edit(shape, "x.txt", "x \n", "X with a space"), "the rebase changed the patch"


def _merged(shape: dict[str, str]) -> tuple[str, str]:
    wt = Path(shape["wt"])
    sh("git", "checkout", "-q", "-b", "side", shape["root"], cwd=wt)
    _edit(shape, "s.txt", "s\n", "side")
    sh("git", "checkout", "-q", "moved", cwd=wt)
    git_at(wt, "merge", "--no-ff", "-m", "merge", "side")
    return sh("git", "rev-parse", "HEAD", cwd=wt), "a merge commit in"


def _clean(shape: dict[str, str]) -> tuple[str, str]:
    return shape["moved"], ""


CASES = {
    "a: CR-316, moved onto another CR's branch": _clean,
    "b: a commit added": _added,
    "c: a whitespace-only change": _spaced,
    "d: a merge commit": _merged,
}


@pytest.mark.parametrize("case", list(CASES))
def test_the_carry_compares_the_exact_patch_ids_of_the_crs_own_commits(
    shape: dict[str, str], case: str
) -> None:
    wt = Path(shape["wt"])
    head, why = CASES[case](shape)
    got = carry_check(wt, Judged(shape["g"], shape["a"], shape["g"]), head, shape["b"])
    assert (got is None) if not why else (got is not None and why in got), got


def test_a_pass_with_no_recorded_base_does_not_carry_and_nothing_is_guessed(
    shape: dict[str, str],
) -> None:
    wt = Path(shape["wt"])
    for what, words in (("pass", "run the long gate again"), ("verdict", "verify again")):
        got = carry_check(
            wt, Judged(shape["g"], None, shape["g"]), shape["moved"], shape["b"], what
        )
        assert got is not None and "recorded no base" in got and words in got
    none = carry_check(wt, Judged(shape["g"], shape["a"], shape["g"]), shape["moved"], None)
    assert none is not None and "no base to prove it" in none


def test_a_ref_git_cannot_read_raises(shape: dict[str, str]) -> None:
    with pytest.raises(ChantierError, match="cannot be read"):
        carry_check(
            Path(shape["wt"]), Judged(shape["g"], "f" * 40, shape["g"]), shape["moved"], shape["b"]
        )


def test_a_failing_git_is_named_and_never_read_as_a_changed_patch(
    shape: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    real = subprocess.run

    def run(argv: list[str], *a: Any, **kw: Any) -> Any:
        if argv[:2] == ["git", "patch-id"]:
            return subprocess.CompletedProcess(argv, 128, b"", b"fatal: boom\nmore\n")
        return real(argv, *a, **kw)

    monkeypatch.setattr(subprocess, "run", run)
    got = carry_check(
        Path(shape["wt"]), Judged(shape["g"], shape["a"], shape["g"]), shape["moved"], shape["b"]
    )
    assert got == (
        f"git could not read the patch-ids of {shape['a'][:7]}..{shape['g'][:7]}: fatal: boom"
    )

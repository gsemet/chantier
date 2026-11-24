"""The cards say how to react to the chain check (CR-442): the driver's and the Foreman's."""

from __future__ import annotations

from pathlib import Path

CARDS = Path(__file__).resolve().parents[3] / "references"
NOT_BASED = "branch not based on"


def section(text: str, start: str, end: str) -> str:
    return " ".join(text.split(start, 1)[1].split(end, 1)[0].split())


def test_the_cards_carry_the_chain_check() -> None:
    driver = (CARDS / "driver.md").read_text(encoding="utf-8")
    stack = section(driver, "\n## Stack driver", "\n## QA driver")
    release = section(driver, "\n## Release driver", "\n## Startup core")
    retake = (CARDS / "driver-retake.md").read_text(encoding="utf-8")
    cr = " ".join(retake.split())  # the CR driver's re-takes, now their own piece
    for word in (
        "merge-base --is-ancestor",
        NOT_BASED,
        "branch moved since its last ship",
        "not shipped at",
        "PRs the refusal names",
        "gh pr ready --undo",
        "stack --out-of-draft` again",
    ):
        assert word in stack, word
    check = stack.split("**Check the chain.**", 1)[1].split("**", 1)[0]
    assert check.index("merge-base") < check.index("gh pr ready")
    assert NOT_BASED in release
    for text in (stack, cr, release):
        assert "holds the merge (`status` shows it merged)" in text
    mode = retake.split("A CR taken (or a `note`) with `rebase: mode", 1)[1].split("\n\n", 1)[0]
    assert mode.index("rebase onto") < mode.index("`ship`")
    foreman = (CARDS / "foreman-stack.md").read_text(encoding="utf-8")
    assert "not shipped at" in " ".join(foreman.split())

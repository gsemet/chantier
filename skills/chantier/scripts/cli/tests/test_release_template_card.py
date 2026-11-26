import re
from collections.abc import Callable

import pytest
from conftest import PLUGIN_ROOT, SKILL

REFS = SKILL / "references"
TEMPLATE = REFS / "release-template.md"
PROCESS = PLUGIN_ROOT / "docs" / "release-process.md"
QUESTIONS = 10
EVIDENCE = REFS / "topics" / "release-evidence.md"
PR_EXTRAS = REFS / "topics" / "pr-extras.md"
IMAGE_BULLET = "A Driver never opens an image file"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _template() -> str:
    return _norm(TEMPLATE.read_text(encoding="utf-8"))


def _driver_bullet() -> str:
    lines = PR_EXTRAS.read_text(encoding="utf-8").splitlines()
    return next(line for line in lines if line.startswith(f"- {IMAGE_BULLET}"))


def _self_check_questions() -> list[str]:
    raw = TEMPLATE.read_text(encoding="utf-8")
    section = raw.split("### Self-check", 1)[1].split("\n## ", 1)[0]
    return re.findall(r"^\d+\. ", section, flags=re.MULTILINE)


def _contributors_item() -> str:
    text = _norm(PROCESS.read_text(encoding="utf-8"))
    start = text.index("For contributors")
    return text[start : text.index(")", start) + 1]


def _h1_line() -> str:
    return next(
        line for line in PROCESS.read_text(encoding="utf-8").splitlines() if "<h1 align" in line
    )


def _check_kinds(t: str) -> None:
    for kind in ("feature", "fix", "restore", "breaking", "internal"):
        assert f"**{kind}**" in t
    assert "`X.Y.Z`" in t


def _check_labels(t: str) -> None:
    for label in ("Fixed:", "Removed:", "Changed:", "Known issue:"):
        assert label in t


def _check_budgets(t: str) -> None:
    budgets = ("at most 16 words", "at most 20;", "at most 40 (", "at most 120 words")
    for words in (*budgets, "and 250 for"):
        assert words in t
    evidence = _norm(EVIDENCE.read_text(encoding="utf-8"))
    for px in ("900 to 1200 px", "600 px"):
        assert px in evidence


def _check_order(t: str) -> None:
    assert "breaking, feature, restore, fix, internal" in t


def _check_ten_questions(_: str) -> None:
    assert len(_self_check_questions()) == QUESTIONS


def _check_anchors(t: str) -> None:
    for heading in ("### Writing rules", "### A highlight"):
        assert heading in t


def _check_gone(t: str) -> None:
    assert "the highlight says so in one line" not in t
    assert "a picture it cannot crop stays whole" not in t


def _check_driver_exception(_: str) -> None:
    assert "The release driver reads the images it produced" in _driver_bullet()


def _check_process_title(_: str) -> None:
    line = _h1_line()
    assert "chantier X.Y.Z" in line
    assert "chantier X.Y</h1>" not in line


def _check_process_contributors(_: str) -> None:
    assert "known issue" not in _contributors_item().lower()


@pytest.mark.parametrize(
    "check",
    [
        _check_kinds,
        _check_labels,
        _check_budgets,
        _check_order,
        _check_ten_questions,
        _check_anchors,
        _check_gone,
        _check_driver_exception,
        _check_process_title,
        _check_process_contributors,
    ],
    ids=lambda f: f.__name__.removeprefix("_check_"),
)
def test_release_template_card(check: Callable[[str], None]) -> None:
    check(_template())

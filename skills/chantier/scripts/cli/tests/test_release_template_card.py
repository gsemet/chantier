import json
import re
from collections.abc import Callable

import pytest
from conftest import PLUGIN_ROOT, SKILL

REFS = SKILL / "references"
TEMPLATE = REFS / "release-template.md"
PROCESS = PLUGIN_ROOT / "docs" / "release-process.md"
QUESTIONS = 10
IMAGE_BULLET = "A Driver never opens an image file"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _template() -> str:
    return _norm(TEMPLATE.read_text(encoding="utf-8"))


def _driver_bullet() -> str:
    for path in sorted(REFS.glob("driver*.md")):
        text = _norm(path.read_text(encoding="utf-8"))
        if IMAGE_BULLET in text:
            start = text.index(IMAGE_BULLET)
            end = text.find(" - ", start)
            return text[start : end if end != -1 else len(text)]
    raise AssertionError("the driver card's image bullet is not in any driver*.md")


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
    for words in ("16", "20", "40", "120", "250"):
        assert f"at most {words} words" in t or f"at most {words} for" in t
    for px in ("900", "1200", "600 px"):
        assert px in t


def _check_order(t: str) -> None:
    assert "breaking, feature, restore, fix, internal" in t


def _check_ten_questions(_: str) -> None:
    assert len(_self_check_questions()) == QUESTIONS


def _check_anchors(t: str) -> None:
    for heading in ("### Writing rules", "### A highlight", "## Visible evidence"):
        assert heading in t


def _check_gone(t: str) -> None:
    assert "the highlight says so in one line" not in t
    assert "a picture it cannot crop stays whole" not in t


def _check_driver_exception(_: str) -> None:
    bullet = _driver_bullet()
    assert "Release Driver" in bullet
    assert "release-template" in bullet


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


def test_release_template_is_an_action_reading_only() -> None:
    manifest = json.loads((REFS / "startup-manifest.json").read_text(encoding="utf-8"))
    assert "release-template.md" not in json.dumps(manifest["startup_sections"])
    assert manifest["common"] != "release-template.md"
    assert manifest["role_core"] != "release-template.md"

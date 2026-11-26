"""No card, doc or web string names the surface server's old command, `chantier board`."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
TEXT = re.compile(r"\$CHANTIER board|`chantier board[ `]|`board --")
WEB = re.compile(r"chantier board -")
SAID = {
    "dollar": "run `$CHANTIER board --seat <id>` now",
    "backticked": "run `chantier board --new-key` now",
    "closed": "start `chantier board` first",
    "flag": "pass `board --seat <id>` now",
}


def _texts() -> list[Path]:
    where = [
        *ROOT.glob("skills/chantier/references/**/*.md"),
        *ROOT.glob("agents/**/*.md"),
        *ROOT.glob("com.github.copilot/agents/**/*.md"),
        *[ROOT / n for n in ("AGENTS.md", "CONTRIBUTING.md", "README.md", "evals/README.md")],
        ROOT / "scenario" / "README.md",
        *(p for p in ROOT.glob("docs/**/*.md") if "release-notes" not in p.parts),
    ]
    return sorted({p for p in where if p.is_file()})


def _web() -> list[Path]:
    return sorted(ROOT.glob("skills/chantier/scripts/cli/src/chantier/clients/web/js/i18n/*.js"))


@pytest.mark.parametrize("form", sorted(SAID))
def test_the_check_finds_each_old_form(form: str) -> None:
    assert TEXT.search(SAID[form])
    assert WEB.search("chantier board --new-key")


def test_the_tree_names_the_old_command_nowhere() -> None:
    assert _texts() and _web()
    found = [
        f"{p.relative_to(ROOT)}:{n}"
        for p, rule in [(p, TEXT) for p in _texts()] + [(p, WEB) for p in _web()]
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if rule.search(line)
    ]
    assert not found


def test_the_blocked_sync_steps_name_the_serve_holder_and_its_stop() -> None:
    refs = ROOT / "skills/chantier/references"
    text = (refs / "sync-checkout.md").read_text(encoding="utf-8")
    step4 = next(s for s in text.splitlines() if s.startswith("4. With any holder"))
    offer = (refs / "topics" / "sync-offer-p1.md").read_text(encoding="utf-8")
    assert "PID <n> serve <project> (started by webui)" in step4
    assert "taskkill /PID <n> /T /F" in offer and "kill <n>" in offer

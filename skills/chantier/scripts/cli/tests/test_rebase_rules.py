"""The rebase rules of P10, their commands and the cards' wording of a refused rebase."""

import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from conftest import SKILL, Chantier, sh

from chantier.commands.allow_samples import RECOMMENDED_ALLOW, SAMPLES, fill_sample, filled_allow
from chantier.commands.permissions import _gap, project_remote, rule_matches

_ONTO_CHANTIER = "git -C /w rebase --onto chantier/batch-01/cr-101-x 0123abc"
_ONTO_ORIGIN = "git -C /w rebase --onto origin/main chantier/batch-01/cr-102-y"
REBASE_CASES = (
    ("git -C /w rebase origin/main", "git -C * rebase origin/*"),
    ("git -C /w rebase origin/chantier/batch-01/cr-101-x", "git -C * rebase origin/*"),
    ("git -C /w rebase chantier/batch-01/cr-101-x", "git -C * rebase chantier/*"),
    (_ONTO_CHANTIER, "git -C * rebase --onto chantier/* *"),
    (_ONTO_ORIGIN, "git -C * rebase --onto origin/* *"),
    ("git -C /w rebase --continue", "git -C * rebase --continue"),
    ("git -C /w rebase --abort", "git -C * rebase --abort"),
    ("git rebase origin/main", "git rebase origin/*"),
    ("git rebase chantier/batch-01/cr-101-x", "git rebase chantier/*"),
)


@pytest.mark.parametrize(("command", "rule"), REBASE_CASES)
def test_each_rebase_command_of_the_cards_is_matched_by_its_rule(command: str, rule: str) -> None:
    assert f"Bash({rule})" in RECOMMENDED_ALLOW and f"PowerShell({rule})" in RECOMMENDED_ALLOW
    assert all(rule_matches(f"{tool}({rule})", tool, command) for tool in ("Bash", "PowerShell"))


@pytest.mark.parametrize(
    "command", ["git -C /w rebase main", "git -C /w rebase --root", "git rebase -i origin/main"]
)
def test_the_narrow_rebase_rules_match_no_other_form(command: str) -> None:
    rebase_rules = [r for r in RECOMMENDED_ALLOW if " rebase " in r]
    assert rebase_rules and all(r.startswith(("Bash(", "PowerShell(")) for r in rebase_rules)
    assert not any(rule_matches(r, r.split("(")[0], command) for r in rebase_rules)


def test_the_rebase_rules_carry_the_projects_remote(repo: Path) -> None:
    sh("git", "remote", "add", "upstream", "git@github.com:a/b.git", cwd=repo)
    configured: Any = SimpleNamespace(root=repo, config={"remote": "upstream"})
    plain: Any = SimpleNamespace(root=repo, config={})
    assert project_remote(configured) == "upstream"
    assert project_remote(plain) == "origin"
    rows = [fill_sample(s) for s in SAMPLES if " rebase " in s[2]]
    gap = _gap(rows, "upstream", {"allow": [], "deny": [], "ask": []}, send=False)
    text = " ".join(gap.named)
    assert "git -C * rebase upstream/*" in text and "git -C * rebase --onto upstream/* *" in text
    assert "origin" not in text


def test_preflight_names_the_rebase_rules_and_a_deny_of_them(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    settings = repo / ".claude"
    settings.mkdir()

    def p10(permissions: dict[str, list[str]]) -> str:
        (settings / "settings.local.json").write_text(
            json.dumps({"permissions": permissions}), encoding="utf-8"
        )
        code, out, _ = chantier("preflight")
        assert code == 0
        return next(ln for ln in out if ln.startswith("P10"))

    pushes = [r for r in RECOMMENDED_ALLOW if " push " in r]
    line = p10({"allow": pushes})  # the push rules alone do not cover the rebase
    assert "git -C * rebase chantier/*" in line
    assert "add Bash(git -C * rebase origin/*)" in line
    line = p10({"allow": list(filled_allow()), "deny": ["Bash(git -C * rebase*)"]})
    assert line.startswith("P10 warn") and "denied: git -C" in line and "rebase" in line


def test_no_card_asks_the_user_about_a_refused_push_without_the_rebase() -> None:
    refs = SKILL / "references"
    said = re.compile(r"asked only if (both|the host refuses you too)|only if both are refused")
    for card in sorted(refs.rglob("*.md")):
        for para in re.split(r"\n\s*\n", card.read_text(encoding="utf-8")):
            flat = " ".join(para.split())
            if said.search(flat):
                assert "rebase" in flat, (card.name, flat[:120])

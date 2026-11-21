"""P10's chantier rules: the real-path rules named, the broad and the stale rules found."""

import json
import shutil
from pathlib import Path

import pytest
from conftest import PLUGIN_ROOT, SKILL, Chantier

from chantier.commands.allow_samples import filled_allow
from chantier.commands.permissions import PROBES, rule_matches
from chantier.launch import dev_rule, plugin_rule, sync_rule

MAX_OUTPUT_LINES = 10  # past ten lines the tool output is cut


def _mode_root(mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repo: Path) -> Path:
    """The plugin root of the case under test: chantier's checkout (it holds `.git`) for a project
    that is chantier (`dev`: the repository holds chantier's manifest) or another (`other`), or a
    plugin folder with no `.git` (`plugin`)."""
    if mode == "dev":
        (repo / ".claude-plugin").mkdir()
        (repo / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "chantier"}), encoding="utf-8"
        )
    if mode in ("dev", "other"):
        return PLUGIN_ROOT.resolve()
    root = tmp_path / "plug"
    (root / "skills" / "chantier").mkdir(parents=True)
    shutil.copy(SKILL / "SKILL.md", root / "skills" / "chantier" / "SKILL.md")
    monkeypatch.setenv("CHANTIER_SKILL_DIR", str(root / "skills" / "chantier"))
    return root.resolve()


def _p10_of(repo: Path, chantier: Chantier, allow: list[str]) -> str:
    (repo / ".claude").mkdir(exist_ok=True)
    (repo / ".claude" / "settings.local.json").write_text(
        json.dumps({"permissions": {"allow": allow}}), encoding="utf-8"
    )
    code, out, _ = chantier("preflight")
    assert code == 0 and len(out) <= MAX_OUTPUT_LINES, out
    return next(ln for ln in out if ln.startswith("P10"))


@pytest.mark.parametrize("case", ["plugin", "dev", "other"])
def test_preflight_names_the_real_path_rules_and_the_broad_and_stale_ones(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, case: str
) -> None:
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    root = _mode_root(case, tmp_path, monkeypatch, repo)
    mode = "dev" if case == "dev" else "plugin"  # another project from the checkout: plugin mode
    plugin, dev, sync = plugin_rule(root), dev_rule(root), sync_rule(root)
    mine = [plugin] if mode == "plugin" else [dev, sync]
    others = [dev, sync] if mode == "plugin" else [plugin]
    line = _p10_of(repo, chantier, [])  # no chantier rule: the real-path rules are named
    assert all(f"add Bash({r})" in line for r in mine)
    assert not any(f"add Bash({r})" in line for r in others)
    assert not any(rule_matches(r, "Bash", p) for r in filled_allow() for p in PROBES)
    assert _p10_of(repo, chantier, list(filled_allow())).startswith("P10 ok")
    replacing = {  # broad rule -> the rules of this mode it lets through
        "uvx --from * chantier *": [plugin] if mode == "plugin" else [],
        "uv run --no-sync --project * chantier *": [dev] if mode == "dev" else [],
        "uv sync --locked --project *": [sync] if mode == "dev" else [],
        "uv run --locked --project * chantier *": [],
    }
    for broad, rules in replacing.items():
        for held, tail in (([], ""), (list(filled_allow()), " present")):
            line = _p10_of(repo, chantier, [*held, f"Bash({broad})"])
            assert line.startswith("P10 warn") and f"Bash({broad}) (" in line
            assert "settings.local.json" in line and "broad rules let any command through" in line
            if rules:
                assert all(f"replaced by Bash({r}){tail}" in line for r in rules)
                assert tail or " present" not in line
                assert "no chantier command needs it" not in line
            else:
                assert "no chantier command needs it" in line and "replaced by" not in line
    gone, other = tmp_path / "gone", tmp_path / "other"
    other.mkdir()
    old = f'uvx --from "{other.as_posix()}" chantier *'
    stale = [f"Bash({dev_rule(gone)})", f"Bash({sync_rule(gone)})"]
    line = _p10_of(repo, chantier, [*filled_allow(), f"Bash({old})", *stale])
    assert all(r in line.split("stale chantier rules", 1)[1] for r in stale)
    assert (f"Bash({old})" in line.split("stale chantier rules", 1)[1]) == (mode == "plugin")
    line = _p10_of(repo, chantier, [*filled_allow(), f"Bash({dev_rule(other)})"])
    assert line.startswith("P10 ok")  # a dev rule of another existing folder is left alone

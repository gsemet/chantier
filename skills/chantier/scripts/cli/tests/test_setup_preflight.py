import json
import subprocess
import sys

import pytest

from chantier.commands import TEMPLATES, render_plugin_agents
from conftest import PLUGIN_ROOT, SKILL, sh


def test_setup_installs_agents_with_absolute_chantier(repo, chantier):
    code, out, _ = chantier("setup")
    assert code == 0
    assert not (repo / ".agents" / "chantier.json").exists()  # defaults need no file
    for name in ("cr-driver", "stack-driver", "qa-driver", "investigator", "coder", "inspector",
                 "debugger", "verifier", "conflict-resolver"):
        text = (repo / ".claude" / "agents" / f"{name}.md").read_text()
        assert "{{" not in text
        assert "model: inherit" in text
        assert f"references/roles/{name}.md" in text
        assert f"uv run --script {SKILL / 'scripts' / 'cli' / 'chantier.py'}" in text
        assert "# chantier-template: 0.1.0" in text
    assert chantier("setup")[1][0] == "setup: nothing to change (claude)"


def test_setup_keeps_local_edits_unless_forced(repo, chantier):
    chantier("setup")
    agent = repo / ".claude" / "agents" / "coder.md"
    agent.write_text(agent.read_text() + "\nlocal rule\n")
    assert any("kept" in ln for ln in chantier("setup")[1])
    chantier("setup", "--force")
    assert "local rule" not in agent.read_text()


@pytest.mark.parametrize("entry", ["cli", "claude-vscode", ""])
def test_preflight_refuses_outside_desktop(repo, chantier, monkeypatch, entry):
    chantier("setup")
    if entry:
        monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", entry)
    code, out, _ = chantier("preflight")
    assert code == 2
    assert out[0].startswith("P1 FAIL")
    assert out[-1] == "preflight FAILED: start nothing"


def test_preflight_passes_on_desktop(repo, chantier, monkeypatch):
    chantier("setup")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    code, out, _ = chantier("preflight")
    assert code == 0, out
    assert out[-1] == "preflight passed"
    assert all(" ok " in ln for ln in out if ln[:2] in {"P1", "P4", "P5", "P6", "P7"})


def test_preflight_accepts_a_copilot_agent_session(repo, chantier, monkeypatch):
    monkeypatch.setenv("CHANTIER_HOST", "copilot")
    chantier("setup")
    code, out, _ = chantier("preflight")
    assert code == 2 and out[0].startswith("P1 FAIL") and "COPILOT_AGENT_SESSION_ID" in out[0]
    monkeypatch.setenv("COPILOT_AGENT_SESSION_ID", "s-1")
    code, out, _ = chantier("preflight")
    assert code == 0, out
    assert out[0].startswith("P1 ok   host is Copilot")


def test_preflight_fails_without_agent_files(repo, chantier, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    code, out, _ = chantier("preflight")
    assert code == 2
    assert any(ln.startswith("P4 FAIL") and "missing" in ln for ln in out)


def test_preflight_fails_without_1h_cache(repo, chantier, monkeypatch):
    chantier("setup")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    agent = repo / ".claude" / "agents" / "cr-driver.md"
    agent.write_text(agent.read_text().replace("cacheTtl: 1h", "cacheTtl: 5m"))
    code, out, _ = chantier("preflight")
    assert code == 2 and any("no 1h cache in cr-driver" in ln for ln in out)


def test_preflight_fails_in_linked_worktree(repo, chantier, monkeypatch, tmp_path):
    chantier("setup")
    sh("git", "add", ".", cwd=repo)
    sh("git", "commit", "--quiet", "-m", "chantier", cwd=repo)
    wt = tmp_path / "linked"
    sh("git", "worktree", "add", "--quiet", str(wt), "-b", "side", cwd=repo)
    monkeypatch.chdir(wt)
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    code, out, _ = chantier("preflight")
    assert code == 2
    assert any(ln.startswith("P7 FAIL") for ln in out)
    assert any(ln.startswith("P6 FAIL") for ln in out)


def test_nothing_is_created_when_preflight_fails(repo, chantier, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-vscode")
    chantier("preflight")
    assert not (repo / ".agents" / "changes" / "batches").exists()


def test_setup_writes_the_configured_model(repo, chantier):
    chantier("setup")
    (repo / ".agents" / "chantier.models.yml").write_text("claude:\n  roles:\n    verifier: opus\n")
    chantier("setup")
    assert "model: opus" in (repo / ".claude/agents/verifier.md").read_text()
    assert "model: inherit" in (repo / ".claude/agents/coder.md").read_text()


# ---- the Claude Code plugin -----------------------------------------------------------------

@pytest.fixture
def plugin(monkeypatch):
    """The skill runs from the Claude Code plugin, which ships the agents in `agents/`."""
    monkeypatch.setenv("CHANTIER_PLUGIN_ROOT", str(PLUGIN_ROOT))
    return PLUGIN_ROOT


def test_plugin_agents_are_up_to_date():
    for name, text in render_plugin_agents().items():
        shipped = PLUGIN_ROOT / "agents" / f"{name}.md"
        assert shipped.read_text(encoding="utf-8") == text, f"run `just agents` ({name})"
        assert "${CLAUDE_PLUGIN_ROOT}/skills/chantier/references/roles/" in text


def test_plugin_needs_no_file_in_the_repository(repo, chantier, plugin, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    code, out, _ = chantier("preflight")
    assert code == 0, out
    assert any(ln.startswith("P4 ok") for ln in out)
    assert chantier("setup")[1][0] == "setup: nothing to change (claude)"
    assert sh("git", "status", "--porcelain", cwd=repo) == ""
    assert chantier("models", "get", "coder")[1][-1] == "agent: chantier:coder (spawn this agent exactly)"
    code, _, err = chantier("open", "b1", "Fix login", "--slots", 1)
    assert code == 0, err


def test_plugin_override_installs_only_that_role(repo, chantier, plugin, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    (repo / ".agents").mkdir()
    (repo / ".agents" / "chantier.models.yml").write_text("claude:\n  roles:\n    verifier: opus\n")
    code, out, _ = chantier("preflight")
    assert code == 2 and any(ln.startswith("P4 FAIL") and "verifier" in ln for ln in out)
    chantier("setup")
    agents = repo / ".claude" / "agents"
    assert sorted(p.name for p in agents.iterdir()) == ["verifier.md"]
    assert "model: opus" in (agents / "verifier.md").read_text()
    assert chantier("preflight")[0] == 0
    assert chantier("models", "get", "verifier")[1][-1] == "agent: verifier (spawn this agent exactly)"
    assert chantier("models", "get", "coder")[1][-1] == "agent: chantier:coder (spawn this agent exactly)"
    (repo / ".agents" / "chantier.models.yml").unlink()
    out = chantier("setup")[1]
    assert out[0] == "removed .claude/agents/verifier.md (the plugin's agent fits the configuration)"
    assert not (agents / "verifier.md").exists()
    assert not (repo / ".agents" / "chantier-installed.json").exists()


def test_plugin_manifests_agree():
    agent_plugin = json.loads((PLUGIN_ROOT / "plugin.json").read_text())
    claude = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((PLUGIN_ROOT / ".claude-plugin" / "marketplace.json").read_text())
    ext = agent_plugin["extensions"]["com.github.awesome-copilot"]
    assert ext["agents"] == [f"./agents/{n}.md" for n in TEMPLATES]
    assert all((PLUGIN_ROOT / p).exists() for p in ext["agents"] + ext["skills"])
    version = subprocess.run([sys.executable, str(PLUGIN_ROOT / "scripts" / "version.py"), "show"],
                             capture_output=True, text=True, check=True).stdout.strip()
    assert agent_plugin["version"] == claude["version"] == market["plugins"][0]["version"] == version
    assert agent_plugin["name"] == claude["name"] == market["plugins"][0]["name"] == "chantier"

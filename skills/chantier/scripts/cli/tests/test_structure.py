"""The plugin's structure: versions, manifests, generated agents, model lists, roles, links, and a
smoke run in a fresh repository. The batch workflow itself is the scenario's job (`just scenario`).
"""
import importlib.util
import json
import re

import pytest

from chantier import __version__
from chantier.commands import render_plugin_agents
from chantier.models import ROLES, Models
from conftest import PLUGIN_ROOT, SKILL, sh


def _version_script():
    spec = importlib.util.spec_from_file_location("version", PLUGIN_ROOT / "scripts" / "version.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_file_carries_the_same_version():
    version = _version_script()
    for path, pattern, count in version.TARGETS:
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        found = [m.group(1) for m in re.finditer(pattern, text, re.M)]
        assert found == [__version__] * count, path


def test_manifests_agree():
    agent_plugin = json.loads((PLUGIN_ROOT / "plugin.json").read_text(encoding="utf-8"))
    claude = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    markets = [json.loads((PLUGIN_ROOT / p / "marketplace.json").read_text(encoding="utf-8"))
               for p in (".claude-plugin", ".github/plugin")]
    assert {agent_plugin["name"], claude["name"]} | {m["plugins"][0]["name"] for m in markets} \
        == {"chantier"}
    for skill in agent_plugin["extensions"]["com.github.awesome-copilot"]["skills"]:
        assert (PLUGIN_ROOT / skill / "SKILL.md").exists()


@pytest.mark.parametrize("host,folder,suffix", [("claude", "agents", ".md"),
                                                ("copilot", "com.github.copilot/agents", ".agent.md")])
def test_plugin_agents_are_generated_and_up_to_date(host, folder, suffix):
    wanted = render_plugin_agents(host)
    assert sorted(wanted) == sorted(ROLES)
    for name, text in wanted.items():
        shipped = (PLUGIN_ROOT / folder / f"{name}{suffix}").read_text(encoding="utf-8")
        assert shipped == text, f"run `just agents` ({folder}/{name}{suffix})"


@pytest.mark.parametrize("host", ["claude", "copilot"])
def test_base_model_lists_are_valid(host):
    assert Models(host, SKILL, None, base_only=True).errors == []


def test_every_role_has_a_template_and_a_card():
    for role in ROLES:
        assert (SKILL / "assets" / "agents" / f"{role}.md").exists(), role
        assert (SKILL / "references" / "roles" / f"{role}.md").exists(), role


def test_skill_links_resolve():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    links = [m[1] for m in re.finditer(r"\]\(([^)#\s]+)", text) if not m[1].startswith("http")]
    assert links
    for link in links:
        assert (SKILL / link).exists(), link


@pytest.mark.parametrize("host,coder", [("claude", "chantier:coder"), ("copilot", "coder")])
def test_the_plugin_runs_with_no_setup(repo, chantier, monkeypatch, host, coder):
    """A fresh repository: preflight passes, nothing is written, a batch opens."""
    monkeypatch.setenv("CHANTIER_HOST", host)
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    monkeypatch.setenv("COPILOT_AGENT_SESSION_ID", "s-1")
    code, out, _ = chantier("preflight")
    assert code == 0, out
    assert sh("git", "status", "--porcelain", cwd=repo) == ""
    assert chantier("models", "get", "coder")[1][-1] == f"agent: {coder} (spawn this agent exactly)"
    code, _, err = chantier("open", "b1", "Fix login", "--slots", 1)
    assert code == 0, err
    assert chantier("status")[1][-1].startswith("CR-101")


def test_agents_md_names_the_repository_own_agent(repo, chantier, monkeypatch):
    monkeypatch.setenv("CHANTIER_HOST", "copilot")
    agent = repo / ".github" / "agents" / "my-debugger.agent.md"
    agent.parent.mkdir(parents=True)
    agent.write_text("---\nname: my-debugger\n---\nDebug.\n")
    (repo / "AGENTS.md").write_text("- chantier debugger agent: .github/agents/my-debugger.agent.md\n")
    out = chantier("models", "get", "debugger")[1]
    assert out[-1].startswith("agent: my-debugger (from AGENTS.md")
    (repo / "AGENTS.md").write_text("- chantier debugger agent: a.md, b.md\n")
    assert chantier("models", "get", "debugger")[0] == 2

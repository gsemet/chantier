"""The plugin's structure: versions, manifests, static agents, roles, links, and a
smoke run in a fresh repository. The batch workflow itself is the scenario's job (`just scenario`).
"""
import importlib.util
import json
import re
import tomllib

import pytest

from chantier import __version__
from chantier.models import ROLES, agent_pin
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


def test_copilot_cost_helper_declares_pypi():
    text = (SKILL / "scripts" / "cli" / "session_usage.py").read_text(encoding="utf-8")
    block = re.search(r"(?m)^# /// script\n((?:#.*\n)*?)# ///$", text.replace("\r\n", "\n"))
    assert block is not None
    metadata = tomllib.loads("\n".join(
        line[2:] if line.startswith("# ") else line[1:] for line in block[1].splitlines()))
    assert "copilot-session-usage>=1" in metadata["dependencies"]
    indexes = metadata["tool"]["uv"]["index"]
    assert len(indexes) == 1
    assert indexes[0]["url"] == "https://pypi.org/simple" and indexes[0]["default"]


@pytest.mark.parametrize("host,folder,suffix", [("claude", "agents", ".md"),
                                                ("copilot", "com.github.copilot/agents", ".agent.md")])
def test_static_plugin_agents_have_explicit_tools(host, folder, suffix):
    directory = PLUGIN_ROOT / folder
    assert sorted(path.name for path in directory.glob(f"*{suffix}")) == \
        sorted(f"{role}{suffix}" for role in ROLES)
    for role in ROLES:
        path = directory / f"{role}{suffix}"
        text = path.read_text(encoding="utf-8")
        front = text.split("---\n", 2)[1]
        assert re.search(rf"^name: {role}$", front, re.M), path
        assert re.search(r"^description: .+", front, re.M), path
        assert re.search(r"^tools: .+", front, re.M), path
        assert agent_pin(path, host)[0], path
        assert "{{" not in text, path
        assert "skill:" in text and "changes:" in text and "--changes-dir" in text, path
        assert "every `$CHANTIER` call" in text, path
        assert "${CLAUDE_PLUGIN_ROOT}" not in text, path
        if host == "copilot":
            assert re.search(r"^strict-tools-list: true$", front, re.M), path
            assert re.search(r"^model-policy: required$", front, re.M), path


def test_every_role_has_a_card():
    for role in ROLES:
        assert (SKILL / "references" / "roles" / f"{role}.md").exists(), role


def test_behavior_eval_seed_is_available():
    assert (SKILL / "evals" / "lib" / "seed.py").is_file()


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
    code, _, err = chantier("file", "Fix login")
    assert code == 0, err
    folder = repo / ".agents/changes/backlog/1-inbox/fix-login"
    (folder / "03-change-spec.md").write_text("# Fix login\n\nFix the login.\n")
    code, _, err = chantier("open", "b1", f"@{folder}", "--slots", 1, "--no-worktrees",
                             "--fast-gate", "just check", "--long-gate", "just check",
                             "--default-branch", "main")
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


def test_agents_md_can_select_different_agents_for_each_host(repo, chantier, monkeypatch):
    copilot = repo / ".github/agents/my-coder.agent.md"
    claude = repo / ".claude/agents/rust-coder.md"
    for path in (copilot, claude):
        path.parent.mkdir(parents=True)
    copilot.write_text("---\nname: copilot-coder\n---\nCode.\n")
    claude.write_text("---\nname: rust-coder\n---\nCode.\n")
    (repo / "AGENTS.md").write_text(
        "- chantier copilot coder agent: .github/agents/my-coder.agent.md\n"
        "- chantier claude coder agent: .claude/agents/rust-coder.md\n")
    monkeypatch.setenv("CHANTIER_HOST", "copilot")
    assert "agent: my-coder (from AGENTS.md" in chantier("models", "get", "coder")[1][-1]
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    assert "agent: rust-coder (from AGENTS.md" in chantier("models", "get", "coder")[1][-1]
    (repo / "AGENTS.md").write_text(
        "- chantier claude coder agent: .github/agents/my-coder.agent.md\n")
    code, _, err = chantier("models", "get", "coder")
    assert code == 2 and "a claude agent must be a file in .claude/agents" in err


def test_repository_agent_copy_is_not_regenerated(repo, chantier, monkeypatch):
    monkeypatch.setenv("CHANTIER_HOST", "copilot")
    monkeypatch.setenv("COPILOT_AGENT_SESSION_ID", "s-1")
    agent = repo / ".github/agents/coder.agent.md"
    agent.parent.mkdir(parents=True)
    text = (PLUGIN_ROOT / "com.github.copilot/agents/coder.agent.md").read_text()
    text = text.replace('"search"]', '"search", "my_tool"]')
    agent.write_text(text)
    assert chantier("preflight")[0] == 0
    assert "repository copy" in chantier("models", "get", "coder")[1][-1]
    assert agent.read_text() == text


def test_legacy_configuration_is_not_read(repo, chantier, monkeypatch, tmp_path):
    monkeypatch.setenv("CHANTIER_HOST", "copilot")
    monkeypatch.setenv("COPILOT_AGENT_SESSION_ID", "s-1")
    (repo / ".agents").mkdir()
    (repo / ".agents/chantier.json").write_text("not JSON")
    (repo / ".agents/chantier.models.yml").write_text("not YAML")
    user_models = tmp_path / "models.yml"
    user_models.write_text("not YAML")
    monkeypatch.setenv("CHANTIER_MODELS_USER", str(user_models))
    assert chantier("preflight")[0] == 0
    assert chantier("models", "check")[0] == 0

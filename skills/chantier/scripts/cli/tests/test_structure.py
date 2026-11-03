"""The plugin's structure: versions, manifests, agents, references, and a smoke run in a fresh
repository. The batch workflow itself is the scenario's job (`just scenario`).
"""
import importlib.util
import json
import re
import tomllib

import pytest

from chantier import __version__
from chantier.commands import CARDS
from chantier.roles import DRIVERS, ROLES, plugin_agent_file
from conftest import PLUGIN_ROOT, SKILL, sh

CLAUDE_MODELS = {"claude-sonnet-5-5"}


def _version_script():
    spec = importlib.util.spec_from_file_location("version", PLUGIN_ROOT / "scripts" / "version.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _front(path):
    _, front, body = path.read_text(encoding="utf-8").split("---\n", 2)
    return dict(line.split(": ", 1) for line in front.splitlines() if ": " in line), body


def _prepared(repo, chantier, title="Fix login"):
    _, out, _ = chantier("file", title)
    folder = repo / out[0].removeprefix("filed ").split(";")[0]
    (folder / "03-change-spec.md").write_text(f"# {title}\n\nDo it.\n")
    return folder


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


@pytest.mark.parametrize("host", ["claude", "copilot"])
def test_each_host_ships_one_agent_per_role_and_nothing_else(host):
    folder = plugin_agent_file(PLUGIN_ROOT, "coder", host).parent
    assert sorted(p.name for p in folder.iterdir()) == \
        sorted(plugin_agent_file(PLUGIN_ROOT, r, host).name for r in ROLES)


@pytest.mark.parametrize("role", ROLES)
def test_both_hosts_give_a_role_the_same_body_and_their_own_frontmatter(role):
    claude, claude_body = _front(plugin_agent_file(PLUGIN_ROOT, role, "claude"))
    copilot, copilot_body = _front(plugin_agent_file(PLUGIN_ROOT, role, "copilot"))
    assert claude_body == copilot_body and f"`chantier {role}`" in claude_body
    assert claude["name"] == role and copilot["name"] == f"chantier-{role}"
    assert claude["description"] == copilot["description"]
    assert claude["model"] in CLAUDE_MODELS
    assert copilot["model-policy"] == "required" and copilot["user-invocable"] == "false"
    assert copilot["strict-tools-list"] == "true"
    assert ("Agent" in claude["tools"]) == ('"agent"' in copilot["tools"]) \
        == (role in ("cr-driver", "stack-driver"))
    assert (claude.get("background") == "true") == (role in DRIVERS)


def test_skill_and_references_links_resolve():
    for page in [SKILL / "SKILL.md", *(SKILL / "references").glob("*.md")]:
        for link in re.findall(r"\]\(([^)#\s]+)", page.read_text(encoding="utf-8")):
            if not link.startswith("http"):
                assert (page.parent / link).exists(), f"{page.name}: {link}"


def test_every_card_section_a_spawn_names_exists():
    for card, section in [*CARDS.values(), ("worker", "Extra review step")]:
        text = (SKILL / "references" / f"{card}.md").read_text(encoding="utf-8")
        assert f"\n## {section}\n" in text, (card, section)


GATES = ("--fast-gate", "just check", "--long-gate", "just check", "--default-branch", "main")


@pytest.mark.parametrize("host,coder", [("claude", "chantier:coder"), ("copilot", "chantier-coder")])
def test_the_plugin_runs_with_no_setup_and_writes_only_in_agents_changes(
        repo, chantier, monkeypatch, host, coder):
    monkeypatch.setenv("CHANTIER_HOST", host)
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    monkeypatch.setenv("COPILOT_AGENT_SESSION_ID", "s-1")
    code, out, _ = chantier("preflight")
    assert code == 0, out
    assert sh("git", "status", "--porcelain", cwd=repo) == ""
    folder = _prepared(repo, chantier)
    code, _, err = chantier("open", "b1", f"@{folder}", "--no-worktrees", *GATES)
    assert code == 0, err
    assert chantier("status")[1][-1].startswith("CR-101 queued")
    _, out, _ = chantier("spawn", "coder", "CR-101", "--note", "round 1")
    assert out[:2] == [f"agent: {coder}", "mode: foreground"]
    assert any('references/worker.md (section "Coder")' in line for line in out)
    assert sh("git", "status", "--porcelain", "-uall", cwd=repo).splitlines() and all(
        line.startswith("?? .agents/changes/")
        for line in sh("git", "status", "--porcelain", "-uall", cwd=repo).splitlines())


def test_a_role_runs_the_users_agent_and_a_review_step_runs_after_the_inspector(
        repo, chantier, monkeypatch):
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    (repo / ".claude" / "agents").mkdir(parents=True)
    (repo / ".claude" / "agents" / "my-debugger.md").write_text("---\nname: my-debugger\n---\nDebug.\n")
    (repo / ".claude" / "agents" / "sec.md").write_text("---\nname: sec\n---\nReview.\n")
    folder = _prepared(repo, chantier)
    for bad in (("--agent", "nobody=x"), ("--review", "coder=sec:y"), ("--review", "sec-review=sec"),
                ("--agent", "debugger=missing")):
        assert chantier("open", "bad", f"@{folder}", "--no-worktrees", *GATES, *bad)[0] == 1, bad
    code, _, err = chantier("open", "b1", f"@{folder}", "--no-worktrees", *GATES,
                            "--agent", "debugger=my-debugger",
                            "--review", "security-review=sec:OWASP top 10")
    assert code == 0, err
    _, out, _ = chantier("spawn", "debugger", "CR-101")
    assert out[0] == "agent: my-debugger" and any('(section "Debugger")' in ln for ln in out)
    _, out, _ = chantier("spawn", "security-review", "CR-101")
    assert out[0] == "agent: sec" and "Your review: OWASP top 10" in out
    _, out, _ = chantier("spawn", "cr-driver", "CR-101")
    assert out[1] == "mode: background"
    assert any(ln.startswith("Extra review steps") and "security-review" in ln for ln in out)

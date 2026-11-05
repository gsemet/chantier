"""The plugin's structure: versions, manifests, agents, references, and a smoke run in a fresh
repository. The batch workflow itself is the scenario's job (`just scenario`).
"""
import importlib.util
import json
import re
import tomllib

import pytest

from chantier import __version__
from conftest import PLUGIN_ROOT, SKILL, sh

CLAUDE_MODELS = {"claude-sonnet-5-5", "claude-opus-5-5"}
DRIVERS = ("cr-driver", "stack-driver", "qa-driver", "release-driver")
WORKERS = ("investigator", "coder", "inspector", "debugger", "verifier", "conflict-resolver")
ROLES = DRIVERS + WORKERS
OPUS_ROLES = {"cr-driver", "stack-driver", "release-driver"}  # judgement; the rest is work
CARDS = {**{r: "driver" for r in DRIVERS}, **{r: "worker" for r in WORKERS}}


def agent_file(role, host):
    """The plugin installs one agent per role and host: `chantier:<role>` on Claude from
    `agents/`, `chantier-<role>` on Copilot from `com.github.copilot/agents/`."""
    if host == "claude":
        return PLUGIN_ROOT / "agents" / f"{role}.md"
    return PLUGIN_ROOT / "com.github.copilot" / "agents" / f"chantier-{role}.agent.md"


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
    agent_plugin = json.loads((PLUGIN_ROOT / ".github" / "plugin" / "plugin.json").read_text(encoding="utf-8"))
    claude = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    markets = [json.loads((PLUGIN_ROOT / p / "marketplace.json").read_text(encoding="utf-8"))
               for p in (".claude-plugin", ".github/plugin")]
    assert {agent_plugin["name"], claude["name"]} | {m["plugins"][0]["name"] for m in markets} \
        == {"chantier"}
    for skill in agent_plugin["skills"]:
        assert (PLUGIN_ROOT / skill / "SKILL.md").exists()
    for folder in agent_plugin["agents"]:
        assert agent_file("coder", "copilot").parent == (PLUGIN_ROOT / folder).resolve()


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
    folder = agent_file("coder", host).parent
    assert sorted(p.name for p in folder.iterdir()) == \
        sorted(agent_file(r, host).name for r in ROLES)


@pytest.mark.parametrize("role", ROLES)
def test_both_hosts_give_a_role_the_same_body_and_their_own_frontmatter(role):
    for host in ("claude", "copilot"):  # a BOM hides the frontmatter from a host
        assert not agent_file(role, host).read_bytes().startswith(b"\xef\xbb\xbf")
    claude, claude_body = _front(agent_file(role, "claude"))
    copilot, copilot_body = _front(agent_file(role, "copilot"))
    assert claude_body == copilot_body and f"`chantier {role}`" in claude_body
    assert claude["name"] == role and copilot["name"] == f"chantier-{role}"
    assert claude["description"] == copilot["description"]
    assert claude["model"] in CLAUDE_MODELS
    assert (claude["model"] == "claude-opus-5-5") == (role in OPUS_ROLES)
    assert ("Opus" in copilot["model"]) == (role in OPUS_ROLES)
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


def test_every_role_has_its_section_in_its_card():
    """The contract a parent names in its prompt: `<card>.md`, section `<Role>`."""
    for role, card in CARDS.items():
        text = (SKILL / "references" / f"{card}.md").read_text(encoding="utf-8")
        section = role.replace("-", " ").capitalize().replace("Cr ", "CR ").replace("Qa ", "QA ")
        assert f"\n## {section}\n" in text, (role, section)


FROM_AGENTS_MD = ("--default-branch", "main")  # what the Chief of Staff read in the project's rules


@pytest.mark.parametrize("host", ["claude", "copilot"])
def test_the_plugin_runs_with_no_setup_and_writes_only_in_agents_changes(
        repo, chantier, monkeypatch, host):
    monkeypatch.setenv("CHANTIER_HOST", host)
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    monkeypatch.setenv("COPILOT_AGENT_SESSION_ID", "s-1")
    code, out, _ = chantier("preflight")
    assert code == 0, out
    assert sh("git", "status", "--porcelain", cwd=repo) == ""
    folder = _prepared(repo, chantier)
    code, _, err = chantier("open", "b1", f"@{folder}", *FROM_AGENTS_MD)
    assert code == 0, err
    assert chantier("status")[1][-1].startswith("CR-101 queued")
    # the CLI names the branch and the worktree; the Driver creates them
    assert not (repo.parent / f"{repo.name}.worktrees").exists()
    assert sh("git", "branch", "--list", "chantier/*", cwd=repo) == ""
    assert chantier("gate", "CR-101", "true")[0] == 2
    code, out, _ = chantier("take", "CR-101")
    assert code == 0 and out[0].startswith("took CR-101")
    assert any(ln.startswith("cards: ") and "references/" in ln for ln in out)
    assert any(ln.startswith("worktree: ") and "not created yet" in ln for ln in out)
    _, out, _ = chantier("round", "CR-101", "--note", "round 1")
    assert out[0] == "round 1 of 3 for CR-101"
    assert chantier("status")[1][-1].startswith("CR-101 working r1/3")
    for _ in range(2):
        chantier("round", "CR-101")
    assert chantier("round", "CR-101")[0] == 5  # the round limit is a rail
    assert chantier("order", "rounds", "CR-101", "--note", "4")[0] == 0
    assert chantier("round", "CR-101")[0] == 0
    _, out, _ = chantier("rules", "--batch", "b1")  # every prompt passes --batch
    assert out[0].startswith(str(repo / "AGENTS.md").replace("\\", "/"))
    assert sh("git", "status", "--porcelain", "-uall", cwd=repo).splitlines() and all(
        line.startswith("?? .agents/changes/")
        for line in sh("git", "status", "--porcelain", "-uall", cwd=repo).splitlines())

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
WORKERS = ("investigator", "coder", "inspector", "debugger", "verifier", "conflict-resolver",
           "demo-explorer")
CHIEF_ROLES = ("spec-writer",)  # started by the Chief of Staff; its card is its own file
ROLES = DRIVERS + WORKERS + CHIEF_ROLES
OPUS_ROLES = {"stack-driver", "release-driver", "spec-writer"}  # judgement; the rest is work
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


def test_the_board_mod_is_wired_on_claude_only():
    claude = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    hooks = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    assert hooks["modules"]
    for module in hooks["modules"]:
        assert (PLUGIN_ROOT / "hooks" / module).is_file(), module
    if "types" in claude:
        assert (PLUGIN_ROOT / claude["types"]).is_file()
    copilot = json.loads((PLUGIN_ROOT / ".github" / "plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert "/schemas/1.0.0/" in copilot["$schema"]
    assert "hooks" not in copilot and "types" not in copilot


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
    for role in CHIEF_ROLES:
        assert (SKILL / "references" / f"{role}.md").is_file(), role
    for role, card in CARDS.items():
        text = (SKILL / "references" / f"{card}.md").read_text(encoding="utf-8")
        section = role.replace("-", " ").capitalize().replace("Cr ", "CR ").replace("Qa ", "QA ")
        assert f"\n## {section}\n" in text, (role, section)


HOST_TOOLS = ("SendMessage", "send_message", "write_agent", "TaskStop", "ScheduleWakeup",
              "start_session", "create_session", "get_session", "/every", "/loop", "/compact",
              "/autocompact", "CLAUDE_CODE_SESSION_ID", "COPILOT_AGENT_SESSION_ID")


def test_each_host_has_its_reference_and_the_cards_hold_no_host_tool():
    hosts = SKILL / "references" / "hosts"
    for name in ("claude-code.md", "copilot.md"):
        assert (hosts / name).is_file(), name
    for card in ("chief-of-staff", "foreman", "driver", "worker", "concepts"):
        text = (SKILL / "references" / f"{card}.md").read_text(encoding="utf-8")
        body = "\n".join(ln for ln in text.splitlines() if "hosts/" not in ln)
        assert [t for t in HOST_TOOLS if t in body] == [], card


FROM_AGENTS_MD =("--default-branch", "main")  # what the Chief of Staff read in the project's rules


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
    code, _, err = chantier("open", str(folder), *FROM_AGENTS_MD)
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
    _, out, _ = chantier("rules", "--batch", "1")  # every prompt passes --batch
    assert out[0].startswith(str(repo / "AGENTS.md").replace("\\", "/"))
    assert sh("git", "status", "--porcelain", "-uall", cwd=repo).splitlines() and all(
        line.startswith("?? .agents/changes/")
        for line in sh("git", "status", "--porcelain", "-uall", cwd=repo).splitlines())


def test_a_direct_batch_is_recorded_shown_and_strict(repo, chantier, monkeypatch):
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "uuid-chief")
    first, second = _prepared(repo, chantier), _prepared(repo, chantier, "Fix logout")
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    code, _, err = chantier("open", str(first), "--direct", *FROM_AGENTS_MD)
    assert code == 2 and "session id" in err  # nothing could tell a Foreman's claim from its own
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "uuid-chief")
    code, out, err = chantier("open", str(first), "--direct", *FROM_AGENTS_MD)
    assert code == 0, err
    assert out[1].endswith("then steer it yourself")
    batch = next((repo / ".agents" / "changes").glob("**/batch.json"))
    assert json.loads(batch.read_text(encoding="utf-8"))["steering"] == "direct"
    assert "Steering: direct" in (batch.parent / "brief.md").read_text(encoding="utf-8")
    assert " steering direct " in chantier("status")[1][0]
    assert "steering direct" in (batch.parent / "STATUS.md").read_text(encoding="utf-8")
    for kind, note in (("add", str(second)), ("qa", "test it")):
        code, _, err = chantier("order", kind, "--note", note)
        assert code == 2 and "a running direct batch is strict" in err
    code, out, err = chantier("order", "add", "--release", "--note", str(second))
    assert code == 0, err  # the release exception
    assert chantier("order", "note", "CR-101", "--note", "hello")[0] == 0  # the rest still works


def test_a_foreman_batch_takes_added_work_and_a_direct_preflight_leaves_out_p2(
        repo, chantier, monkeypatch):
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    code, out, _ = chantier("preflight")
    assert code == 2 and any(ln.startswith("P1 FAIL") for ln in out)
    code, out, _ = chantier("preflight", "--direct")
    assert code == 0, out
    assert any(ln.startswith("P1 ok") for ln in out)
    assert any(ln.startswith("P3, P9 and") for ln in out) and not any("P2" in ln for ln in out)
    chantier("open", str(_prepared(repo, chantier)), *FROM_AGENTS_MD)
    assert chantier("order", "qa", "--note", "test it")[0] == 0


def test_init_creates_the_five_folders_once_and_refuses_outside_a_main_checkout(
        repo, chantier, tmp_path, monkeypatch):
    code, out, _ = chantier("init")
    assert code == 0 and [ln.split()[0] for ln in out] == ["created"] * 5
    changes = repo / ".agents" / "changes"
    assert sorted(p.name for p in changes.iterdir()) == [
        "1-inbox", "2-backlog", "3-requests", "4-archives", "5-trash"]
    assert not list(changes.rglob("*.*"))  # empty, no .gitkeep
    assert [ln.split()[0] for ln in chantier("init")[1]] == ["exists"] * 5
    sh("git", "worktree", "add", "--quiet", str(tmp_path / "wt"), "-b", "side", cwd=repo)
    monkeypatch.chdir(tmp_path / "wt")
    code, _, err = chantier("init")
    assert code == 2 and "main checkout" in err
    monkeypatch.chdir(tmp_path.parent)
    code, _, err = chantier("init")
    assert code == 2 and "git" in err

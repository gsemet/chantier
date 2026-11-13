"""The plugin's files: versions, manifests, agents, the model table, references and hosts."""

import json
import re
import subprocess
import tomllib
from pathlib import Path
from types import ModuleType

import pytest
from conftest import PLUGIN_ROOT, SKILL, load_script

from chantier import __version__
from chantier.playbook.models import MODELS, normalise, resolve

CLAUDE_MODELS = {"claude-sonnet-5-5", "claude-opus-5-5"}


DRIVERS = ("cr-driver", "stack-driver", "qa-driver", "release-driver")


WORKERS = (
    "investigator",
    "coder",
    "inspector",
    "debugger",
    "verifier",
    "conflict-resolver",
    "demo-explorer",
)


CHIEF_ROLES = ("spec-writer",)  # started by the Chief of Staff; its card is its own file


ROLES = DRIVERS + WORKERS + CHIEF_ROLES


CLAUDE_OPUS_ROLES = {"spec-writer"}  # Sonnet by default; escalation starts Opus at need


COPILOT_OPUS_ROLES = {"stack-driver", "release-driver", "spec-writer"}  # Copilot is untouched


CARDS = {**{r: "driver" for r in DRIVERS}, **{r: "worker" for r in WORKERS}}


def agent_file(role: str, host: str) -> Path:
    """The plugin installs one agent per role and host: `chantier:<role>` on Claude from
    `agents/`, `chantier-<role>` on Copilot from `com.github.copilot/agents/`."""
    if host == "claude":
        return PLUGIN_ROOT / "agents" / f"{role}.md"
    return PLUGIN_ROOT / "com.github.copilot" / "agents" / f"chantier-{role}.agent.md"


def _version_script() -> ModuleType:
    return load_script("version", PLUGIN_ROOT / "scripts" / "version.py")


def _front(path: Path) -> tuple[dict[str, str], str]:
    _, front, body = path.read_text(encoding="utf-8").split("---\n", 2)
    return dict(line.split(": ", 1) for line in front.splitlines() if ": " in line), body


HOST_TOOLS = (
    "SendMessage",
    "send_message",
    "write_agent",
    "TaskStop",
    "ScheduleWakeup",
    "start_session",
    "create_session",
    "get_session",
    "/every",
    "/loop",
    "/compact",
    "/autocompact",
    "CLAUDE_CODE_SESSION_ID",
    "COPILOT_AGENT_SESSION_ID",
)


def test_release_scan_catches_a_uuid_after_an_underscore() -> None:
    module = load_script("release_notes", PLUGIN_ROOT / "scripts" / "release_notes.py")
    hits = module.scan_text("see local_00000000-1111-2222-3333-444444444444", "f", module.FIXED)
    assert any(h.endswith("uuid") for h in hits)


def test_every_file_carries_the_same_version() -> None:
    version = _version_script()
    for path, pattern, count in version.TARGETS:
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        found = [m.group(1) for m in re.finditer(pattern, text, re.M)]
        assert found == [__version__] * count, path


def test_manifests_agree() -> None:
    agent_plugin = json.loads(
        (PLUGIN_ROOT / ".github" / "plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    claude = json.loads(
        (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    markets = [
        json.loads((PLUGIN_ROOT / p / "marketplace.json").read_text(encoding="utf-8"))
        for p in (".claude-plugin", ".github/plugin")
    ]
    assert {agent_plugin["name"], claude["name"]} | {m["plugins"][0]["name"] for m in markets} == {
        "chantier"
    }
    for skill in agent_plugin["skills"]:
        assert (PLUGIN_ROOT / skill / "SKILL.md").exists()
    for folder in agent_plugin["agents"]:
        assert agent_file("coder", "copilot").parent == (PLUGIN_ROOT / folder).resolve()


def test_the_board_mod_is_wired_on_claude_only() -> None:
    claude = json.loads(
        (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    hooks = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    assert hooks["modules"]
    for module in hooks["modules"]:
        assert (PLUGIN_ROOT / "hooks" / module).is_file(), module
    if "types" in claude:
        assert (PLUGIN_ROOT / claude["types"]).is_file()
    copilot = json.loads(
        (PLUGIN_ROOT / ".github" / "plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert "/schemas/1.0.0/" in copilot["$schema"]
    assert "hooks" not in copilot and "types" not in copilot


def test_copilot_cost_helper_declares_pypi() -> None:
    text = (SKILL / "scripts" / "cli" / "session_usage.py").read_text(encoding="utf-8")
    block = re.search(r"(?m)^# /// script\n((?:#.*\n)*?)# ///$", text.replace("\r\n", "\n"))
    assert block is not None
    metadata = tomllib.loads(
        "\n".join(line[2:] if line.startswith("# ") else line[1:] for line in block[1].splitlines())
    )
    assert "copilot-session-usage>=1" in metadata["dependencies"]
    indexes = metadata["tool"]["uv"]["index"]
    assert len(indexes) == 1
    assert indexes[0]["url"] == "https://pypi.org/simple" and indexes[0]["default"]


def test_no_tracked_file_starts_with_a_utf8_byte_order_mark() -> None:
    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=PLUGIN_ROOT, capture_output=True, check=True
    )
    marked = []
    for name in listed.stdout.decode("utf-8").split("\0"):
        path = PLUGIN_ROOT / name
        if name and path.is_file():  # a tracked path deleted from the working tree has no bytes
            with path.open("rb") as handle:
                if handle.read(3) == b"\xef\xbb\xbf":
                    marked.append(name)
    assert not marked, (
        "files with a UTF-8 byte-order mark (write them as UTF-8 without one): " + ", ".join(marked)
    )


@pytest.mark.parametrize("host", ["claude", "copilot"])
def test_each_host_ships_one_agent_per_role_and_nothing_else(host: str) -> None:
    folder = agent_file("coder", host).parent
    assert sorted(p.name for p in folder.iterdir()) == sorted(
        agent_file(r, host).name for r in ROLES
    )


@pytest.mark.parametrize("role", ROLES)
def test_both_hosts_give_a_role_the_same_body_and_their_own_frontmatter(role: str) -> None:
    for host in ("claude", "copilot"):  # a BOM hides the frontmatter from a host
        assert not agent_file(role, host).read_bytes().startswith(b"\xef\xbb\xbf")
    claude, claude_body = _front(agent_file(role, "claude"))
    copilot, copilot_body = _front(agent_file(role, "copilot"))
    assert claude_body == copilot_body and f"`chantier {role}`" in claude_body
    assert claude["name"] == role and copilot["name"] == f"chantier-{role}"
    assert claude["description"] == copilot["description"]
    # the description ends with the first line the prompt must start with; the refusal names it
    # and says a new start is needed; a later message gets the same answer
    described = claude["description"].strip("'").replace("''", "'")
    assert described.endswith("`") and f" Prompt starts with: `chantier {role} for " in described
    first = described.rsplit("Prompt starts with: `", 1)[1][:-1]
    assert f"My prompt must start with `{first}`" in claude_body
    assert "a message to me gets this same answer: start a new agent with that line" in claude_body
    assert "Any later message gets the same answer." in claude_body
    assert claude["model"] in CLAUDE_MODELS
    assert (claude["model"] == "claude-opus-5-5") == (role in CLAUDE_OPUS_ROLES)
    assert ("Opus" in copilot["model"]) == (role in COPILOT_OPUS_ROLES)
    assert copilot["model-policy"] == "required" and copilot["user-invocable"] == "false"
    assert copilot["strict-tools-list"] == "true"
    assert (
        ("Agent" in claude["tools"])
        == ('"agent"' in copilot["tools"])
        == (role in ("cr-driver", "stack-driver"))
    )
    assert (claude.get("background") == "true") == (role in DRIVERS)


@pytest.mark.parametrize("host", ["claude", "copilot"])
def test_the_model_table_names_every_model_the_agent_files_name(host: str) -> None:
    for role in ROLES:
        front, _ = _front(agent_file(role, host))
        # Copilot writes `[Display name, id]`; Claude the id alone
        named = front["model"].strip("[]").split(", ")[-1]
        found, why = resolve(host, named)
        assert why is None and found is not None and found.id == named, (role, named, why)


def test_the_model_table_names_no_model_twice_per_host() -> None:
    for host, models in MODELS.items():
        ids = [normalise(m.id) for m in models]
        assert len(set(ids)) == len(ids), host
        names = [normalise(m.name) for m in models]
        assert len(set(names)) == len(names), host


def test_skill_and_references_links_resolve() -> None:
    for page in [
        *(PLUGIN_ROOT / "skills").glob("*/SKILL.md"),
        *(SKILL / "references").glob("*.md"),
        PLUGIN_ROOT / "README.md",
        *(PLUGIN_ROOT / "docs").glob("*.md"),
    ]:
        for link in re.findall(r"\]\(([^)#\s]+)", page.read_text(encoding="utf-8")):
            if not link.startswith("http"):
                assert (page.parent / link).exists(), f"{page.name}: {link}"


def test_four_skills_the_router_and_three_thin_ones_listed_by_copilot() -> None:
    names = ("chantier", "chief-of-staff", "griller", "status")
    for name in names:
        front, _ = _front(PLUGIN_ROOT / "skills" / name / "SKILL.md")
        assert front["name"] == name
    for name in names[1:]:
        text = (PLUGIN_ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert "../chantier/references/" in text and "../chantier/scripts/cli/" in text
    copilot = json.loads(
        (PLUGIN_ROOT / ".github" / "plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert copilot["skills"] == [f"./skills/{n}" for n in names]


def test_every_role_has_its_section_in_its_card() -> None:
    """The contract a parent names in its prompt: `<card>.md`, section `<Role>`."""
    for role in CHIEF_ROLES:
        assert (SKILL / "references" / f"{role}.md").is_file(), role
    for role, card in CARDS.items():
        text = (SKILL / "references" / f"{card}.md").read_text(encoding="utf-8")
        section = role.replace("-", " ").capitalize().replace("Cr ", "CR ").replace("Qa ", "QA ")
        assert f"\n## {section}\n" in text, (role, section)


def test_each_host_has_its_reference_and_the_cards_hold_no_host_tool() -> None:
    hosts = SKILL / "references" / "hosts"
    for name in ("claude-code.md", "copilot.md"):
        assert (hosts / name).is_file(), name
    for card in (
        "chief-of-staff",
        "foreman",
        "driver",
        "worker",
        "concepts",
        "griller",
        "session-start",
        "status-layout",
    ):
        text = (SKILL / "references" / f"{card}.md").read_text(encoding="utf-8")
        body = "\n".join(ln for ln in text.splitlines() if "hosts/" not in ln)
        assert [t for t in HOST_TOOLS if t in body] == [], card

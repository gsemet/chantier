"""The plugin's structure: versions, manifests, agents, references, and a smoke run in a fresh
repository. The batch workflow itself is the scenario's job (`just scenario`).
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
import tomllib

import pytest

from chantier import __version__
from chantier.commands import RECOMMENDED_ALLOW
from conftest import PLUGIN_ROOT, SKILL, sh

CLAUDE_MODELS = {"claude-sonnet-5-5", "claude-opus-5-5"}
DRIVERS = ("cr-driver", "stack-driver", "qa-driver", "release-driver")
WORKERS = ("investigator", "coder", "inspector", "debugger", "verifier", "conflict-resolver",
           "demo-explorer")
CHIEF_ROLES = ("spec-writer",)  # started by the Chief of Staff; its card is its own file
ROLES = DRIVERS + WORKERS + CHIEF_ROLES
CLAUDE_OPUS_ROLES = {"spec-writer"}  # Sonnet by default; escalation starts Opus at need
COPILOT_OPUS_ROLES = {"stack-driver", "release-driver", "spec-writer"}  # Copilot is untouched
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


def test_release_scan_catches_a_uuid_after_an_underscore():
    spec = importlib.util.spec_from_file_location("release_notes", PLUGIN_ROOT / "scripts" / "release_notes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    hits = module.scan_text("see local_00000000-1111-2222-3333-444444444444", "f", module.FIXED)
    assert any(h.endswith("uuid") for h in hits)


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
    assert (claude["model"] == "claude-opus-5-5") == (role in CLAUDE_OPUS_ROLES)
    assert ("Opus" in copilot["model"]) == (role in COPILOT_OPUS_ROLES)
    assert copilot["model-policy"] == "required" and copilot["user-invocable"] == "false"
    assert copilot["strict-tools-list"] == "true"
    assert ("Agent" in claude["tools"]) == ('"agent"' in copilot["tools"]) \
        == (role in ("cr-driver", "stack-driver"))
    assert (claude.get("background") == "true") == (role in DRIVERS)


@pytest.mark.parametrize("host", ["claude", "copilot"])
def test_the_model_table_names_every_model_the_agent_files_name(host):
    from chantier.playbook import resolve
    for role in ROLES:
        front, _ = _front(agent_file(role, host))
        # Copilot writes `[Display name, id]`; Claude the id alone
        named = front["model"].strip("[]").split(", ")[-1]
        found, why = resolve(host, named)
        assert why is None and found.id == named, (role, named, why)


def test_the_model_table_names_no_model_twice_per_host():
    from chantier.playbook import MODELS, normalise
    for host, models in MODELS.items():
        ids = [normalise(m.id) for m in models]
        assert len(set(ids)) == len(ids), host
        names = [normalise(m.name) for m in models]
        assert len(set(names)) == len(names), host


def test_skill_and_references_links_resolve():
    for page in [*(PLUGIN_ROOT / "skills").glob("*/SKILL.md"), *(SKILL / "references").glob("*.md"),
                 PLUGIN_ROOT / "README.md", *(PLUGIN_ROOT / "docs").glob("*.md")]:
        for link in re.findall(r"\]\(([^)#\s]+)", page.read_text(encoding="utf-8")):
            if not link.startswith("http"):
                assert (page.parent / link).exists(), f"{page.name}: {link}"


def test_four_skills_the_router_and_three_thin_ones_listed_by_copilot():
    names = ("chantier", "chief-of-staff", "griller", "status")
    for name in names:
        front, _ = _front(PLUGIN_ROOT / "skills" / name / "SKILL.md")
        assert front["name"] == name
    for name in names[1:]:
        text = (PLUGIN_ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert "../chantier/references/" in text and "../chantier/scripts/cli/" in text
    copilot = json.loads((PLUGIN_ROOT / ".github" / "plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert copilot["skills"] == [f"./skills/{n}" for n in names]


def test_the_seat_is_one_file_held_until_taken_over_on_purpose(repo, chantier, monkeypatch):
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    changes = repo / ".agents" / "changes"
    assert chantier("seat")[1] == ["seat none"]
    code, out, _ = chantier("seat", "take", "s-1", "--env", "Mac", "--title", "[Mac] Proj [Chief of Staff]",
                            "--link", "claude://s-1")
    assert (code, out) == (0, ["seat s-1"])
    assert sorted(p.name for p in changes.iterdir() if not p.name.startswith(".")) == ["seat.json"]
    seat = json.loads((changes / "seat.json").read_text(encoding="utf-8"))
    assert seat["session"] == "s-1" and seat["link"] == "claude://s-1"
    assert set(seat) == {"session", "transcript", "env", "title", "link"}  # no date
    assert chantier("seat")[1][0] == 'seat s-1 env Mac title "[Mac] Proj [Chief of Staff]" link claude://s-1'
    assert chantier("seat", "take", "s-1", "--title", "again")[0] == 0  # the same session
    code, _, err = chantier("seat", "take", "s-2")
    assert code == 2 and "held by s-1" in err and "--over s-1" in err
    assert chantier("seat", "take", "s-2", "--over", "s-3")[0] == 2
    assert chantier("seat", "leave", "s-2")[0] == 2
    assert chantier("seat", "take", "s-2", "--over", "s-1")[1] == ["seat s-2"]
    assert chantier("seat", "leave", "s-2")[1] == ["seat none"]
    assert chantier("seat", "leave", "s-2")[1] == ["seat none"]


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
    for card in ("chief-of-staff", "foreman", "driver", "worker", "concepts", "griller",
                 "session-start", "status-layout"):
        text = (SKILL / "references" / f"{card}.md").read_text(encoding="utf-8")
        body = "\n".join(ln for ln in text.splitlines() if "hosts/" not in ln)
        assert [t for t in HOST_TOOLS if t in body] == [], card


FROM_AGENTS_MD =("--default-branch", "main")  # what the Chief of Staff read in the project's rules


@pytest.mark.parametrize("host", ["claude", "copilot"])
def test_the_plugin_runs_with_no_setup_and_writes_only_in_the_planning_folder(
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


def test_an_external_surface_gets_the_planning_folder_and_the_project_stays_clean(
        repo, chantier, monkeypatch, tmp_path):
    surface = tmp_path / "surface"
    project = surface / "projects" / "demo"
    project.mkdir(parents=True)
    (project / "checkout.yml").write_text(
        f"# the clone\nrepo: {Path(os.path.relpath(repo, project)).as_posix()}\n"
        "worktrees: ../../../wt\n")
    sh("git", "init", "--quiet", "-b", "main", str(surface))
    sh("git", "add", ".", cwd=surface)
    sh("git", "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "--quiet",
       "-m", "init", cwd=surface)
    monkeypatch.chdir(surface)
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    assert chantier("preflight")[0] == 0
    folder = _prepared(surface, chantier)  # one project: taken without --project
    assert folder.relative_to(surface).as_posix().startswith("projects/demo/changes/1-inbox/")
    code, _, err = chantier("open", str(folder), *FROM_AGENTS_MD)
    assert code == 0, err
    code, out, _ = chantier("take", "CR-101")
    assert code == 0, out
    assert any(ln.startswith("cli: ") and f'--project "{project.resolve().as_posix()}"' in ln
               for ln in out)
    assert any(ln.startswith("clone: ") and repo.name in ln for ln in out)
    assert any(ln.startswith("worktree: ") and "/wt/batch-01-CR-101" in ln.replace("\\", "/") for ln in out)
    assert any(ln.startswith("archive: in the PR at .agents/changes/5-archives/") for ln in out)
    shown = sh("git", "status", "--porcelain", "-uall", cwd=surface).splitlines()
    assert shown and all(ln.startswith("?? projects/demo/changes/") for ln in shown)
    local = ("batch.json", "events.jsonl", "STATUS", ".lock", ".batch-number", "seat.json")
    assert not [ln for ln in shown if any(name in ln for name in local)], shown
    assert sh("git", "status", "--porcelain", "-uall", cwd=repo) == ""


def test_a_direct_batch_is_recorded_shown_and_queues_added_work(repo, chantier, monkeypatch):
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
    batch = repo / ".agents" / "changes" / "4-batch" / "batch.json"
    assert json.loads(batch.read_text(encoding="utf-8"))["steering"] == "direct"
    assert "Steering: direct" in (batch.parent / "brief.md").read_text(encoding="utf-8")
    assert " steering direct " in chantier("status")[1][0]
    assert "steered by the Chief of Staff (direct mode) · independent PRs (parallel)" in (
        batch.parent / "STATUS.md").read_text(encoding="utf-8")
    code, _, err = chantier("order", "qa", "--note", "test it")
    assert code == 2 and "a running direct batch takes no QA" in err
    code, out, err = chantier("order", "add", "--note", str(second))
    assert code == 0 and any("added CR-102, queued" in ln for ln in out), err  # taken at a free slot
    assert chantier("order", "note", "101", "--note", "hello")[0] == 0  # a bare number is a CR


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


def test_a_byte_order_mark_from_windows_powershell_is_read_through(repo, chantier, monkeypatch):
    """PowerShell 5.1's `Set-Content -Encoding utf8` and `Out-File` start a file with U+FEFF."""
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    folder = _prepared(repo, chantier)
    spec = folder / "03-change-spec.md"
    spec.write_bytes(b"\xef\xbb\xbf" + spec.read_bytes())
    assert chantier("open", str(folder), *FROM_AGENTS_MD)[0] == 0
    batch = repo / ".agents" / "changes" / "4-batch" / "batch.json"
    batch.write_bytes(b"\xef\xbb\xbf" + batch.read_bytes())
    code, out, err = chantier("status")
    assert code == 0 and out[-1].startswith("CR-101 queued"), err
    assert chantier("take", "CR-101")[0] == 0
    assert not batch.read_bytes().startswith(b"\xef\xbb\xbf")  # written back without the mark


def test_the_allow_rules_json_block_lists_exactly_what_preflight_checks():
    text = (SKILL / "references" / "hosts" / "claude-code.md").read_text(encoding="utf-8")
    section = text.split("### Allow rules\n", 1)[1]
    block = re.search(r"```json\n(.*?)\n```", section, re.S)[1]
    assert tuple(json.loads(block)["permissions"]["allow"]) == RECOMMENDED_ALLOW


def test_preflight_warns_on_missing_allow_rules_and_never_fails_on_them(
        repo, chantier, monkeypatch):
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    code, out, _ = chantier("preflight")
    assert code == 0, out
    assert any(ln.startswith("P10 warn") and "SendMessage" in ln for ln in out)
    assert len(out) <= 10
    settings = repo / ".claude"
    settings.mkdir()
    (settings / "settings.local.json").write_text(
        json.dumps({"permissions": {"allow": list(RECOMMENDED_ALLOW)}}), encoding="utf-8")
    assert any(ln.startswith("P10 ok") for ln in chantier("preflight")[1])
    (settings / "settings.local.json").write_text("{not json", encoding="utf-8")
    code, out, _ = chantier("preflight")
    assert code == 0 and any(ln.startswith("P10 warn") and "settings.local.json" in ln
                             for ln in out)
    (settings / "settings.local.json").unlink()
    (settings / "settings.json").write_text(
        json.dumps({"permissions": {"allow": list(RECOMMENDED_ALLOW)}}), encoding="utf-8")
    assert any(ln.startswith("P10 ok") for ln in chantier("preflight")[1])
    monkeypatch.setenv("CHANTIER_HOST", "copilot")
    monkeypatch.setenv("COPILOT_AGENT_SESSION_ID", "s-1")
    code, out, _ = chantier("preflight")
    assert code == 0 and not any("P10" in ln for ln in out)


def test_init_creates_the_eight_folders_once_and_refuses_outside_a_main_checkout(
        repo, chantier, tmp_path, monkeypatch):
    code, out, _ = chantier("init")
    assert code == 0 and [ln.split()[0] for ln in out] == ["created"] * 8
    changes = repo / ".agents" / "changes"
    assert sorted(p.name for p in changes.iterdir()) == [
        ".gitignore", "1-inbox", "2-backlog", "3-ready", "4-batch", "5-archives", "6-trash"]
    assert not [p for p in changes.rglob("*.*") if p.name != ".gitignore"]  # empty, no .gitkeep
    assert [ln.split()[0] for ln in chantier("init")[1]] == ["exists"] * 8
    sh("git", "worktree", "add", "--quiet", str(tmp_path / "wt"), "-b", "side", cwd=repo)
    monkeypatch.chdir(tmp_path / "wt")
    code, _, err = chantier("init")
    assert code == 2 and "main checkout" in err
    monkeypatch.chdir(tmp_path.parent)
    code, _, err = chantier("init")
    assert code == 2 and "git" in err


def test_a_cr_has_one_spelling_and_a_passed_gate_and_a_verdict_are_read_at_a_head():
    from chantier.commands import gate_passed, last_verdict
    from chantier.state import normalize_cr
    assert [normalize_cr(x) for x in ("165", "CR-165", "cr-165", "stack", "O-2", "-")] == [
        "CR-165", "CR-165", "CR-165", "stack", "O-2", "-"]
    g = lambda result, run, head="abc1234": {"kind": "gate", "result": result, "head": head, "run": run}  # noqa: E731
    assert gate_passed([g("pass", "1"), g("pass", "1")], "abc1234")
    assert not gate_passed([g("pass", "1"), g("fail", "1")], "abc1234")  # the second command failed
    assert not gate_passed([g("fail", "1"), g("pass", "2"), g("fail", "3")], "abc1234")  # the last run
    assert gate_passed([g("fail", "1"), g("pass", "2")], "abc1234")
    assert not gate_passed([g("pass", "1")], "other")
    v = lambda result, head="abc1234": {"kind": "verdict", "result": result, "head": head}  # noqa: E731
    assert last_verdict([v("VERIFIED"), v("NOT VERIFIED")], "abc1234") == "NOT VERIFIED"
    assert last_verdict([v("NOT VERIFIED"), v("VERIFIED")], "abc1234") == "VERIFIED"
    assert last_verdict([v("VERIFIED", "old")], "abc1234") is None


def test_cost_puts_the_steering_sessions_own_subagents_on_their_own_line_and_qa_on_a_driver():
    from chantier.commands import OWN_CHIEF, _breakdown, _kind, _label
    row = lambda agent, parent, **more: {"agent": agent, "type": "Explore", "parent": parent,  # noqa: E731
                                         "calls": 1, "usd": 1.0, **more}
    assert _kind(row("a", None)) == "Driver"  # tied to a CR, the stack or a QA order by the log
    own = row("b", None, own=OWN_CHIEF)  # `_cost_rows` marks the others
    assert (_kind(own), _label(own)) == ("Foreman", OWN_CHIEF)
    labels = [e["label"] for e in _breakdown([row("a", None), own, row("c", "a")])]
    assert labels == [OWN_CHIEF, "Driver Explore", "Worker Explore"]


def test_the_eval_sandbox_builds_its_recorded_base():
    script = PLUGIN_ROOT / "evals" / "kit" / "sandbox.py"
    done = subprocess.run([sys.executable, str(script), "build"], capture_output=True, text=True,
                          encoding="utf-8")
    assert done.returncode == 0, done.stdout + done.stderr
    found = re.search(r"^base ([0-9a-f]+)$", done.stdout, re.MULTILINE)
    assert found, done.stdout + done.stderr
    built = found.group(1)
    recorded = json.loads((PLUGIN_ROOT / "evals" / "kit" / "sandbox.json").read_text(encoding="utf-8"))["base"]
    assert built == recorded
    assert re.fullmatch(r"[0-9a-f]{40}", recorded)

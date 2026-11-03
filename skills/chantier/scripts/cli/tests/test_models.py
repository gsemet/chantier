import json

import pytest

from conftest import SKILL
from chantier.models import Models, detect_host, parse_yaml
from chantier.state import ChantierError

NEAR_MISSES = ["gpt-6-luna-x", "GPT-5.6-Luna", "gpt-5.6 luna", "gpt5.6-luna", "gpt-5.6-luna ",
               "GPT-5.6 Luna (copilot)", "luna", "gpt-5.6", "gpt-5-6-luna"]


def project_models(repo, text):
    path = repo / ".agents" / "chantier.models.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


# ---- parser -------------------------------------------------------------------------------

def test_parse_yaml_nested_comments_and_empty_mapping():
    data = parse_yaml("a: 1  # note\nb:\n  c: x # y\n  d: 'q # r'\ne: {}\nf:\n", "t")
    assert data == {"a": "1", "b": {"c": "x", "d": "q # r"}, "e": {}, "f": {}}


@pytest.mark.parametrize("text", ["a: [x, y]\n", "a:\n  b: 1\n   c: 2\n", "a: 1\na: 2\n",
                                  "a:\n\tb: 1\n", "- x\n", "a: {b: 1}\n"])
def test_parse_yaml_refuses_what_it_does_not_know(text):
    with pytest.raises(ChantierError):
        parse_yaml(text, "t")


# ---- base lists and layering ----------------------------------------------------------------

@pytest.mark.parametrize("host", ["claude", "copilot"])
def test_base_lists_are_valid(host, monkeypatch, tmp_path):
    monkeypatch.setenv("CHANTIER_MODELS_USER", str(tmp_path / "none.yml"))
    m = Models(host, SKILL, None)
    assert m.errors == []
    assert all(m.source[r] == "skill" for r in m.roles)


def test_copilot_defaults_are_exact(repo):
    m = Models("copilot", SKILL, repo)
    assert m.role("coder") == "gpt-5.6-luna"
    assert m.role("inspector") == "gpt-6.1-sol"
    assert m.frontmatter_model("coder") == "[GPT-5.6 Luna, gpt-5.6-luna]"


def test_project_overrides_user_overrides_skill(repo, tmp_path):
    (tmp_path / "user-models.yml").write_text(
        "copilot:\n  roles:\n    coder: gpt-6-luna\n    verifier: kimi-k3\n")
    project_models(repo, "copilot:\n  roles:\n    coder: gpt-5.6-terra\n")
    m = Models("copilot", SKILL, repo)
    assert m.errors == []
    assert (m.role("coder"), m.source["coder"]) == ("gpt-5.6-terra", "project")
    assert (m.role("verifier"), m.source["verifier"]) == ("kimi-k3", "user")
    assert (m.role("inspector"), m.source["inspector"]) == ("gpt-6.1-sol", "skill")


@pytest.mark.parametrize("value", NEAR_MISSES)
def test_near_miss_ids_are_refused_never_mapped(repo, value):
    project_models(repo, f"copilot:\n  roles:\n    coder: '{value}'\n")
    m = Models("copilot", SKILL, repo)
    assert any("role `coder`" in e and "not in the copilot catalog" in e for e in m.errors)
    with pytest.raises(ChantierError):
        m.exact(value)


def test_luna_generations_never_swap(repo):
    project_models(repo, "copilot:\n  roles:\n    coder: gpt-5.6-luna\n    debugger: gpt-6-luna\n")
    m = Models("copilot", SKILL, repo)
    assert m.role("coder") == "gpt-5.6-luna"
    assert m.role("debugger") == "gpt-6-luna"


def test_declared_alias_resolves_to_its_exact_target(repo):
    project_models(repo, "copilot:\n  aliases:\n    luna: gpt-5.6-luna\n  roles:\n"
                         "    coder: luna\n")
    m = Models("copilot", SKILL, repo)
    assert m.errors == [] and m.role("coder") == "gpt-5.6-luna"


@pytest.mark.parametrize("text,needle", [
    ("copilot:\n  roles:\n    coders: gpt-5.6-luna\n", "unknown role `coders`"),
    ("copilot:\n  role:\n    coder: gpt-5.6-luna\n", "unknown section `role`"),
    ("copiot:\n  roles:\n    coder: gpt-5.6-luna\n", "unknown host key"),
    ("copilot:\n  aliases:\n    luna: gpt-6.6-luna\n", "alias `luna` points to"),
    ("copilot:\n  aliases:\n    gpt-6-luna: gpt-5.6-luna\n", "also a model id"),
])
def test_config_mistakes_are_errors(repo, text, needle):
    project_models(repo, text)
    assert any(needle in e for e in Models("copilot", SKILL, repo).errors)


def test_legacy_models_in_chantier_json_is_an_error(repo, chantier):
    chantier("setup")
    cfg_path = repo / ".agents" / "chantier.json"
    cfg_path.parent.mkdir(exist_ok=True)
    cfg_path.write_text(json.dumps({"models": {"coder": "opus"}}))
    code, out, _ = chantier("models", "check")
    assert code == 2 and any("no longer read" in ln for ln in out)


def test_detect_host(monkeypatch):
    monkeypatch.delenv("CHANTIER_HOST", raising=False)
    for var in ("CLAUDE_CODE_ENTRYPOINT", "COPILOT_CLI", "COPILOT_AGENT_SESSION_ID", "AI_AGENT"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(ChantierError):
        detect_host()
    monkeypatch.setenv("AI_AGENT", "github_copilot_vscode_agent")
    assert detect_host()[0] == "copilot"
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    assert detect_host()[0] == "claude"
    assert detect_host("copilot") == ("copilot", "--host")


# ---- setup and preflight ----------------------------------------------------------------------

def test_setup_copilot_pins_models_in_github_agents(repo, chantier):
    code, out, err = chantier("setup", "--host", "copilot")
    assert code == 0, err
    text = (repo / ".github" / "agents" / "coder.agent.md").read_text()
    front = text.split("---\n")[1]
    assert "model: [GPT-5.6 Luna, gpt-5.6-luna]" in front
    assert "model-policy: required" in front
    assert 'tools: ["execute", "read", "edit", "search"]' in front
    assert "strict-tools-list: true" in front
    assert "user-invocable: false" in front
    for claude_only in ("Bash", "background:", "experimental:", "cacheTtl", "effort", "{{"):
        assert claude_only not in front
    assert "references/roles/coder.md" in text
    driver = (repo / ".github" / "agents" / "cr-driver.agent.md").read_text()
    assert "model: [Claude Sonnet 5.5, claude-sonnet-5.5]" in driver
    assert '"agent"' in driver and '"write_agent"' in driver
    assert not (repo / ".claude" / "agents").exists()
    foreman = (repo / ".github" / "agents" / "foreman.agent.md").read_text().split("---\n")[1]
    for line in ("model: [Claude Opus 5.5, claude-opus-5.5]", "reasoning-effort: low",
                 "user-invocable: true", '"send_message"', '"skill"'):
        assert line in foreman
    assert chantier("setup", "--host", "copilot")[1][0] == "setup: nothing to change (copilot)"


def test_setup_claude_installs_a_foreman_agent(repo, chantier, monkeypatch):
    assert chantier("setup", "--host", "claude")[0] == 0
    text = (repo / ".claude" / "agents" / "foreman.md").read_text()
    front = text.split("---\n")[1]
    assert "model: opus\neffort: low\n" in front and "ScheduleWakeup" in front
    assert "background" not in front and "references/roles/foreman.md" in text
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    assert chantier("models", "get", "foreman")[1][1] == "effort: low (copy this level exactly)"


def test_setup_refuses_an_invalid_config_and_installs_nothing(repo, chantier):
    project_models(repo, "copilot:\n  roles:\n    coder: GPT-5.6-Luna\n")
    code, _, err = chantier("setup", "--host", "copilot")
    assert code == 2 and "not in the copilot catalog" in err
    assert not (repo / ".github" / "agents").exists()


def test_preflight_catches_a_model_changed_after_setup(repo, chantier, monkeypatch):
    chantier("setup")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    project_models(repo, "claude:\n  roles:\n    coder: sonnet\n")
    code, out, _ = chantier("preflight")
    assert code == 2
    assert any(ln.startswith("P4 FAIL") and "model, effort or tools differ" in ln and "coder" in ln for ln in out)
    chantier("setup")
    assert "model: sonnet" in (repo / ".claude" / "agents" / "coder.md").read_text()
    assert chantier("preflight")[0] == 0


def test_preflight_fails_on_an_invalid_model(repo, chantier, monkeypatch):
    chantier("setup")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    project_models(repo, "claude:\n  roles:\n    coder: sonet\n")
    code, out, _ = chantier("preflight")
    assert code == 2 and any(ln.startswith("P8 FAIL") for ln in out)


# ---- get, brief and audit ---------------------------------------------------------------------

def set_brief_models(repo, line):
    brief = repo / ".agents" / "changes" / "batches" / "b1" / "brief.md"
    text = "\n".join(line if ln.startswith("- Models") else ln
                     for ln in brief.read_text().splitlines())
    brief.write_text(text + "\n")


@pytest.fixture
def copilot_ready(ready, chantier, monkeypatch):
    monkeypatch.setenv("CHANTIER_HOST", "copilot")
    assert chantier("setup")[0] == 0
    return ready


def test_get_omits_a_pinned_model_and_the_effort(copilot_ready, chantier):
    assert chantier("models", "get", "coder")[1] == ["model: omit (the agent file pins gpt-5.6-luna)",
                                                "effort: omit (the user's setting)",
                                                "agent: coder (spawn this agent exactly)"]
    assert chantier("models", "get", "foreman")[1][0].startswith("model: claude-opus-5.5")


def test_copilot_refuses_a_brief_override_of_a_pinned_role(copilot_ready, chantier):
    set_brief_models(copilot_ready, "- Models: coder@CR-102=gpt-6.1-sol, foreman=gpt-6-sol")
    code, _, err = chantier("models", "get", "coder", "--cr", "CR-102")
    assert code == 2 and "model-policy: required" in err
    assert chantier("models", "get", "coder", "--cr", "CR-101")[1][0].startswith("model: omit")
    assert chantier("models", "get", "foreman")[1][0].startswith("model: gpt-6-sol (brief foreman")
    code, out, _ = chantier("models", "check")
    assert code == 2 and any("coder=gpt-6.1-sol" in ln for ln in out)


def test_claude_passes_brief_overrides(ready, chantier, monkeypatch):
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    project_models(ready, "claude:\n  roles:\n    coder: sonnet\n")
    assert chantier("setup")[0] == 0
    set_brief_models(ready, "- Models: coder@CR-102=opus")
    out = chantier("models", "get", "coder", "--cr", "CR-102")[1]
    assert out[0] == "model: opus (brief coder@CR-102; copy this id exactly)"
    assert chantier("models", "check")[0] == 0


# ---- effort and tools -------------------------------------------------------------------------

def test_effort_is_rendered_with_each_host_field(repo, chantier):
    project_models(repo, "copilot:\n  effort:\n    coder: low\n    inspector: xhigh\n"
                         "claude:\n  effort:\n    coder: high\n")
    assert chantier("setup", "--host", "copilot")[0] == 0
    gh = repo / ".github" / "agents"
    assert "reasoning-effort: low" in (gh / "coder.agent.md").read_text()
    assert "reasoning-effort: xhigh" in (gh / "inspector.agent.md").read_text()
    assert "reasoning-effort" not in (gh / "verifier.agent.md").read_text()
    assert chantier("setup", "--host", "claude")[0] == 0
    coder = (repo / ".claude" / "agents" / "coder.md").read_text().split("---\n")[1]
    assert "effort: high\ntools: Bash, Read, Edit, Write, Grep, Glob" in coder
    assert "effort" not in (repo / ".claude" / "agents" / "inspector.md").read_text().split(
        "---\n")[1]


def test_effort_inherit_in_an_upper_layer_removes_the_base_level(repo, chantier, monkeypatch,
                                                                 tmp_path):
    user = tmp_path / "user-models.yml"
    user.write_text("copilot:\n  effort:\n    coder: high\n")
    monkeypatch.setenv("CHANTIER_MODELS_USER", str(user))
    m = Models("copilot", SKILL, repo)
    assert m.effort_of("coder") == "high" and m.effort_source["coder"] == "user"
    project_models(repo, "copilot:\n  effort:\n    coder: inherit\n")
    assert Models("copilot", SKILL, repo).effort_of("coder") is None


@pytest.mark.parametrize("level", ["High", "very-high", "minimal", "xhigh "])
def test_effort_levels_are_exact(repo, chantier, level):
    project_models(repo, f"copilot:\n  effort:\n    coder: '{level}'\n")
    assert any("effort `coder`" in e for e in Models("copilot", SKILL, repo).errors)
    code, _, err = chantier("setup", "--host", "copilot")
    assert code == 2 and not (repo / ".github" / "agents").exists()


def test_tools_cannot_be_overridden(repo, chantier):
    project_models(repo, "copilot:\n  tools:\n    inspector: execute, read, edit\n")
    errors = Models("copilot", SKILL, repo).errors
    assert any("`tools` is set by the skill only" in e for e in errors)


def test_preflight_catches_an_effort_changed_after_setup(repo, chantier, monkeypatch):
    chantier("setup")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    project_models(repo, "claude:\n  effort:\n    inspector: max\n")
    code, out, _ = chantier("preflight")
    assert any(ln.startswith("P4 FAIL") and "inspector" in ln for ln in out)
    chantier("setup")
    assert chantier("preflight")[0] == 0


def test_get_tells_the_foreman_its_effort(copilot_ready, chantier):
    project_models(copilot_ready, "copilot:\n  effort:\n    foreman: high\n    coder: low\n")
    assert chantier("models", "get", "foreman")[1][1].startswith("effort: omit (high is in the agent")
    assert chantier("models", "get", "coder")[1][1] == "effort: omit (the agent file sets low)"
    assert "coder [low]" in " ".join(chantier("models")[1])


@pytest.mark.parametrize("host,beat,seconds", [("copilot", "4m", 240), ("claude", "55m", 3300)])
def test_heartbeat_follows_the_host_cache_ttl(repo, host, beat, seconds):
    m = Models(host, SKILL, repo)
    assert (m.heartbeat, m.heartbeat_seconds(), m.heartbeat_source) == (beat, seconds, "skill")


def test_get_tells_the_foreman_its_heartbeat(copilot_ready, chantier):
    assert chantier("models", "get", "foreman")[1][2] == "heartbeat: 4m (240 s)"
    assert not any(ln.startswith("heartbeat") for ln in chantier("models", "get", "coder")[1])
    project_models(copilot_ready, "copilot:\n  heartbeat: 25m\n")
    assert chantier("models", "get", "foreman")[1][2] == "heartbeat: 25m (1500 s)"
    assert "heartbeat: 25m (project)" in chantier("models")[1]


@pytest.mark.parametrize("beat", ["4 m", "4min", "0m", "30s", "61m", "1h", "4M"])
def test_heartbeat_mistakes_are_errors(repo, beat):
    project_models(repo, f"copilot:\n  heartbeat: {beat}\n")
    assert any("heartbeat" in e for e in Models("copilot", SKILL, repo).errors)


@pytest.mark.parametrize("entry", ["coder@CR-102=GPT-6.1-Sol", "coder@CR-102=gpt 6.1 sol",
                                   "coder CR-102 opus", "coders=gpt-6.1-sol"])
def test_brief_models_line_is_exact(copilot_ready, chantier, entry):
    set_brief_models(copilot_ready, f"- Models: {entry}")
    code, out, err = chantier("models", "check")
    assert code == 2, out
    assert chantier("models", "get", "coder", "--cr", "CR-102")[0] == 2


def test_check_and_show(copilot_ready, chantier):
    code, out, _ = chantier("models", "check")
    assert code == 0 and out[0].startswith("models ok (copilot)")
    out = chantier("models")[1]
    assert out[0].startswith("copilot models")
    assert any(ln.startswith("gpt-5.6-luna:") and "coder" in ln for ln in out)


def write_events(tmp_path, session, spawns):
    path = tmp_path / "copilot-home" / "session-state" / session / "events.jsonl"
    path.parent.mkdir(parents=True)
    lines = [json.dumps({"type": "session.start", "data": {}})]
    for agent_id, role, name, model, source, *effort in spawns:
        lines.append(json.dumps({"type": "subagent.started", "agentId": agent_id, "data": {
            "agentName": role, "agentType": role, "agentDisplayName": name, "model": model,
            "modelSelectionSource": source}}))
        lines.append(json.dumps({"type": "subagent.configured", "agentId": agent_id, "data": {
            "model": model, "reasoningEffort": effort[0] if effort else "medium"}}))
    path.write_text("\n".join(lines) + "\n")


def test_audit_flags_a_model_that_is_not_the_configured_one(copilot_ready, chantier, tmp_path):
    set_brief_models(copilot_ready, "- Models: coder@CR-102=gpt-6.1-sol")
    assert chantier("agents", "set", "CR-101", "drv-1")[0] == 0
    write_events(tmp_path, "s1", [
        ("drv-1", "cr-driver", "driver", "claude-sonnet-5.5", "agent_definition_default"),
        ("c1", "coder", "CR-101 coder", "gpt-5.6-luna", "agent_definition_default"),
        ("c2", "coder", "CR-102 coder", "gpt-6.1-sol", "explicit_override"),
        ("c3", "coder", "CR-103 coder", "gpt-6-luna", "explicit_override"),
        ("t1", "task", "unrelated", "gpt-6-luna", "session_inheritance"),
    ])
    code, out, _ = chantier("models", "audit", "--session", "s1")
    assert code == 2
    assert out[0] == "audit s1: 4 chantier spawns, 1 mismatched"
    assert out[1].startswith("MISMATCH coder CR-103 ran gpt-6-luna, expected gpt-5.6-luna")


def test_audit_passes_when_every_spawn_ran_its_model(copilot_ready, chantier, tmp_path):
    write_events(tmp_path, "s2", [
        ("c1", "coder", "CR-101 coder", "gpt-5.6-luna", "agent_definition_default"),
        ("i1", "inspector", "CR-101 inspector", "gpt-6.1-sol", "agent_definition_default"),
    ])
    assert chantier("models", "audit", "--session", "s2")[:2] == (0, [
        "audit s2: 2 chantier spawns, 0 mismatched"])


def test_audit_is_copilot_only(ready, chantier):
    assert chantier("models", "audit", "--session", "x")[0] == 1


def test_audit_flags_an_effort_that_is_not_the_configured_one(copilot_ready, chantier, tmp_path):
    project_models(copilot_ready, "copilot:\n  effort:\n    coder: low\n")
    write_events(tmp_path, "s2", [
        ("c1", "coder", "CR-101 coder", "gpt-5.6-luna", "agent_definition_default", "low"),
        ("c2", "coder", "CR-102 coder", "gpt-5.6-luna", "agent_definition_default", "high"),
        ("i1", "inspector", "CR-101 inspector", "gpt-6.1-sol", "agent_definition_default"),
    ])
    code, out, _ = chantier("models", "audit", "--session", "s2")
    assert code == 2 and out[0] == "audit s2: 3 chantier spawns, 1 mismatched"
    assert out[1] == "MISMATCH coder CR-102 ran effort high, expected low"


def foreman_events(tmp_path, ready, chantier, records, schedules=()):
    chantier("foreman", "set", "chat-f")
    chantier("foreman", "transcript", "fs1", "--epoch", 1)
    path = tmp_path / "copilot-home" / "session-state" / "fs1" / "events.jsonl"
    path.parent.mkdir(parents=True)
    lines = [{"type": "session.usage_record", "data": {"usage": {
        "model": model, "reasoningEffort": effort}}} for model, effort in records]
    lines.append({"type": "session.usage_record", "agentId": "c1", "data": {"usage": {
        "model": "gpt-5.6-luna", "reasoningEffort": "low"}}})
    lines += [{"type": "session.schedule_created", "data": {
        "id": i, "prompt": prompt, "intervalMs": ms, "recurring": True}}
        for i, (prompt, ms) in enumerate(schedules, 1)]
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n")


def test_audit_checks_the_foreman_model_effort_and_heartbeat(copilot_ready, chantier, tmp_path):
    foreman_events(tmp_path, copilot_ready, chantier, [("claude-opus-5.5", "medium")] * 3,
                   [("chantier heartbeat b1 epoch 1", 240_000)])
    code, out, _ = chantier("models", "audit")
    assert code == 0, out
    assert out == ["audit fs1: 0 chantier spawns, 0 mismatched",
                   "foreman ran claude-opus-5.5 effort medium (3 calls)",
                   "NOTE foreman effort medium, configured low: create_session cannot set it "
                   "(accepted exception)"]


def test_audit_flags_a_foreman_model_and_a_missing_heartbeat(copilot_ready, chantier, tmp_path):
    foreman_events(tmp_path, copilot_ready, chantier, [("claude-sonnet-5.5", "low")],
                   [("chantier heartbeat b1 epoch 1", 3_300_000)])
    code, out, _ = chantier("models", "audit")
    assert code == 2
    assert "MISMATCH foreman ran claude-sonnet-5.5, expected claude-opus-5.5 (skill foreman)" in out
    assert "MISMATCH heartbeat every 3300 s, expected 4m (240 s)" in out

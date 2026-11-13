"""Smoke runs of the CLI in a fresh repository: the seat, no setup, an external surface, direct and
Foreman batches, preflight allow rules and `init`.
"""

import json
import os
import re
from pathlib import Path

import pytest
from conftest import SKILL, Chantier, sh

from chantier.commands.permissions import RECOMMENDED_ALLOW, SAMPLES, rule_matches
from chantier.core.errors import EXIT_BUDGET, EXIT_PRECONDITION


def _prepared(repo: Path, chantier: Chantier, title: str = "Fix login") -> Path:
    _, out, _ = chantier("file", title)
    folder = repo / out[0].removeprefix("filed ").split(";")[0]
    (folder / "03-change-spec.md").write_text(f"# {title}\n\nDo it.\n")
    return folder


MAX_OUTPUT_LINES = 10  # past ten lines the tool output is cut
FROM_AGENTS_MD = ("--default-branch", "main")  # what the Chief of Staff read in the project's rules


def test_the_seat_is_one_file_held_until_taken_over_on_purpose(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    changes = repo / ".agents" / "changes"
    assert chantier("seat")[1] == ["seat none"]
    code, out, _ = chantier(
        "seat",
        "take",
        "s-1",
        "--env",
        "Mac",
        "--title",
        "[Mac] Proj [Chief of Staff]",
        "--link",
        "claude://s-1",
    )
    assert (code, out) == (0, ["seat s-1"])
    assert sorted(p.name for p in changes.iterdir() if not p.name.startswith(".")) == ["seat.json"]
    seat = json.loads((changes / "seat.json").read_text(encoding="utf-8"))
    assert seat["session"] == "s-1" and seat["link"] == "claude://s-1"
    assert set(seat) == {"session", "transcript", "env", "title", "link"}  # no date
    assert (
        chantier("seat")[1][0]
        == 'seat s-1 env Mac title "[Mac] Proj [Chief of Staff]" link claude://s-1'
    )
    assert chantier("seat", "take", "s-1", "--title", "again")[0] == 0  # the same session
    code, _, err = chantier("seat", "take", "s-2")
    assert code == EXIT_PRECONDITION and "held by s-1" in err and "--over s-1" in err
    assert chantier("seat", "take", "s-2", "--over", "s-3")[0] == EXIT_PRECONDITION
    assert chantier("seat", "leave", "s-2")[0] == EXIT_PRECONDITION
    assert chantier("seat", "take", "s-2", "--over", "s-1")[1] == ["seat s-2"]
    assert chantier("seat", "leave", "s-2")[1] == ["seat none"]
    assert chantier("seat", "leave", "s-2")[1] == ["seat none"]


@pytest.mark.parametrize("host", ["claude", "copilot"])
def test_the_plugin_runs_with_no_setup_and_writes_only_in_the_planning_folder(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, host: str
) -> None:
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
    assert chantier("gate", "CR-101", "true")[0] == EXIT_PRECONDITION
    code, out, _ = chantier("take", "CR-101")
    assert code == 0 and out[0].startswith("took CR-101")
    assert any(ln.startswith("cards: ") and "references/" in ln for ln in out)
    assert any(ln.startswith("worktree: ") and "not created yet" in ln for ln in out)
    _, out, _ = chantier("round", "CR-101", "--note", "round 1")
    assert out[0] == "round 1 of 3 for CR-101"
    assert chantier("status")[1][-1].startswith("CR-101 working r1/3")
    code, _, err = chantier("round", "CR-101")  # nothing happened since round 1: refused
    assert code == EXIT_PRECONDITION and "nothing happened since" in err
    assert chantier("status")[1][-1].startswith("CR-101 working r1/3")
    for i in range(2):
        chantier("note", "CR-101", f"note {i}")
        assert chantier("round", "CR-101")[0] == 0
    assert chantier("round", "CR-101")[0] == EXIT_BUDGET  # the round limit is a rail
    assert chantier("order", "rounds", "CR-101", "--note", "4")[0] == 0
    chantier("note", "CR-101", "another round")
    _, out, _ = chantier("note", "CR-101", "context")
    assert out == ["ok", "context: not measured (no agent recorded)"]
    assert chantier("round", "CR-101")[0] == 0
    _, out, _ = chantier("rules", "--batch", "1")  # every prompt passes --batch
    assert out[0].startswith(str(repo / "AGENTS.md").replace("\\", "/"))
    assert sh("git", "status", "--porcelain", "-uall", cwd=repo).splitlines() and all(
        line.startswith("?? .agents/changes/")
        for line in sh("git", "status", "--porcelain", "-uall", cwd=repo).splitlines()
    )


def test_an_external_surface_gets_the_planning_folder_and_the_project_stays_clean(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    surface = tmp_path / "surface"
    project = surface / "projects" / "demo"
    project.mkdir(parents=True)
    (project / "checkout.yml").write_text(
        f"# the clone\nrepo: {Path(os.path.relpath(repo, project)).as_posix()}\n"
        "worktrees: ../../../wt\n"
    )
    sh("git", "init", "--quiet", "-b", "main", str(surface))
    sh("git", "add", ".", cwd=surface)
    sh(
        "git",
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.com",
        "commit",
        "--quiet",
        "-m",
        "init",
        cwd=surface,
    )
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
    assert any(
        ln.startswith("cli: ") and f'--project "{project.resolve().as_posix()}"' in ln for ln in out
    )
    assert any(ln.startswith("clone: ") and repo.name in ln for ln in out)
    assert any(
        ln.startswith("worktree: ") and "/wt/batch-01-CR-101" in ln.replace("\\", "/") for ln in out
    )
    assert any(ln.startswith("archive: in the PR at .agents/changes/5-archives/") for ln in out)
    shown = sh("git", "status", "--porcelain", "-uall", cwd=surface).splitlines()
    assert shown and all(ln.startswith("?? projects/demo/changes/") for ln in shown)
    local = ("batch.json", "events.jsonl", "STATUS", ".lock", ".batch-number", "seat.json")
    assert not [ln for ln in shown if any(name in ln for name in local)], shown
    assert sh("git", "status", "--porcelain", "-uall", cwd=repo) == ""


def test_a_direct_batch_is_recorded_shown_and_queues_added_work(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "uuid-chief")
    first, second = _prepared(repo, chantier), _prepared(repo, chantier, "Fix logout")
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    code, _, err = chantier("open", str(first), "--direct", *FROM_AGENTS_MD)
    assert (
        code == EXIT_PRECONDITION and "session id" in err
    )  # nothing could tell a Foreman's claim from its own
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "uuid-chief")
    code, out, err = chantier("open", str(first), "--direct", *FROM_AGENTS_MD)
    assert code == 0, err
    assert out[1].endswith("then steer it yourself")
    batch = repo / ".agents" / "changes" / "4-batch" / "batch.json"
    assert json.loads(batch.read_text(encoding="utf-8"))["steering"] == "direct"
    assert "Steering: direct" in (batch.parent / "brief.md").read_text(encoding="utf-8")
    assert " steering direct " in chantier("status")[1][0]
    assert "steered by the Chief of Staff (direct mode) · independent PRs (parallel)" in (
        batch.parent / "STATUS.md"
    ).read_text(encoding="utf-8")
    code, _, err = chantier("order", "qa", "--note", "test it")
    assert code == EXIT_PRECONDITION and "a running direct batch takes no QA" in err
    code, out, err = chantier("order", "add", "--note", str(second))
    assert code == 0 and any("added CR-102, queued" in ln for ln in out), (
        err
    )  # taken at a free slot
    assert chantier("order", "note", "101", "--note", "hello")[0] == 0  # a bare number is a CR


def test_a_foreman_batch_takes_added_work_and_a_direct_preflight_leaves_out_p2(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    code, out, _ = chantier("preflight")
    assert code == EXIT_PRECONDITION and any(ln.startswith("P1 FAIL") for ln in out)
    code, out, _ = chantier("preflight", "--direct")
    assert code == 0, out
    assert any(ln.startswith("P1 ok") for ln in out)
    assert any(ln.startswith("P3, P9 and") for ln in out) and not any("P2" in ln for ln in out)
    chantier("open", str(_prepared(repo, chantier)), *FROM_AGENTS_MD)
    assert chantier("order", "qa", "--note", "test it")[0] == 0


def test_a_byte_order_mark_from_windows_powershell_is_read_through(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
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


def test_the_allow_rules_json_block_lists_exactly_what_preflight_checks() -> None:
    text = (SKILL / "references" / "hosts" / "claude-code.md").read_text(encoding="utf-8")
    section = text.split("### Allow rules\n", 1)[1]
    found = re.search(r"```json\n(.*?)\n```", section, re.S)
    assert found is not None
    block = found[1]
    assert tuple(json.loads(block)["permissions"]["allow"]) == RECOMMENDED_ALLOW
    for _, command, rule in SAMPLES:  # each sample is covered by its own rule, in both forms
        assert all(
            rule_matches(f"{tool}({rule})", tool, command) for tool in ("Bash", "PowerShell")
        ), command
    assert rule_matches("SendMessage", "SendMessage")


def test_preflight_warns_on_missing_allow_rules_and_never_fails_on_them(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    code, out, _ = chantier("preflight")
    assert code == 0, out
    assert any(
        ln.startswith("P10 warn")
        and "SendMessage" in ln
        and "git push --force-with-lease -u origin chantier/*" in ln
        for ln in out
    )
    assert len(out) <= MAX_OUTPUT_LINES
    settings = repo / ".claude"
    settings.mkdir()
    local = settings / "settings.local.json"

    def p10(permissions: dict[str, list[str]]) -> str:
        local.write_text(json.dumps({"permissions": permissions}), encoding="utf-8")
        code, out, _ = chantier("preflight")
        assert code == 0
        return next(ln for ln in out if ln.startswith("P10"))

    user = [
        "git push --force-with-lease -u origin chantier/*",
        "git push --force-with-lease=chantier/* origin *chantier/*",
    ]
    line = p10({"allow": [f"{tool}({r})" for r in user for tool in ("Bash", "PowerShell")]})
    assert "add Bash(git push --force-with-lease -u origin" not in line  # equivalence is judged
    assert "add Bash(git -C * push --force-with-lease -u origin chantier/*)" in line
    assert p10({"allow": ["Bash(*)", "PowerShell(*)"]}).startswith("P10 warn")
    line = p10(
        {
            "allow": list(RECOMMENDED_ALLOW),
            "deny": ["Bash(git push --force-with-lease*)", "PowerShell(git push --force*)"],
        }
    )
    assert line.startswith("P10 warn") and "denied: git push --force-with-lease" in line


def test_preflight_reads_the_settings_files_for_allow_rules(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    settings = repo / ".claude"
    settings.mkdir()
    (settings / "settings.local.json").write_text(
        json.dumps({"permissions": {"allow": list(RECOMMENDED_ALLOW)}}), encoding="utf-8"
    )
    assert any(ln.startswith("P10 ok") for ln in chantier("preflight")[1])
    (settings / "settings.local.json").write_text("{not json", encoding="utf-8")
    code, out, _ = chantier("preflight")
    assert code == 0 and any(
        ln.startswith("P10 warn") and "settings.local.json" in ln for ln in out
    )
    (settings / "settings.local.json").unlink()
    (settings / "settings.json").write_text(
        json.dumps({"permissions": {"allow": list(RECOMMENDED_ALLOW)}}), encoding="utf-8"
    )
    assert any(ln.startswith("P10 ok") for ln in chantier("preflight")[1])


def test_preflight_has_no_allow_rule_check_on_copilot(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHANTIER_HOST", "copilot")
    monkeypatch.setenv("COPILOT_AGENT_SESSION_ID", "s-1")
    code, out, _ = chantier("preflight")
    assert code == 0 and not any("P10" in ln for ln in out)


def test_init_creates_the_eight_folders_once_and_refuses_outside_a_main_checkout(
    repo: Path, chantier: Chantier, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    code, out, _ = chantier("init")
    assert code == 0 and [ln.split()[0] for ln in out] == ["created"] * 8
    changes = repo / ".agents" / "changes"
    assert sorted(p.name for p in changes.iterdir()) == [
        ".gitignore",
        "1-inbox",
        "2-backlog",
        "3-ready",
        "4-batch",
        "5-archives",
        "6-trash",
    ]
    assert not [p for p in changes.rglob("*.*") if p.name != ".gitignore"]  # empty, no .gitkeep
    assert [ln.split()[0] for ln in chantier("init")[1]] == ["exists"] * 8
    sh("git", "worktree", "add", "--quiet", str(tmp_path / "wt"), "-b", "side", cwd=repo)
    monkeypatch.chdir(tmp_path / "wt")
    code, _, err = chantier("init")
    assert code == EXIT_PRECONDITION and "main checkout" in err
    monkeypatch.chdir(tmp_path.parent)
    code, _, err = chantier("init")
    assert code == EXIT_PRECONDITION and "git" in err

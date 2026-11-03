"""Prepared CRs move between project stages without losing their contents."""
import json
import os

import pytest

from conftest import sh

GATES = ("--fast-gate", "exit 0", "--long-gate", "exit 0")


def prepare(repo, chantier, title="Prepared change"):
    code, _, err = chantier("file", title)
    assert code == 0, err
    folder = repo / ".agents/changes/backlog/1-inbox" / title.lower().replace(" ", "-")
    (folder / "03-change-spec.md").write_text(f"# {title}\n\nDo the work.\n")
    return folder


def open_cr(chantier, batch, item, *options):
    return chantier("open", batch, f"@{item}", *GATES, "--default-branch", "main", *options)


def test_numbering_starts_at_project_value_and_failed_open_does_not_consume_it(repo, chantier):
    folder = prepare(repo, chantier)
    code, _, err = open_cr(chantier, "failed", folder, "--remote", "missing",
                           "--first-cr-number", "1")
    assert code == 4 and "no remote" in err
    assert (folder / "03-change-spec.md").is_file()
    assert not (repo / ".agents/changes/.chantier-counter").exists()

    code, out, err = open_cr(chantier, "retry", folder, "--no-worktrees",
                             "--first-cr-number", "1")
    assert code == 0, err
    assert any(line.startswith("CR-1 ") for line in out)
    active = repo / ".agents/changes/backlog/3-requests/001-prepared-change"
    assert active.is_dir() and not folder.exists()


def test_existing_archive_number_takes_precedence_over_project_start(repo, chantier):
    folder = prepare(repo, chantier)
    archive = repo / ".agents/changes/backlog/4-archives/005-previous"
    archive.mkdir(parents=True)
    code, out, err = open_cr(chantier, "next", folder, "--no-worktrees",
                             "--first-cr-number", "1")
    assert code == 0, err
    assert any(line.startswith("CR-6 ") for line in out)
    assert (repo / ".agents/changes/backlog/3-requests/006-prepared-change").is_dir()


def test_specification_and_existing_files_survive_drop_reopen_and_merge(repo, chantier):
    folder = prepare(repo, chantier)
    (folder / "alternate-spec.md").write_text("# Alternate\n\nOriginal scope.\n")
    expected = {"task.md": "Existing task\n", "STATE.md": "Existing state\n",
                "report.md": "Existing report\n"}
    for name, text in expected.items():
        (folder / name).write_text(text)

    code, _, err = open_cr(chantier, "first", folder / "alternate-spec.md", "--no-worktrees")
    assert code == 0, err
    code, out, err = chantier("path", "CR-101", "--spec", "--batch", "first")
    assert code == 0, err
    assert out == [str((repo / ".agents/changes/backlog/3-requests/101-prepared-change"
                        / "alternate-spec.md").resolve())]
    assert chantier("foreman", "set", "f1", "--batch", "first")[0] == 0
    assert chantier("event", "start", "--batch", "first", "--epoch", "1")[0] == 0
    assert chantier("order", "drop", "CR-101", "--batch", "first")[0] == 0
    assert chantier("event", "--order", "O-1", "--batch", "first", "--epoch", "1")[0] == 0
    assert chantier("cancel", "CR-101", "--batch", "first", "--epoch", "1")[0] == 0
    assert folder.is_dir()
    for name, text in expected.items():
        assert (folder / name).read_text() == text

    (folder / "alternate-spec.md").write_text("# Alternate\n\nUpdated scope.\n")
    code, _, err = open_cr(chantier, "second", folder / "alternate-spec.md", "--no-worktrees")
    assert code == 0, err
    code, out, err = chantier("path", "CR-102", "--spec", "--batch", "second")
    assert code == 0, err
    assert "Updated scope." in (repo / out[0]).read_text()
    assert chantier("foreman", "set", "f2", "--batch", "second")[0] == 0
    assert chantier("event", "start", "--batch", "second", "--epoch", "1")[0] == 0
    assert chantier("event", "hand-back-ready", "CR-102", "https://example.com/pr/1",
                    "--batch", "second", "--epoch", "1")[0] == 0
    assert chantier("order", "merged", "CR-102", "--batch", "second")[0] == 0
    assert chantier("event", "--order", "O-1", "--batch", "second", "--epoch", "1")[0] == 0
    code, out, err = chantier("path", "CR-102", "--batch", "second")
    assert code == 0, err
    archived = repo / out[0]
    assert archived.parent.name == "4-archives"
    for name, text in expected.items():
        assert (archived / name).read_text() == text
    assert "Updated scope." in (archived / "alternate-spec.md").read_text()


def test_unknown_branch_and_missing_gate_block_before_moving_a_cr(repo, chantier):
    folder = prepare(repo, chantier)
    code, _, err = chantier("open", "missing-long", f"@{folder}", "--no-worktrees",
                             "--fast-gate", "exit 0", "--default-branch", "main")
    assert code == 2 and "no long gate supplied" in err and folder.is_dir()
    code, _, err = chantier("open", "missing-branch", f"@{folder}", "--no-worktrees", *GATES)
    assert code == 2 and "pass --default-branch" in err and folder.is_dir()
    code, _, err = chantier("order", "add", "--note", "raw title")
    assert code == 1 and "prepared-CR" in err


def test_open_preserves_an_existing_batch_brief(repo, chantier):
    folder = prepare(repo, chantier)
    brief = repo / ".agents/changes/batches/reused/brief.md"
    brief.parent.mkdir(parents=True)
    brief.write_text("Existing user brief\n")
    code, _, err = open_cr(chantier, "reused", folder, "--no-worktrees")
    assert code == 3 and "refusing to overwrite" in err
    assert brief.read_text() == "Existing user brief\n"
    assert folder.is_dir()


def test_legacy_brief_override_fails_preflight(repo, chantier, monkeypatch):
    monkeypatch.setenv("CHANTIER_HOST", "copilot")
    monkeypatch.setenv("COPILOT_AGENT_SESSION_ID", "s-1")
    folder = prepare(repo, chantier)
    assert open_cr(chantier, "legacy", folder, "--no-worktrees")[0] == 0
    brief = repo / ".agents/changes/batches/legacy/brief.md"
    brief.write_text(brief.read_text() + "- Models: coder=some-model\n")
    code, lines, _ = chantier("preflight")
    assert code == 2 and any("brief model overrides are no longer supported" in line for line in lines)
    code, lines, _ = chantier("models", "check", "--batch", "legacy")
    assert code == 2 and any("brief model overrides are no longer supported" in line for line in lines)


def test_ship_requires_body_before_push(repo, chantier, tmp_path):
    origin = tmp_path / "origin.git"
    sh("git", "init", "--quiet", "--bare", "-b", "main", str(origin))
    sh("git", "remote", "add", "origin", str(origin), cwd=repo)
    sh("git", "push", "--quiet", "-u", "origin", "main", cwd=repo)
    folder = prepare(repo, chantier)
    code, _, err = open_cr(chantier, "shipping", folder)
    assert code == 0, err
    state = repo / ".agents/changes/batches/shipping/batch.json"
    cr = json.loads(state.read_text())["crs"][0]
    code, _, err = chantier("ship", cr["id"], "--batch", "shipping")
    assert code == 2 and "write" in err and "pr-body.md" in err
    assert sh("git", "ls-remote", "--heads", "origin", cr["branch"], cwd=repo) == ""


def test_custom_changes_root_is_resolved_from_a_worktree(repo, chantier, monkeypatch, tmp_path):
    origin = tmp_path / "origin.git"
    sh("git", "init", "--quiet", "--bare", "-b", "main", str(origin))
    sh("git", "remote", "add", "origin", str(origin), cwd=repo)
    sh("git", "push", "--quiet", "-u", "origin", "main", cwd=repo)
    changes = repo / ".agents/other changes"
    code, _, err = chantier("--changes-dir", changes, "file", "Custom root")
    assert code == 0, err
    folder = changes / "backlog/1-inbox/custom-root"
    (folder / "03-change-spec.md").write_text("# Custom root\n\nDo the work.\n")
    code, _, err = chantier("--changes-dir", changes, "open", "custom", f"@{folder}", *GATES,
                             "--default-branch", "main")
    assert code == 0, err
    state = json.loads((changes / "batches/custom/batch.json").read_text())
    monkeypatch.chdir(state["crs"][0]["worktree"])
    code, out, err = chantier("--changes-dir", changes, "path", "CR-101",
                               "--batch", "custom", "--spec")
    assert code == 0, err
    assert (repo / out[0]).read_text() == "# Custom root\n\nDo the work.\n"
    assert "CHANTIER_CHANGES" not in os.environ


@pytest.mark.parametrize("fast,long,fast_code,long_code", [
    ("exit 0", "exit 7", 0, 4),
    ("exit 7", "exit 0", 4, 0),
])
def test_fast_and_long_gates_execute_and_fail_independently(
        repo, chantier, tmp_path, fast, long, fast_code, long_code):
    origin = tmp_path / "origin.git"
    sh("git", "init", "--quiet", "--bare", "-b", "main", str(origin))
    sh("git", "remote", "add", "origin", str(origin), cwd=repo)
    sh("git", "push", "--quiet", "-u", "origin", "main", cwd=repo)
    folder = prepare(repo, chantier)
    code, _, err = chantier("open", "gates", f"@{folder}", "--default-branch", "main",
                             "--fast-gate", fast, "--long-gate", long)
    assert code == 0, err
    code, out, _ = chantier("gate", "CR-101", "--batch", "gates")
    assert code == fast_code
    assert ("pass" if fast_code == 0 else "FAIL") in out[0]
    code, out, _ = chantier("gate", "CR-101", "--long", "--batch", "gates")
    assert code == long_code
    assert ("pass" if long_code == 0 else "FAIL") in out[0]
    logs = repo / ".agents/changes/backlog/3-requests/101-prepared-change/scratch/gates"
    assert len(list(logs.glob("*-fast.log"))) == 1
    assert len(list(logs.glob("*-long.log"))) == 1

    state = repo / ".agents/changes/batches/gates/batch.json"
    data = json.loads(state.read_text())
    data["settings"]["gates"]["fast"] = []
    state.write_text(json.dumps(data))
    code, _, err = chantier("gate", "CR-101", "--batch", "gates")
    assert code == 2 and "no fast gate was recorded" in err

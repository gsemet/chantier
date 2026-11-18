"""An external planning surface: the CLI's runs on it, and the archive in the PR, off unless the
project's `project.md` says `yes`."""

import json
import os
from pathlib import Path

import pytest
from conftest import Chantier, sh
from test_cli_runs import FROM_AGENTS_MD, _prepared

from chantier import plugin_files
from chantier.commands import delivery
from chantier.core.records import CrEntry
from chantier.core.repo import Repo


def _the_cr_drivers_writes_hold_the_folder_then_the_absolute_archive(out: list[str]) -> None:
    archive = next(ln for ln in out if ln.startswith("archive: in the PR at ")).split(" at ")[1]
    folder = next(ln for ln in out if ln.startswith("folder: ")).split(" (")[0][len("folder: ") :]
    heading = next(i for i, ln in enumerate(out) if ln.startswith("cr-driver prompt ("))
    writes = next(ln for ln in out[heading:] if ln.startswith("  writes: ")).removeprefix(
        "  writes: "
    )
    assert writes.startswith(f"{folder}; ") and writes.endswith(archive)
    assert Path(writes.split("; ")[1]).is_absolute()


def _surface(repo: Path, tmp_path: Path, project_md: str | None) -> tuple[Path, Path]:
    """A one-project surface (`demo`) over `repo`, with the given `project.md` (None: no file)."""
    surface = tmp_path / "surface"
    project = surface / "projects" / "demo"
    project.mkdir(parents=True)
    (project / "checkout.yml").write_text(
        f"# the clone\nrepo: {Path(os.path.relpath(repo, project)).as_posix()}\n"
        "worktrees: ../../../wt\n"
    )
    if project_md is not None:
        (project / "project.md").write_text(project_md, encoding="utf-8")
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
    return surface, project


@pytest.mark.parametrize(
    ("project_md", "archived"),
    [
        (None, False),
        ("# demo\n\nNothing about the archive.\n", False),
        ("# demo\n\n- Archive in the PR: no\n", False),
        ("# demo\n\n- Archive in the PR: no (the CRs live on the surface)\n", False),
        ("# demo\n\n- Archive in the PR: yes\n", True),
        ("# demo\n\n- Archive in the PR: Yes\n", True),
    ],
)
def test_an_external_project_keeps_the_archive_out_of_its_pr_unless_it_says_yes(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    project_md: str | None,
    archived: bool,
) -> None:
    surface, _ = _surface(repo, tmp_path, project_md)
    monkeypatch.chdir(surface)
    found = Repo.find(project="demo")
    assert found.external and found.archive_in_pr is archived
    path = plugin_files.archive_path(found, CrEntry(id="CR-101", path="1-inbox/fix-login"))
    assert (path is None) is (not archived)


def _ship_once(
    repo: Path, project: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, archived: bool
) -> None:
    cr = json.loads(next(project.glob("changes/4-batch/batch.json")).read_text(encoding="utf-8"))[
        "crs"
    ][0]
    sh("git", "worktree", "add", "-q", "-b", cr["branch"], cr["worktree"], "HEAD", cwd=repo)
    (Path(cr["worktree"]) / "f.txt").write_text("f\n")
    sh("git", "add", "f.txt", cwd=Path(cr["worktree"]))
    sh(
        "git",
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.com",
        "commit",
        "--quiet",
        "-m",
        "work",
        cwd=Path(cr["worktree"]),
    )
    monkeypatch.setattr(delivery, "read_state", lambda link: ("main", False, ""))
    code, out, err = chantier("ship", "CR-101", "https://github.com/acme/demo/pull/7")
    assert code == 0, err
    missing = [ln for ln in out if "archive missing" in ln]
    if archived:
        assert (
            len(missing) == 1
            and "archive missing from the PR at .agents/changes/5-archives/" in missing[0]
        )
    else:
        assert not missing, out


@pytest.mark.parametrize("archived", [False, True])
def test_an_external_surface_gets_the_planning_folder_and_the_project_stays_clean(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    archived: bool,
) -> None:
    surface, project = _surface(
        repo, tmp_path, "# demo\n\n- Archive in the PR: yes\n" if archived else None
    )
    monkeypatch.chdir(surface)
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
    assert chantier("preflight")[0] == 0
    folder = _prepared(surface, chantier)  # one project: taken without --project
    assert folder.relative_to(surface).as_posix().startswith("projects/demo/changes/1-inbox/")
    code, _, err = chantier("open", str(folder), *FROM_AGENTS_MD)
    assert code == 0, err
    code, out, _ = chantier("take", "CR-101", "--epoch", 0)
    assert code == 0, out
    assert any(
        ln.startswith("cli: ") and f'--project "{project.resolve().as_posix()}"' in ln for ln in out
    )
    assert any(ln.startswith("clone: ") and repo.name in ln for ln in out)
    assert any(
        ln.startswith("worktree: ") and "/wt/batch-01-CR-101" in ln.replace("\\", "/") for ln in out
    )
    if archived:
        assert any(ln.startswith("archive: in the PR at .agents/changes/5-archives/") for ln in out)
        _the_cr_drivers_writes_hold_the_folder_then_the_absolute_archive(out)
    else:
        assert "archive: not in the PR" in out
        heading = next(i for i, ln in enumerate(out) if ln.startswith("cr-driver prompt ("))
        writes = next(ln for ln in out[heading:] if ln.startswith("  writes: "))
        assert "; " not in writes
    shown = sh("git", "status", "--porcelain", "-uall", cwd=surface).splitlines()
    assert shown and all(ln.startswith("?? projects/demo/changes/") for ln in shown)
    local = ("batch.json", "events.jsonl", "STATUS", ".lock", ".batch-number", "seat.json")
    assert not [ln for ln in shown if any(name in ln for name in local)], shown
    assert sh("git", "status", "--porcelain", "-uall", cwd=repo) == ""
    _ship_once(repo, project, chantier, monkeypatch, archived)

"""The surface's writer, its edges (spec CR-404 C.5, C.6, Q11, Q25): refusals, exclusions, times,
LFS and the board's start."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from conftest import Surface, sh
from writer_rig import QUIET, Rig

from chantier.hub import state
from chantier.hub.lock import wake
from chantier.writer import git_ops
from chantier.writer.record import TEXT_MAX, read

FOLDER_LENGTH = 235
LONG_PATH = 300  # above git for Windows' 260


@pytest.mark.parametrize(
    ("text", "is_refused"),
    [
        (" ! [rejected] HEAD -> main (non-fast-forward)", True),
        (" ! [rejected] HEAD -> main (fetch first)", True),
        (" ! [remote rejected] HEAD -> main (pre-receive hook declined)", False),
        (" ! [remote rejected] HEAD -> main (protected branch hook declined)", False),
    ],
)
def test_only_a_moved_remote_is_a_refused_push(text: str, is_refused: bool) -> None:
    assert git_ops.refused(text) is is_refused


def test_a_remote_hook_that_rejects_a_push_is_a_failed_step_not_a_retry(
    rig: Callable[[], Rig],
) -> None:
    r = rig()
    r.seat()
    r.repo.store.ensure_gitignore()
    hook = r.origin / "hooks" / "pre-receive"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text("#!/bin/sh\necho no pushes today >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    r.write("projects/demo/changes/1-inbox/idea/01-intent.md")
    r.tick()
    first = r.tick(QUIET)
    assert first["state"] == "pending" and first["failure"]["cycles"] == 1
    assert r.tick()["state"] == "blocked"
    assert r.entry()["reason"] == "git-error" and "remote rejected" in r.entry()["text"]
    assert r.types() == ["sync-blocked@1"]


@pytest.mark.parametrize("layout", ["named", "defaults", "unnamed"])
def test_the_projects_checkout_folders_are_never_staged_and_any_other_repository_blocks(
    rig: Callable[[], Rig], layout: str
) -> None:
    r = rig()
    r.seat()
    r.repo.store.ensure_gitignore()
    project = "projects/a"
    if layout == "named":
        r.write(f"{project}/checkout.yml", "repo: code\nworktrees: code.worktrees\n")
        folders = [f"{project}/code", f"{project}/code.worktrees/w"]
    elif layout == "defaults":
        project = "projects/b"  # no checkout.yml: both defaults
        r.write("projects/c/checkout.yml", "repo: code\n")  # `worktrees:` not named: the default
        folders = ["projects/b/.repo", "projects/b/.worktrees/x", "projects/c/.worktrees/y"]
        folders += ["projects/c/code"]
    else:
        r.write(f"{project}/checkout.yml", "repo: code\n")
        folders = [f"{project}/code", f"{project}/changes/1-inbox/x/clone"]
    for folder in folders:
        r.repo_at(folder)
    intent = f"{project}/changes/1-inbox/x/01-intent.md"
    r.write(intent)
    if layout == "unnamed":
        r.tick()
        entry = r.tick()
        assert (entry["state"], entry["reason"]) == ("blocked", "nested-repo")
        assert entry["text"] == f"{project}/changes/1-inbox/x/clone"
        told = r.root / project / "changes" / "forge-journal.jsonl"  # to the project that holds it
        assert [json.loads(x)["type"] for x in told.read_text(encoding="utf-8").splitlines()] == [
            "sync-blocked@1"
        ]
        assert r.git("log", "-1", "--format=%s") == "init"  # nothing committed
        return
    entry = r.until("synced")
    assert entry["state"] == "synced" and entry["reason"] == ""
    tracked = r.git("ls-files", "projects").splitlines()
    assert intent in tracked
    assert not [t for t in tracked if any(t.startswith(f + "/") for f in folders)]
    assert not r.git("diff", "--cached", "--name-only")
    assert r.types() == []


def test_a_file_that_keeps_changing_is_committed_when_max_wait_passes(
    rig: Callable[[], Rig],
) -> None:
    r = rig()
    path = "projects/demo/changes/1-inbox/idea/01-intent.md"
    for i in range(1, 5):  # 31 s apart: 0, 31, 62, 93 s since the first sight
        r.write(path, "x" * i)
        assert r.tick()["pending"] == 1
    r.write(path, "x" * 5)
    assert r.tick()["pending"] == 0  # 124 s: past the 120 s
    assert r.pushed() == r.head()


def test_only_the_plans_published_paths_are_committed(rig: Callable[[], Rig]) -> None:
    r = rig()
    r.seat()
    r.repo.store.ensure_gitignore()
    r.tick()
    changes = "projects/demo/changes"
    for rel in (f"{changes}/4-batch/batch.json", f"{changes}/forge-journal.jsonl"):
        r.write(rel, "{}\n")
    r.write("scripts/x.py")
    r.write("AGENTS.md")
    r.write("outside.txt")
    r.git("add", "outside.txt")  # staged by hand, outside the writer's paths
    r.write(f"{changes}/1-inbox/idea/01-intent.md")
    wake(r.repo.git_dir)
    r.loop.poll(r.clock + 1.0)  # the first cycle that sees the staged file: not blocked yet
    entry = r.entry()
    assert entry["state"] == "synced" and entry["last_commit"]
    shown = r.git("show", "--name-only", "--format=", "HEAD").splitlines()
    assert set(shown) == {f"{changes}/.gitignore", f"{changes}/1-inbox/idea/01-intent.md"}
    assert r.git("diff", "--cached", "--name-only") == "outside.txt"  # still staged
    assert r.types() == []
    untracked = set(r.git("ls-files", "--others", "--exclude-standard").splitlines())
    assert {"scripts/x.py", "AGENTS.md"} <= untracked


def test_a_change_still_moving_inside_the_quiet_is_committed_before_the_rebase(
    rig: Callable[[], Rig],
) -> None:
    r = rig()
    r.tick()
    r.write("projects/other/changes/1-inbox/theirs/01-intent.md", where=r.other)
    sh("git", "add", ".", cwd=r.other)
    sh("git", "commit", "-qm", "theirs", cwd=r.other)
    sh("git", "push", "-q", "origin", "main", cwd=r.other)
    r.write("projects/demo/changes/1-inbox/mine/01-intent.md", "a")
    r.tick(61.0)  # a fetch is due, the change was first seen now: inside the quiet
    assert r.entry()["state"] == "synced"
    log = r.git("log", "--format=%s", "--reverse", "-2").splitlines()
    assert log[0] == "theirs" and log[1].startswith("chantier: demo: ")  # rebased onto theirs
    assert r.pushed() == r.head()


def test_a_hand_commit_and_the_writers_commit_are_rebased_and_pushed_in_order(
    rig: Callable[[], Rig],
) -> None:
    r = rig()
    r.tick()
    r.write("AGENTS.md", "rules\n")
    r.git("add", "AGENTS.md")
    r.git("commit", "-qm", "by hand")  # H
    r.write("projects/demo/changes/1-inbox/idea/01-intent.md")  # W, committed by the writer
    r.write("projects/other/changes/1-inbox/theirs/01-intent.md", where=r.other)
    sh("git", "add", ".", cwd=r.other)
    sh("git", "commit", "-qm", "theirs", cwd=r.other)
    sh("git", "push", "-q", "origin", "main", cwd=r.other)
    r.tick(61.0)
    assert r.entry()["state"] == "synced"
    log = r.git("log", "--format=%s", "--reverse", "-3", cwd=r.origin).splitlines()
    assert log[:2] == ["theirs", "by hand"] and log[2].startswith("chantier: demo: ")


def test_one_blocked_line_per_episode_whatever_the_reason_becomes(rig: Callable[[], Rig]) -> None:
    r = rig()
    r.seat()
    r.tick()
    r.write("outside.txt")
    r.git("add", "outside.txt")
    r.tick()
    assert (r.tick()["state"], r.entry()["reason"]) == ("blocked", "staged")
    sh("git", "init", "-q", str(r.root / "projects" / "demo" / "inner"))
    assert r.tick()["reason"] == "nested-repo"  # the reason moved: the episode did not end
    assert r.types() == ["sync-blocked@1"]


def test_a_stuck_surface_is_late_once_even_while_blocked(rig: Callable[[], Rig]) -> None:
    r = rig()
    r.seat()
    r.write("projects/demo/changes/1-inbox/idea/01-intent.md")
    r.tick()
    r.git("checkout", "-q", "--detach")
    r.tick()  # blocked: not-a-branch, the change still waiting
    assert r.tick(300.0)["state"] == "blocked"
    assert r.types() == ["sync-blocked@1", "sync-late@1"]
    r.tick()
    assert r.types() == ["sync-blocked@1", "sync-late@1"]


def test_an_lfs_push_that_cannot_reach_the_lfs_server_is_offline(rig: Callable[[], Rig]) -> None:
    try:
        subprocess.run(["git", "lfs", "version"], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git lfs is not installed here (`git lfs version` fails)")
    r = rig()
    r.seat()
    r.repo.store.ensure_gitignore()
    r.write(".gitattributes", "*.png filter=lfs diff=lfs merge=lfs -text\n")
    r.git("add", ".gitattributes")
    r.git("commit", "-qm", "lfs attributes")
    r.git("lfs", "install", "--local")
    r.git("config", "lfs.url", "https://lfs.invalid/")
    r.write("projects/demo/changes/1-inbox/idea/shot.png", "not really a png\n")
    r.tick()
    entry = r.tick(QUIET)
    assert entry["state"] == "offline", entry  # not blocked: the pre-push hook found no network
    assert entry["failure"] is None


def test_a_board_started_with_no_seat_starts_the_writer(
    surface: Surface, chantier: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from chantier.board import command  # noqa: PLC0415

    git_dir = surface.root / ".git"
    state.modify(git_dir, lambda data: data.pop(state.WRITER, None))
    (surface.project / "changes").mkdir(exist_ok=True)
    seen: list[str] = []

    class Served:
        def run(self, sockets: Any) -> None:  # the server "serves" and at once stops
            seen.append(read(git_dir)["state"])

    monkeypatch.setattr(command, "make_server", lambda ctx: Served())
    code, _out, _err = chantier("serve", "--project", "demo", "--port", "0")
    assert code == 0, _err
    assert seen == ["syncing"]  # the writer ran while the server served, with no `--seat`
    assert read(git_dir)["state"] == "off"  # and went with it


def test_a_downloaded_artifact_folder_is_left_out_of_the_commit(rig: Callable[[], Rig]) -> None:
    r = rig()
    r.seat()
    r.repo.store.ensure_gitignore()
    changes = "projects/demo/changes/1-inbox/idea"
    r.write(f"{changes}/01-intent.md")
    r.write(f"{changes}/work/debugger/artifacts-123/log/a.txt")
    entry = r.until("synced")
    assert entry["state"] == "synced"
    shown = r.git("show", "--name-only", "--format=", "HEAD").splitlines()
    assert f"{changes}/01-intent.md" in shown
    assert not any("artifacts-123" in p for p in shown)


@pytest.mark.parametrize(
    ("text", "path"),
    [
        # prepared texts (no shipped file holds them): git for Windows, then the POSIX spelling
        (
            'error: open("p/a/long.txt"): Filename too long error: unable to index file '
            "'p/a/long.txt' fatal: adding files failed",
            "p/a/long.txt",
        ),
        ("error: unable to index file 'p/b.txt': File name too long", "p/b.txt"),
        ("error: Filename too long", None),
        ("fatal: pathspec 'x' did not match any files", None),
    ],
    ids=["windows", "posix", "phrase-without-path", "other-error"],
)
def test_a_failed_add_names_the_path_git_refuses_as_too_long(text: str, path: str | None) -> None:
    assert git_ops.too_long_path(("add", "-A", "--", "p"), text) == path
    assert git_ops.too_long_path(("commit", "-m", "x"), text) is None


@pytest.mark.skipif(sys.platform != "win32", reason="git for Windows refuses a path above 260")
def test_a_real_path_too_long_blocks_with_its_reason_then_resumes(rig: Callable[[], Rig]) -> None:
    r = rig()
    r.seat()
    r.git("config", "core.longpaths", "false")
    r.write("projects/demo/changes/1-inbox/idea/01-intent.md")
    assert r.settle()["state"] == "synced"  # nothing else is left to stage
    prefix = "projects/demo/changes/1-inbox/idea/work/notes/"
    # the folder is still openable (git skips a folder it cannot open, with a warning only), the
    # file inside it is not: its path is above LONG_PATH
    pad = FOLDER_LENGTH - len(str(r.root / prefix))
    rel = f"{prefix}{'d' * pad}/{'f' * 70}.txt"
    file = Path("\\\\?\\" + str(r.root / rel).replace("/", "\\"))
    assert len(str(r.root / rel)) > LONG_PATH
    file.parent.mkdir(parents=True)
    file.write_text("x\n", encoding="utf-8")
    r.tick()
    entry = r.tick(QUIET)
    assert entry["state"] == "pending" and entry["failure"]["cycles"] == 1
    assert r.lines() == []
    entry = r.tick()
    assert entry["state"] == "blocked" and entry["reason"] == "path-too-long"
    assert entry["text"].startswith(f"{len(str(r.root / rel))} characters: {prefix}")
    assert len(entry["text"]) <= TEXT_MAX
    r.tick()
    assert r.types().count("sync-blocked@1") == 1
    file.unlink()
    assert r.until("synced")["state"] == "synced"
    resumed = [x for x in r.lines() if x["type"] == "sync-resumed@1"]
    assert [x["after"] for x in resumed] == ["blocked"]

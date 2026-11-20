"""The surface's writer (spec CR-404 C.5 to C.7): its cycle over a real surface and a real bare
origin."""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from conftest import sh
from writer_rig import QUIET, Rig

from chantier.core.git import git as real_git
from chantier.hub import state
from chantier.hub.lock import WriterLock, wake
from chantier.writer.loop import WriterLoop


def test_a_change_is_committed_after_the_quiet_and_pushed_in_the_c_locale(
    rig: Callable[[], Rig], monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict[str, str]] = []
    called: list[tuple[str, ...]] = []

    def spy(*args: str, **kw: Any) -> str:
        seen.append(kw.get("env") or {})
        called.append(args)
        return real_git(*args, **kw)

    monkeypatch.setattr("chantier.writer.git_ops.git", spy)
    r = rig()
    assert r.loop.start() is None
    assert r.entry()["state"] == "syncing"
    r.write("projects/demo/changes/1-inbox/idea/01-intent.md")
    assert r.tick()["state"] == "pending"
    assert r.entry()["pending"] == 1
    assert r.tick(QUIET)["pending"] == 0  # quiet: committed, and pushed in the same cycle
    done = r.entry()
    assert done["state"] == "synced" and done["ahead"] == 0
    assert done["last_commit"]["sha"] == done["last_push"]["sha"] == r.head() == r.pushed()
    assert r.git("log", "-1", "--format=%s").startswith("chantier: demo: ")
    assert r.types() == []  # a quiet success tells nothing
    assert seen and all(e.get("LC_ALL") == "C" and e.get("LANGUAGE") == "C" for e in seen)
    flags = {"--force", "-f", "--no-verify", "--force-with-lease"}
    assert not [c for c in called if flags & set(c)]  # nothing forced, no hook skipped


def test_another_machines_commit_is_integrated_before_the_push(rig: Callable[[], Rig]) -> None:
    r = rig()
    r.write("projects/demo/changes/1-inbox/mine/01-intent.md")
    r.write("projects/demo/changes/1-inbox/theirs/01-intent.md", where=r.other)
    sh("git", "add", ".", cwd=r.other)
    sh("git", "commit", "-qm", "theirs", cwd=r.other)
    sh("git", "push", "-q", "origin", "main", cwd=r.other)
    r.tick()
    r.tick(QUIET)
    assert r.entry()["state"] == "synced"
    assert (r.root / "projects/demo/changes/1-inbox/theirs/01-intent.md").is_file()
    assert r.pushed() == r.head()
    assert r.git("log", "--format=%s", "-3").count("theirs") == 1


def test_a_conflict_aborts_the_rebase_tells_it_and_ends_when_integrated(
    rig: Callable[[], Rig],
) -> None:
    r = rig()
    r.seat()
    path = "projects/demo/changes/notes.md"
    r.write(path, "base\n")
    r.settle()
    sh("git", "pull", "-q", cwd=r.other)
    r.write(path, "theirs\n", where=r.other)
    sh("git", "commit", "-qam", "theirs", cwd=r.other)
    sh("git", "push", "-q", "origin", "main", cwd=r.other)
    r.write(path, "mine\n")
    r.tick()
    r.tick(QUIET)
    entry = r.entry()
    assert entry["state"] == "conflict"
    assert entry["conflict"]["files"] == [path]
    assert not (r.root / ".git" / "rebase-merge").exists()
    assert r.types() == ["sync-conflict@1"]
    assert (r.root / path).read_text(encoding="utf-8") == "mine\n"  # no marker, no git write
    before = r.head()
    r.tick()
    assert r.entry()["state"] == "conflict" and r.head() == before  # waits for the integration
    sh("git", "fetch", "-q", cwd=r.root)
    r.write(path, "theirs\n")
    sh("git", "checkout", "--", path, cwd=r.root)
    sh("git", "reset", "-q", "--hard", "origin/main", cwd=r.root)
    r.tick()
    r.tick()
    assert r.entry()["state"] == "synced"
    assert r.types() == ["sync-conflict@1", "sync-resumed@1"]


@pytest.mark.parametrize(
    ("setup", "reason"),
    [
        ("detach", "not-a-branch"),
        ("no-upstream", "no-upstream"),
        ("staged", "staged"),
        ("nested", "nested-repo"),
        ("busy", "git-busy"),
        ("foreign", "foreign-autosync"),
    ],
)
def _tool(r: Rig) -> Path:
    return r.root / ".git" / "ai-autosync"


def _foreign(r: Rig) -> None:
    _tool(r).mkdir()
    (_tool(r) / "control.json").write_text('{"enabled": true}', encoding="utf-8")
    (_tool(r) / "watcher.json").write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")


def _inner(r: Rig) -> Path:
    return r.root / "projects" / "demo" / "inner"


def _unnest(r: Rig) -> None:
    shutil.rmtree(_inner(r) / ".git", ignore_errors=True)
    shutil.rmtree(_inner(r))


def _stage(r: Rig) -> None:
    r.write("outside.txt")
    r.git("add", "outside.txt")


def _merge_head(r: Rig) -> Path:
    return r.root / ".git" / "MERGE_HEAD"


# a precondition's reason: how to break it, how to mend it
BREAKS: dict[str, tuple[Callable[[Rig], object], Callable[[Rig], object]]] = {
    "detach": (
        lambda r: r.git("checkout", "-q", "--detach"),
        lambda r: r.git("checkout", "-q", "main"),
    ),
    "no-upstream": (
        lambda r: r.git("branch", "--unset-upstream"),
        lambda r: r.git("branch", "-u", "origin/main"),
    ),
    "staged": (_stage, lambda r: r.git("reset", "-q", "outside.txt")),
    "nested": (lambda r: sh("git", "init", "-q", str(_inner(r)), cwd=r.root), _unnest),
    "foreign": (_foreign, lambda r: shutil.rmtree(_tool(r))),
    "busy": (lambda r: _merge_head(r).write_text(r.head()), lambda r: _merge_head(r).unlink()),
}


@pytest.mark.parametrize(
    ("setup", "reason"),
    [
        ("detach", "not-a-branch"),
        ("no-upstream", "no-upstream"),
        ("staged", "staged"),
        ("nested", "nested-repo"),
        ("busy", "git-busy"),
        ("foreign", "foreign-autosync"),
    ],
)
def test_a_precondition_blocks_with_one_line_and_resumes(
    rig: Callable[[], Rig], setup: str, reason: str
) -> None:
    r = rig()
    r.seat()
    r.tick()
    breaks, mends = BREAKS[setup]
    breaks(r)
    r.tick()
    entry = r.tick()  # the staged rule asks two cycles
    assert (entry["state"], entry["reason"]) == ("blocked", reason)
    r.tick()
    assert r.types() == ["sync-blocked@1"]  # once for the episode
    mends(r)
    assert r.tick()["state"] != "blocked"
    assert r.types() == ["sync-blocked@1", "sync-resumed@1"]


def test_an_unreachable_origin_is_offline_late_once_and_resumes(
    rig: Callable[[], Rig], tmp_path: Path
) -> None:
    r = rig()
    r.seat()
    r.write("projects/demo/changes/1-inbox/idea/01-intent.md")
    r.settle()
    moved = tmp_path / "gone.git"
    r.origin.rename(moved)
    r.write("projects/demo/changes/1-inbox/idea/02-more.md")
    r.tick()
    r.tick(QUIET)
    entry = r.entry()
    assert entry["state"] == "offline" and entry["ahead"] == 1
    assert entry["failure"] is None  # offline is not a failed step
    assert r.tick()["state"] == "offline"  # retried at the next cycle, not blocked
    assert r.types() == []  # offline tells no one by itself
    assert r.tick(300.0)["state"] == "offline"  # the 5 minutes of the oldest commit are past
    assert r.types() == ["sync-late@1"]
    r.tick()
    assert r.types() == ["sync-late@1"]  # once for the episode
    moved.rename(r.origin)
    assert r.tick()["state"] == "synced"
    assert r.types() == ["sync-late@1", "sync-resumed@1"]
    assert r.lines()[-1]["after"] == "offline"
    assert r.pushed() == r.head()


def test_a_failed_git_step_waits_a_cycle_then_blocks_once_and_resumes(
    rig: Callable[[], Rig],
) -> None:
    r = rig()
    r.seat()
    r.repo.store.ensure_gitignore()  # else its first appearance moves the changes again
    hook = r.root / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text("#!/bin/sh\necho refused by the hook >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)  # git skips a hook with no exec bit on POSIX
    r.git("config", "core.hooksPath", str(hook.parent))
    r.write("projects/demo/changes/1-inbox/idea/01-intent.md")
    r.tick()
    first = r.tick(QUIET)
    assert first["state"] == "pending" and first["failure"]["cycles"] == 1
    assert r.types() == []
    second = r.tick()
    assert second["state"] == "blocked" and second["reason"] == "git-error"
    assert "refused by the hook" in second["text"]
    r.tick()
    assert r.types() == ["sync-blocked@1"]
    hook.unlink()
    assert r.tick()["state"] == "synced"
    assert r.types() == ["sync-blocked@1", "sync-resumed@1"]
    assert r.lines()[-1]["after"] == "blocked"


def test_a_stash_git_cannot_reapply_blocks_at_once_and_is_never_touched(
    rig: Callable[[], Rig],
) -> None:
    r = rig()
    r.seat()
    r.write("outside.md", "a\n")  # a tracked file outside the writer's paths
    r.git("add", "outside.md")
    r.git("commit", "-qm", "outside")
    r.git("push", "-q", "origin", "main")
    r.tick()
    sh("git", "pull", "-q", cwd=r.other)
    r.write("outside.md", "theirs\n", where=r.other)
    sh("git", "commit", "-qam", "outside theirs", cwd=r.other)
    sh("git", "push", "-q", "origin", "main", cwd=r.other)
    r.write("outside.md", "mine\n")  # unstaged, in the way of the incoming change
    r.tick()
    entry = r.entry()
    assert entry["state"] == "blocked" and "stash@{0}" in entry["text"]
    assert r.types() == ["sync-blocked@1"]
    stash = r.git("stash", "list")
    assert stash
    r.tick()
    assert r.git("stash", "list") == stash  # never popped, applied or dropped


def test_hand_commits_are_pushed_with_nothing_pending(rig: Callable[[], Rig]) -> None:
    r = rig()
    r.tick()
    r.write("projects/demo/changes/1-inbox/hand/01-intent.md")
    r.git("add", ".")
    r.git("commit", "-qm", "by hand")
    entry = r.tick()
    assert entry["state"] == "synced" and entry["pending"] == 0
    assert r.pushed() == r.head()


def test_the_wake_file_runs_a_cycle_now(rig: Callable[[], Rig]) -> None:
    r = rig()
    r.tick()
    r.write("projects/demo/changes/1-inbox/idea/01-intent.md")
    r.loop.poll(r.clock + 1.0)  # not due
    assert r.entry()["pending"] == 0
    wake(r.repo.git_dir)
    r.loop.poll(r.clock + 2.0)
    assert r.entry()["state"] == "synced"  # asked: committed at once, without the quiet
    assert r.pushed() == r.head()


def test_the_final_cycle_commits_and_pushes_and_removes_the_entry(rig: Callable[[], Rig]) -> None:
    r = rig()
    r.tick()
    r.write("projects/demo/changes/1-inbox/idea/01-intent.md")
    r.loop.stop()
    assert r.entry()["state"] == "off"
    assert state.read(r.repo.git_dir).get("writer") is None
    assert r.pushed() == r.head()
    assert WriterLock(r.repo.git_dir).acquire()  # the lock is let go


def test_a_second_loop_does_not_get_the_lock(rig: Callable[[], Rig]) -> None:
    r = rig()
    assert r.loop.start() is None
    second = WriterLoop(r.repo)
    reason = second.start()
    assert reason and "writer.lock" in reason
    second.poll(1.0)
    assert second.writer is None and r.entry()["pid"] == state.read(r.repo.git_dir)["writer"]["pid"]


def test_an_unknown_default_branch_names_the_command_that_reads_it() -> None:
    from chantier.writer import blocking  # noqa: PLC0415

    found = blocking.blocking(None, blocking.Look(branch="main"), "", set(), False)  # type: ignore[arg-type]
    assert found is not None and found[0] == "not-a-branch"
    assert "git remote set-head origin -a" in found[1] and "unknown" not in found[1]

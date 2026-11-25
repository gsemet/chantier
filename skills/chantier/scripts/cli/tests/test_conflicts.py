"""`chantier conflicts`: the early conflict check of a parallel batch, run by `git merge-tree`
only, one note per conflicting pair, the ask printed and never recorded, a refusal on an old
git, nothing run in a stack or a series batch. The shipped `src/` runs, on a real repository."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import changes, open_batch, record, write_record
from conftest import Chantier, sh

from chantier.core import git
from chantier.core.errors import EXIT_CONFLICT, EXIT_PRECONDITION

PR = "https://github.com/acme/demo/pull/{}"
BASE_FILES = ("shared.py", "other.py", *(f"f{i}.py" for i in range(1, 8)))
COMMIT = ("git", "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q")


def _branch(repo: Path, name: str, files: dict[str, str]) -> None:
    sh("git", "checkout", "-q", "-b", name, "main", cwd=repo)
    for path, text in files.items():
        (repo / path).write_text(text, encoding="utf-8")
    sh("git", "add", *files, cwd=repo)
    sh(*COMMIT, "-m", name, cwd=repo)
    sh("git", "checkout", "-q", "main", cwd=repo)


def _world(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    clash: tuple[str, ...] = ("shared.py",),
) -> list[str]:
    """A parallel batch of three CRs, ready with a PR and a branch: A and B change `clash` in
    different ways, C changes another file. Returns the ids."""
    for path in BASE_FILES:
        (repo / path).write_text("base\n", encoding="utf-8")
    sh("git", "add", *BASE_FILES, cwd=repo)
    sh(*COMMIT, "-m", "files", cwd=repo)
    ids = open_batch(repo, chantier, monkeypatch, "Cr a", "Cr b", "Cr c")
    _branch(repo, "br-a", {f: "from a\n" for f in clash})
    _branch(repo, "br-b", {f: "from b\n" for f in clash})
    _branch(repo, "br-c", {"other.py": "from c\n"})
    data = record(repo)
    for i, (c, name) in enumerate(zip(data["crs"], ("br-a", "br-b", "br-c"), strict=True)):
        c.update(status="ready", pr=PR.format(i + 1), branch=name)
    write_record(repo, data)
    return ids


def _crs(repo: Path) -> list[dict[str, Any]]:
    crs: list[dict[str, Any]] = record(repo)["crs"]
    return crs


def _events(repo: Path) -> list[dict[str, Any]]:
    path = changes(repo) / "4-batch" / "events.jsonl"
    return [json.loads(x) for x in path.read_text("utf-8").splitlines()]


def _state(repo: Path) -> list[str]:
    """Everything a trial merge must leave alone."""
    return [
        sh("git", "for-each-ref", cwd=repo),
        sh("git", "worktree", "list", "--porcelain", cwd=repo),
        sh("git", "status", "--porcelain", cwd=repo),
        sh("git", "stash", "list", cwd=repo),
        str((repo / ".git" / "rebase-merge").exists() or (repo / ".git" / "rebase-apply").exists()),
    ]


def _frozen(repo: Path) -> tuple[Any, bytes]:
    events = changes(repo) / "4-batch" / "events.jsonl"
    return record(repo), events.read_bytes() if events.is_file() else b""


def test_a_conflicting_pair_is_noted_once_and_asked_not_recorded_and_the_repository_untouched(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b, c = _world(repo, chantier, monkeypatch)
    slug = {x["id"]: Path(x["path"]).name.split("-", 1)[1] for x in _crs(repo)}
    before, asks, notes = _state(repo), record(repo)["asks"], [x["notes"] for x in _crs(repo)]
    code, out, err = chantier("conflicts", b, "--epoch", 1)
    assert code == 0, err
    assert f"{b} x {a}: conflict in shared.py; noted" in out
    assert f"{b} x {c}: clean" in out
    assert out[0].startswith(f"conflicts: {b} against 2 ready PR(s): 1 in conflict, 1 clean")
    want = f"conflict {b} {slug[b]} with {a} {slug[a]}: shared.py; switch to a stack?"
    assert out[-1] == f'next: asks "{want}"'
    assert _crs(repo)[1]["notes"] == [*notes[1], f"early conflict: with {a}: shared.py"]
    assert [_crs(repo)[0]["notes"], _crs(repo)[2]["notes"]] == [notes[0], notes[2]]
    assert record(repo)["asks"] == asks  # printed, not recorded
    assert sum(1 for e in _events(repo) if e["kind"] == "note") == 1
    assert _state(repo) == before  # no ref, worktree, index change, stash or rebase
    code, out, err = chantier("conflicts", b, "--epoch", 1)
    assert code == 0, err
    assert f"{b} x {a}: skipped: already noted" in out
    assert not [ln for ln in out if ln.startswith("next:")]
    assert len([n for n in _crs(repo)[1]["notes"] if n.startswith("early conflict")]) == 1
    # an old-card Foreman's note on B makes the pair skipped from A's side too
    data = record(repo)
    data["crs"][0]["notes"] = [f"early conflict: with {b}: shared.py"]
    data["crs"][1]["notes"] = []
    write_record(repo, data)
    code, out, _ = chantier("conflicts", a, "--epoch", 1)
    assert code == 0
    assert f"{a} x {b}: skipped: already noted" in out
    assert f"{a} x {c}: clean" in out


def test_paths_over_five_are_cut_in_the_note_and_all_named_in_the_ask(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    clash = tuple(f"f{i}.py" for i in range(1, 8))
    a, b, _ = _world(repo, chantier, monkeypatch, clash)
    code, out, err = chantier("conflicts", b, "--epoch", 1)
    assert code == 0, err
    assert _crs(repo)[1]["notes"][-1] == (
        f"early conflict: with {a}: f1.py, f2.py, f3.py, f4.py, f5.py and 2 more"
    )
    assert f"{', '.join(clash)}; switch to a stack?" in out[-1]


@pytest.mark.parametrize(
    ("case", "chained"),
    [
        ("after", True),
        ("start_on", True),
        ("pr_base", False),
        ("working", False),
        ("merged", False),
    ],
)
def test_pairs_left_out_cost_no_git_call(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    chained: bool,
) -> None:
    a, b, c = _world(repo, chantier, monkeypatch)
    data = record(repo)
    one, two = data["crs"][0], data["crs"][1]
    if case == "after":
        two["after"] = [a]
    elif case == "start_on":
        two["start_on"] = "br-a"
    elif case == "pr_base":
        one["pr_base"] = "feature"
    else:
        one["status"] = case
    write_record(repo, data)
    calls: list[tuple[str, ...]] = []
    real = git.run

    def counting(*args: str, cwd: Path | str | None = None) -> tuple[int, str, str]:
        if args[0] == "merge-tree":
            calls.append(args[-2:])
        return real(*args, cwd=cwd)

    monkeypatch.setattr(git, "run", counting)
    code, out, err = chantier("conflicts", b, "--epoch", 1)
    assert code == 0, err
    assert calls == [("br-b", "br-c")]
    if chained:
        assert f"{b} x {a}: skipped: chained" in out
    else:
        assert not [ln for ln in out if f"{b} x {a}" in ln]
    assert f"{b} x {c}: clean" in out


@pytest.mark.parametrize(
    "case",
    ["missing branch", "working", "no pr", "stack", "series", "no epoch", "stale epoch"],
)
def test_not_run_and_refusals(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    a, b, _ = _world(repo, chantier, monkeypatch)
    data = record(repo)
    if case == "missing branch":
        data["crs"][0]["branch"] = "no-such-branch"
    elif case == "working":
        data["crs"][1]["status"] = "working"
    elif case == "no pr":
        data["crs"][1]["pr"] = None
    elif case in ("stack", "series"):
        data["mode"] = case
    write_record(repo, data)
    before = _frozen(repo)
    args = {"no epoch": (), "stale epoch": ("--epoch", 7)}.get(case, ("--epoch", 1))
    code, out, err = chantier("conflicts", b, *args)
    if case == "missing branch":
        assert code == 0, err
        note = _crs(repo)[1]["notes"][-1]
        assert note.startswith(f"early conflict check: not run against {a}: ")
        assert f"{b} x {a}: not run: " in "\n".join(out)
        assert not [ln for ln in out if ln.startswith("next:")]
        return
    assert _frozen(repo) == before
    if case in ("stack", "series"):
        assert code == 0, err
        assert len(out) == 1 and f"is a {case} batch" in out[0]
    else:
        want = EXIT_CONFLICT if case == "stale epoch" else EXIT_PRECONDITION
        assert code == want, (out, err)


@pytest.mark.parametrize(
    "text", ["git version 2.37.1", "git version 2.37.1.windows.1", "not git at all"]
)
def test_an_older_or_unreadable_git_refuses_before_anything_is_read_or_written(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    _, b, _ = _world(repo, chantier, monkeypatch)
    before = _frozen(repo)
    ran: list[str] = []

    def fake(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        ran.append(cmd[-1])
        return subprocess.CompletedProcess(cmd, 0, f"{text}\n", "")

    monkeypatch.setattr(subprocess, "run", fake)
    code, _, err = chantier("conflicts", b, "--epoch", 1)
    assert code == EXIT_PRECONDITION
    assert "2.38" in err
    assert ("cannot read git's version" in err) == text.startswith("not")
    assert ran == ["--version"]  # no merge-tree ran
    assert _frozen(repo) == before


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("git version 2.56.0.windows.4", (2, 56, 0)),
        ("git version 2.38.0", (2, 38, 0)),
        ("git version 2.40", (2, 40, 0)),
        ("nope", None),
    ],
)
def test_the_git_version_parses(text: str, want: tuple[int, int, int] | None) -> None:
    assert git.parse_version(text) == want

"""A Driver's prompt skeleton: the table in `concepts.md` and what `take`, `take stack` and
`order qa` print from it."""

import shutil
import subprocess
from pathlib import Path

import pytest
from batch_helpers import changes, open_batch, record, write_record
from conftest import PLUGIN_ROOT, SKILL, Chantier
from test_plugin_files import DRIVERS, _front, agent_file

from chantier.core import files
from chantier.core.errors import EXIT_PRECONDITION
from chantier.driver_prompt import BACKTICKED, driver_table


@pytest.mark.parametrize("host", ["claude", "copilot"])
def test_the_drivers_prompt_table_names_each_driver_card_and_start_once(host: str) -> None:
    table = driver_table()
    assert sorted(cells[0].strip("`") for cells in table) == sorted(DRIVERS)
    started = [BACKTICKED.findall(cells[1]) for cells in table]
    assert sorted(t[0] for t in started) == ["order qa", "take <cr>", "take <cr>", "take stack"]
    assert sorted(k for t in started if t[0] == "take <cr>" for k in t[1:]) == [
        "change",
        "fix",
        "release",
    ]
    for cells in table:
        role = cells[0].strip("`")
        assert (SKILL / "references" / cells[2].strip("`")).is_file()
        assert cells[3].strip("`") == "none" or role == "cr-driver"
        assert cells[4] in {"yes", "none"}
        head = _front(agent_file(role, host))[0]["description"]
        assert "Started by the steering session" in head
        assert f"Prompt starts with: `chantier {role} for " in head


def _skeleton(out: list[str], role: str) -> list[str]:
    """The Driver's skeleton in a command's output: its heading, then the indented lines."""
    start = next(i for i, ln in enumerate(out) if ln.startswith(f"{role} prompt ("))
    end = start + 1
    while end < len(out) and out[end].startswith("  "):
        end += 1
    return out[start:end]


def _worker_writes_line_and_scratch(out: list[str], block: list[str]) -> None:
    """The facts print a bare `writes:` line for the workers and the Verifier's scratch folder."""
    facts = next(ln for ln in out if ln.startswith("folder: "))
    folder = facts.removeprefix("folder: ").removesuffix(" (work/, evidence/)")
    heading = "worker writes line (copy it unchanged, without the two leading spaces, into each "
    at = next(i for i, ln in enumerate(out) if ln.startswith(heading))
    assert out[at + 1].startswith("  writes: ") and "(" not in out[at + 1]
    assert [ln for ln in out if ln.lstrip().startswith("writes:")].count(out[at + 1]) == 1
    worktree, cr_folder = out[at + 1].removeprefix("  writes: ").split("; ")
    assert Path(worktree).is_absolute() and Path(cr_folder).is_absolute() and cr_folder == folder
    wt_line = next(ln for ln in out if ln.startswith("worktree: "))
    assert wt_line.removeprefix("worktree: ").split(" branch ")[0].replace("\\", "/") == worktree
    scratch = out[out.index(facts) + 1]
    assert scratch == f"scratch: {folder}/work/scratch"
    assert f"    {out[at + 1].strip()}" in block


@pytest.mark.parametrize("which", ["change", "release", "stack", "qa"])
def test_the_commands_print_each_drivers_prompt_skeleton_without_a_writes_line_for_most(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, which: str
) -> None:
    mode = ("--mode", "stack") if which == "stack" else ()
    ids = open_batch(repo, chantier, monkeypatch, "One", "Two", args=mode)
    batch, root = record(repo)["id"], repo.resolve().as_posix()
    if which == "release":
        d = record(repo)
        d["crs"][0]["kind"] = "release"
        write_record(repo, d)
    args = {
        "change": ("take", "CR-101", "--note", "why", "--epoch", 1),
        "release": ("take", "CR-101", "--note", "why", "--epoch", 1),
        "stack": ("take", "stack", "--note", "why", "--epoch", 1),
        "qa": ("order", "qa", "--note", "test it"),
    }[which]
    code, out, err = chantier(*args)
    assert code == 0, err
    role = {"change": "cr-driver", "release": "release-driver"}.get(which, f"{which}-driver")
    block = _skeleton(out, role)
    writes = [ln for ln in block if ln.startswith("  writes:")]
    teams = [ln for ln in block if ln.startswith("  Team:")]
    start = "(copy it whole" if which == "change" else "(no writes: line"
    assert block[0].startswith(f"{role} prompt {start}")
    assert block[2].startswith("  Read ") and block[3].startswith("  Read ")
    assert block[3].endswith("/driver.md;") and "  CLI ($CHANTIER): " in block[5]
    assert any(ln.startswith("  Steering: the Foreman ") for ln in block)
    assert len(teams) == (1 if which in {"change", "stack"} else 0)
    folder = out[1].removeprefix("QA folder: ").split(";")[0]
    target = {
        "change": f'for CR-101 "One" of batch {batch}',
        "release": f'for CR-101 "One" of batch {batch}',
        "stack": f"for the stack of batch {batch}",
        "qa": f"for {folder} of batch {batch}",
    }[which]
    assert block[1] == f"  chantier {role} {target}, in the project {root}."
    assert block[-1] == f"  Note: {'test it' if which == 'qa' else 'why'}"
    if which == "change":
        folder = next(ln for ln in out if ln.startswith("folder: ")).split(" (")[0]
        assert writes == [f"  writes: {folder.removeprefix('folder: ')}"]
        _worker_writes_line_and_scratch(out, block)
        assert [ln[2:] for ln in block if ln[2:].startswith("writes:")] == [writes[0][2:]]
    else:
        assert not writes
    if which == "stack":
        rows = [ln for ln in out[: out.index(block[0])] if ln.startswith(("the stack of", "CR-"))]
        assert len(rows) == len(ids) + 1 and all(f"  {ln}" in block for ln in rows)
    if which == "qa":
        assert out.index(block[0]) > 1
        assert f"  QA folder: {folder}; order O-1" in block and "  default branch: main" in block


@pytest.mark.parametrize("missing", ["qa-driver", "cr-driver"])
def test_a_driver_role_with_no_agent_file_is_refused_before_anything_is_recorded(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, missing: str
) -> None:
    args = {
        "qa-driver": ("order", "qa", "--note", "test it"),
        "cr-driver": ("take", "CR-101", "--epoch", 1),
    }[missing]
    open_batch(repo, chantier, monkeypatch, "One")
    plugin = tmp_path / "plugin"
    shutil.copytree(PLUGIN_ROOT / "agents", plugin / "agents")
    shutil.copytree(PLUGIN_ROOT / "config", plugin / "config")
    (plugin / "agents" / f"{missing}.md").unlink()
    monkeypatch.setenv("CHANTIER_PLUGIN_ROOT", str(plugin))
    before = (record(repo), sorted(p.name for p in (changes(repo) / "1-inbox").glob("*")))
    code, _, err = chantier(*args)
    assert code == EXIT_PRECONDITION and missing in err and "out of step" in err
    after = (record(repo), sorted(p.name for p in (changes(repo) / "1-inbox").glob("*")))
    assert after == before


def test_a_round_prints_the_bare_worker_writes_line_and_the_template_line_holds_no_parenthesis(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_batch(repo, chantier, monkeypatch, "One")
    assert chantier("take", "CR-101", "--note", "why", "--epoch", 1)[0] == 0
    _, out, _ = chantier("round", "CR-101", "--note", "round 1")
    at = next(i for i, ln in enumerate(out) if ln.startswith("worker writes line ("))
    worktree, folder = out[at + 1].removeprefix("  writes: ").split("; ")
    assert out[at + 1].startswith("  writes: ") and "(" not in out[at + 1]
    assert Path(worktree).is_absolute() and Path(folder).is_absolute()
    assert f"scratch: {folder}/work/scratch" in out
    template = (SKILL / "references" / "concepts.md").read_text(encoding="utf-8")
    assert [ln for ln in template.splitlines() if ln.startswith("writes: <worktree>")] == [
        "writes: <worktree>; <CR folder>"
    ]


def test_the_planning_folder_ignores_a_scratch_project_and_a_call_there_leaves_the_live_one_alone(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_batch(repo, chantier, monkeypatch, "One")
    live = changes(repo)
    assert "**/work/scratch/" in (live / ".gitignore").read_text(encoding="utf-8").splitlines()
    scratch = live / "4-batch" / "2-actives" / "101-one" / "work" / "scratch" / "probe"
    scratch.mkdir(parents=True)
    (scratch / "f.txt").write_text("x", encoding="utf-8")
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", str(scratch / "f.txt")], cwd=repo, check=False
    )
    assert ignored.returncode == 0
    assert "**/work/gates/" in (live / ".gitignore").read_text(encoding="utf-8").splitlines()
    gate = live / "4-batch" / "2-actives" / "101-one" / "work" / "gates" / "out.txt"
    gate.parent.mkdir(parents=True)
    gate.write_text("x", encoding="utf-8")
    assert (
        subprocess.run(["git", "check-ignore", "-q", str(gate)], cwd=repo, check=False).returncode
        == 0
    )

    def snapshot() -> dict[str, bytes]:
        return {
            p.relative_to(live).as_posix(): p.read_bytes()
            for p in live.rglob("*")
            if p.is_file() and "scratch" not in p.relative_to(live).parts
        }

    before = snapshot()
    subprocess.run(["git", "init", "--quiet", str(scratch)], check=True)
    monkeypatch.chdir(scratch)
    code, _, err = chantier("file", "probe")
    assert code == 0, err
    assert (scratch / ".agents" / "changes" / "1-inbox").is_dir()
    assert any(p.is_file() for p in (scratch / ".agents" / "changes" / "1-inbox").rglob("*"))
    assert snapshot() == before


def test_an_old_work_gates_line_is_completed_with_the_any_depth_one(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_batch(repo, chantier, monkeypatch, "One")
    live = changes(repo)
    (live / ".gitignore").write_text("work/gates/\n", encoding="utf-8")
    files._ignored_done.clear()
    code, _, err = chantier("file", "probe")
    assert code == 0, err
    lines = (live / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert lines.count("**/work/gates/") == 1 and "work/gates/" in lines
    gate = live / "2-backlog" / "P1" / "a-cr" / "work" / "gates" / "out.txt"
    gate.parent.mkdir(parents=True)
    gate.write_text("x", encoding="utf-8")
    assert (
        subprocess.run(["git", "check-ignore", "-q", str(gate)], cwd=repo, check=False).returncode
        == 0
    )

"""A Driver's prompt: the table in `concepts.md`, the `brief:` line `take`, `take stack` and
`order qa` print, and the brief it writes."""

import re
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
from chantier.roles_data import load_roles

COMMAND_ARGUMENTS = {"<command>", "<role>", "<cr>", "<crs>", "<name>", "<rule>"}


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
        card = cells[2].strip("`")
        assert card == next(r.card for r in load_roles() if r.name == role)
        assert (SKILL / "references" / card).is_file()
        assert cells[3].strip("`") == "none" or role == "cr-driver"
        assert cells[4] in {"yes", "none"}
        assert (cells[5] == "none") == (role == "qa-driver")
        assert cells[5] in {"own branch", "batch branches", "none"}
        head = _front(agent_file(role, host))[0]["description"]
        assert "Started by the steering session" in head
        assert f"Prompt starts with: `chantier {role} for " in head


def _start_at(out: list[str]) -> int:
    """The `brief:` line that starts a Driver: the one holding its lease."""
    found = [i for i, ln in enumerate(out) if ln.startswith("brief: ") and " --lease " in ln]
    assert len(found) == 1, out
    return found[0]


def brief_of(chantier: Chantier, out: list[str]) -> tuple[list[str], list[str]]:
    """Run the `brief:` line a command printed: `(the short prompt, the brief file's facts)`."""
    line = out[_start_at(out)]
    code, short, err = chantier("brief", *line.rsplit(" brief ", 1)[1].split())
    assert code == 0, err
    return short, brief_facts(short)


def _worker_writes_line_and_scratch(chantier: Chantier, batch: str) -> None:
    """A worker's brief prints a bare `writes:` line and the Verifier's scratch folder."""
    code, out, err = chantier("brief", "coder", "CR-101", "--batch", batch)
    assert code == 0, err
    facts = brief_facts(out)
    folder = next(ln for ln in facts if ln.startswith("folder: "))
    folder = folder.removeprefix("folder: ").removesuffix(" (work/, evidence/)")
    writes = [ln for ln in facts if ln.startswith("writes: ")]
    assert len(writes) == 1 and writes[0] in out and "(" not in writes[0]
    worktree, cr_folder = writes[0].removeprefix("writes: ").split("; ")
    assert Path(worktree).is_absolute() and Path(cr_folder).is_absolute() and cr_folder == folder
    wt_line = next(ln for ln in facts if ln.startswith("worktree: "))
    assert wt_line.removeprefix("worktree: ").split(" branch ")[0].replace("\\", "/") == worktree
    assert f"scratch: {folder}/work/scratch" in facts


def brief_facts(short: list[str]) -> list[str]:
    path = Path(short[-1].removeprefix("Read ").removesuffix(" whole, first."))
    text = path.read_text(encoding="utf-8")
    return text.split("\n\n=== facts\n", 1)[1].split("\n\n=== host rows: ", 1)[0].split("\n")


def _check_rewrites(facts: list[str], which: str) -> None:
    """The `Rewrites:` line: none for qa, else once between `writes:` (or the lease line) and
    `Steering:`, naming the branch the `worktree:` line printed (change, release)."""
    rewrites = [i for i, ln in enumerate(facts) if ln.startswith("Rewrites: ")]
    if which == "qa":
        assert not rewrites
        return
    assert len(rewrites) == 1 and facts[rewrites[0] + 1].startswith("Steering: ")
    line = facts[rewrites[0]]
    assert "--force-with-lease" not in line and "pre-authorized by the playbook" in line
    assert "never the default branch" in line and "rebase --exec" in line
    assert facts[rewrites[0] - 1].startswith("writes:") == (which == "change")
    if which != "stack":
        worktree = next(ln for ln in facts if ln.startswith("worktree: "))
        path, rest = worktree.removeprefix("worktree: ").split(" branch ")
        branch, base = rest.split(" base ")
        base = base.split(";")[0]
        assert f"git -C {path} rebase {base}, then" in line
        assert "then $CHANTIER push CR-101 --lease 1, one command each" in line
        assert "--unit stack" not in line
        assert f"({branch})" in line
    else:
        assert "each CR branch of the stack listed above (chantier/*)" in line
        assert "git -C its row's worktree rebase its row's base, then" in line
        assert "push with its row's CR --lease 1 --unit stack, one command per" in line


@pytest.mark.parametrize("which", ["change", "release", "stack", "qa"])
def test_the_commands_print_each_drivers_brief_line_and_its_brief_holds_the_prompt(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, which: str
) -> None:
    mode = ("--mode", "stack") if which == "stack" else ()
    ids = open_batch(repo, chantier, monkeypatch, "One", "Two", args=mode)
    batch = record(repo)["id"]
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
    unit = {"stack": "stack", "qa": "O-1"}.get(which, "CR-101")
    at = _start_at(out)
    assert f" brief {role} {unit} --lease 1 --batch {batch}" in out[at]
    assert out[at - 1].startswith("lease: ")
    assert out[at + 1] == (
        "next: run it and pass its output, unchanged, as the Driver's whole prompt"
    )
    _check_prompt_and_facts(chantier, out, (which, repo, ids))


def _check_prompt_and_facts(
    chantier: Chantier, out: list[str], case: tuple[str, Path, list[str]]
) -> None:
    """The short prompt's first line and the brief's facts, for one kind of Driver."""
    which, repo, ids = case
    at = _start_at(out)
    role = out[at].rsplit(" brief ", 1)[1].split()[0]
    batch, root = record(repo)["id"], repo.resolve().as_posix()
    short, facts = brief_of(chantier, out)
    folder = out[1].removeprefix("QA folder: ").split(";")[0]
    target = {
        "change": f'for CR-101 "One" of batch {batch}',
        "release": f'for CR-101 "One" of batch {batch}',
        "stack": f"for the stack of batch {batch}",
        "qa": f"for {folder} of batch {batch}",
    }[which]
    assert short[0] == f"chantier {role} {target}, in the project {root}."
    assert any(ln.startswith("CLI ($CHANTIER): ") for ln in facts)
    assert any(ln.startswith("Steering: the Foreman ") for ln in facts)
    assert sum(ln.startswith("Team:") for ln in facts) == int(which in {"change", "stack"})
    # nothing is left to fill: the only `<…>` are the arguments of a command the Driver types
    assert set(re.findall(r"<[^<>\n]+>", "\n".join(facts))) <= COMMAND_ARGUMENTS
    _check_rewrites(facts, which)
    assert facts[-1] == f"Note: {'test it' if which == 'qa' else 'why'}"
    writes = [ln for ln in facts if ln.startswith("writes:")]
    if which == "change":
        folder = next(ln for ln in facts if ln.startswith("folder: ")).split(" (")[0]
        assert writes == [f"writes: {folder.removeprefix('folder: ')}"]
        assert writes[0] in short
        _worker_writes_line_and_scratch(chantier, batch)
    else:
        assert not writes
    if which == "stack":
        rows = [ln for ln in out[:at] if ln.startswith(("the stack of", "CR-"))]
        assert len(rows) == len(ids) + 1 and all(ln in facts for ln in rows)
    if which == "qa":
        assert f"QA folder: {folder}; order O-1" in facts and "default branch: main" in facts


PROJECT_SECTION = """
## chantier

- planning: https://example.org/surface, projects/demo
- docs-review: `docs-reviewer`, after the Inspector: every new option is
  documented in README.md
- coder: `a-role-is-no-review-step`
- style-review: `strict-reviewer`, after the Inspector: the house style
- release: RELEASING.md

## Other

- late-review: outside the section
"""
STEPS = (
    "; review step docs-review: `docs-reviewer`, after the Inspector: every new option is "
    "documented in README.md; review step style-review: `strict-reviewer`, after the "
    "Inspector: the house style"
)


@pytest.mark.parametrize(
    ("which", "team", "steps"),
    [
        ("change", False, False),
        ("change", True, False),
        ("change", False, True),
        ("stack", True, True),
    ],
)
def test_a_drivers_team_line_holds_the_configured_team_then_the_extra_review_steps(  # noqa: PLR0913, PLR0917 - one prepared state per row
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    which: str,
    team: bool,
    steps: bool,
) -> None:
    if team:
        (repo / "chantier.yaml").write_text(
            "hosts:\n  claude:\n    roles:\n      coder:\n        model: opus\n", encoding="utf-8"
        )
    if steps:
        with (repo / "AGENTS.md").open("a", encoding="utf-8") as f:
            f.write(PROJECT_SECTION)
    mode = ("--mode", "stack") if which == "stack" else ()
    open_batch(repo, chantier, monkeypatch, "One", "Two", args=mode)
    target = "stack" if which == "stack" else "CR-101"
    code, out, err = chantier("take", target, "--note", "why", "--epoch", 1)
    assert code == 0, err
    _, facts = brief_of(chantier, out)
    found = [ln.removeprefix("Team: ") for ln in facts if ln.startswith("Team: ")]
    assert len(found) == 1
    who = found[0].removesuffix(STEPS) if steps else found[0]
    assert found[0].endswith(STEPS) == steps and "review step" not in who
    printed = [ln.removeprefix("team: ") for ln in facts if ln.startswith("team: ")]
    if not team:
        assert who == "the plugin's agents" and not printed
    else:
        assert who.startswith("coder model=") and "[repository]" in who
        assert which == "stack" or who == "; ".join(printed)


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


def test_a_round_prints_the_workers_line_and_the_template_line_holds_no_parenthesis(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_batch(repo, chantier, monkeypatch, "One")
    batch = record(repo)["id"]
    assert chantier("take", "CR-101", "--note", "why", "--epoch", 1)[0] == 0
    _, out, _ = chantier("round", "CR-101", "--note", "round 1")
    workers = [ln for ln in out if ln.startswith("workers: ")]
    assert len(workers) == 1
    assert workers[0].startswith(f"workers: $CHANTIER brief <role> CR-101 --batch {batch} (")
    assert any(ln.startswith("scratch: ") and ln.endswith("/work/scratch") for ln in out)
    _worker_writes_line_and_scratch(chantier, batch)
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

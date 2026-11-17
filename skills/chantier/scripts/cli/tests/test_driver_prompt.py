"""A Driver's prompt skeleton: the table in `concepts.md` and what `take`, `take stack` and
`order qa` print from it."""

import shutil
from pathlib import Path

import pytest
from batch_helpers import changes, open_batch, record, write_record
from conftest import PLUGIN_ROOT, SKILL, Chantier
from test_plugin_files import DRIVERS, _front, agent_file

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

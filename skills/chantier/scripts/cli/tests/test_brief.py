"""`chantier brief`: a role's whole start brief in the git folder, and the short prompt that points
at it. The worlds are built once per host and batch kind; each loops over the roles."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest
from batch_helpers import changes, host, open_batch, prepared, record, write_record
from conftest import PLUGIN_ROOT, SKILL, Chantier
from test_driver_prompt import brief_of
from test_plugin_files import agent_file

from chantier.commands.brief import CLOSING, DRIVERS
from chantier.core.errors import EXIT_PRECONDITION
from chantier.host_rows import load_rows
from chantier.role_wrappers import first_line_template
from chantier.roles_data import load_roles

ROLE_COUNT, FLOOR_BYTES = 18, 1200
REFS = SKILL / "references"
ROLES = {r.name: r for r in load_roles()}
NAMES = list(ROLES)
WORKERS = ("coder", "conflict-resolver", "debugger", "inspector", "investigator", "verifier")
FIRST = re.compile(r"Prompt starts with: `(chantier [a-z-]+ for [^`]*)`")
CAPABILITY = re.compile(r"^([a-z0-9-]+): .+ \((?:proved|untested)\)$", re.M)
# The lines of a reused builder that hold a clock-relative value would break the byte test; none
# of the builders the brief reuses prints one (`lease: N (...)` names no time, the facts print no
# age), and this reads the file for the forms such a line takes.
CLOCK = re.compile(r"\b(?:ago|in \d+ ?(?:s|sec|min)|until \d\d:\d\d|expires)\b")


def _hook(name: str) -> re.Pattern[str]:
    """The regular expression a hook function applies to a prompt, read from the shipped file."""
    ts = (PLUGIN_ROOT / "hooks" / "register.tsx").read_text(encoding="utf-8")
    body = ts[ts.index(f"function {name}(") :]
    m = re.search(r"= /(.+?)/(m?)\.exec", body)
    assert m is not None
    return re.compile(m[1], re.M if m[2] else 0)


def _wrapped(role: str, host_name: str) -> bool:
    return ROLES[role].hosts[host_name].wrapper is not None


def _norm(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def _state(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _part(text: str, start: str, end: str) -> list[str]:
    body = text.split(f"\n\n{start}", 1)[1].split("\n", 1)[1]
    return body.split(f"\n\n{end}", 1)[0].split("\n")


def _world(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, name: str, kind: str
) -> dict[str, tuple[str | None, str | None, list[str]]]:
    """A batch on `name`'s host with its Drivers taken: for each role, its `(unit, lease, take's
    lines)`. The parallel batch has a taken change CR, a taken release CR and an open QA order;
    the stack batch, its taken stack."""
    mode = ("--mode", "stack") if kind == "stack" else ()
    open_batch(repo, chantier, monkeypatch, "One", "Two", args=("--slots", "4", *mode))
    d = record(repo)
    d["host"] = name
    if kind == "parallel":
        d["crs"][1]["kind"] = "release"
    write_record(repo, d)
    host(monkeypatch, name)
    spec = prepared(repo, chantier, "Spec item").name
    taken: dict[str, tuple[str | None, str | None, list[str]]] = {}

    def take(*words: str) -> tuple[str, list[str]]:
        code, out, err = chantier(*words)
        assert code == 0, err
        lease = re.search(r"lease:? (?:stack )?(\d+)", "\n".join(out))
        assert lease is not None
        return lease[1], out

    if kind == "stack":
        n, out = take("take", "stack", "--note", "why", "--epoch", "1")
        taken["stack-driver"] = ("stack", n, out)
    else:
        n, out = take("take", "CR-101", "--note", "why", "--epoch", "1")
        taken["cr-driver"] = ("CR-101", n, out)
        taken.update({w: ("CR-101", None, out) for w in WORKERS})
        n, out = take("take", "CR-102", "--note", "why", "--epoch", "1")
        taken["release-driver"] = ("CR-102", n, out)
        code, out, err = chantier("order", "qa", "--note", "test it")
        assert code == 0, err
        taken["qa-driver"] = ("O-1", "1", out)
    for role in ("spec-writer", "spec-critic", "board-griller"):
        taken[role] = (spec, None, [])
    for role in ("retro-critic", "demo-explorer", "chief-of-staff", "griller", "foreman"):
        taken[role] = (None, None, [])
    return taken


def _run(chantier: Chantier, role: str, unit: str | None, lease: str | None) -> list[str]:
    words = ["brief", role, *([unit] if unit else [])]
    words += ["--lease", lease] if lease else []
    words += ["--epoch", "1"] if role in ("foreman", "chief-of-staff") else []
    code, out, err = chantier(*words)
    assert code == 0, f"{role}: {err}"
    return out


def _check_file(path: Path, role: str, name: str, planning: Path, rows_of: set[str]) -> str:
    """The brief file: in the git folder, LF, stable, the card first, the floor once, the facts,
    the host's rows, the closing line."""
    data = ROLES[role]
    git_dir = (planning.parents[1] / ".git").resolve()
    assert path.is_absolute() and path.parents[3] == git_dir / "chantier"
    assert path.parents[2].name == "briefs"
    raw = path.read_bytes()
    assert b"\r" not in raw
    text = raw.decode("utf-8")
    assert not CLOCK.search(text), f"{role}: a clock-relative value"
    card = _norm((REFS / data.card).resolve()).rstrip("\n")
    floor = _norm(REFS / "floor.md").rstrip("\n")
    assert text.startswith(f"{card}\n\n=== floor\n{floor}\n\n=== facts\n")
    assert text.count(floor) == 1 and text.endswith(f"\n\n{CLOSING}\n")
    rows = _part(text, "=== host rows: ", CLOSING)
    assert text.count(f"\n\n=== host rows: {name}\n") == 1
    got = {m[1] for m in CAPABILITY.finditer("\n".join(rows))}
    if role == "board-griller":
        assert rows == ["none"]
    else:
        assert got == (rows_of if data.rows is None else set(data.rows))
    return text


def _check_prompt(
    out: list[str], role: str, facts: list[str], names: tuple[str, str], took: list[str]
) -> None:
    """The short prompt: the filled first line, the hook's own reading of the other lines;
    `names`: the host and the repository's root."""
    name, root = names
    writes_re, tree_re, root_re = _hook("writesOf"), _hook("worktreeOf"), _hook("rootOf")
    template = (
        FIRST.search(agent_file(role, name).read_text("utf-8")) if _wrapped(role, name) else None
    )
    assert bool(template) == (role not in ("chief-of-staff", "griller", "foreman"))
    if template:
        fills = {"<root>": root, "<batch>": "batch-01", "<cr>": out[0].split()[3], "<title>": "One"}
        if role == "release-driver":
            fills["<title>"] = "Two"
        if role == "qa-driver":
            fills["<folder>"] = next(ln for ln in took if ln.startswith("QA folder: "))[11:]
            fills["<folder>"] = fills["<folder>"].split(";")[0]
        line = template[1]
        for key, value in fills.items():
            line = line.replace(key, value)
        assert out[0] == line and root_re.search(out[0])
    guarded = [m[1].strip() for ln in out if (m := writes_re.match(ln))]
    trees = [m[1] for ln in out if (m := tree_re.match(ln))]
    assert len(out) == (1 if template else 0) + len(guarded) + len(trees) + 1
    if role in ("cr-driver", *WORKERS):
        assert guarded == [_writes(facts, role)]
        on_take_trees = [m[1] for ln in took if (m := tree_re.match(ln))]
        assert trees == on_take_trees[:1]
    else:
        assert not guarded
        assert bool(trees) == (role == "release-driver")


def _check_driver_facts(facts: list[str]) -> None:
    """A Driver's facts hold the CLI line and the Steering line, which names the host rows."""
    assert any(ln.startswith("CLI ($CHANTIER): ") for ln in facts)
    assert "Steering: the Foreman (host means: the host rows below)" in facts


@pytest.mark.parametrize("name", ["claude", "copilot"])
@pytest.mark.parametrize("kind", ["parallel", "stack"])
def test_every_role_gets_a_stable_brief_in_the_git_folder_and_a_short_prompt(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, name: str, kind: str
) -> None:
    taken = _world(repo, chantier, monkeypatch, name, kind)
    wanted = ["stack-driver", "foreman"]
    if kind != "stack":
        wanted = [n for n in NAMES if n != "stack-driver"]
    root = repo.resolve().as_posix()
    planning = _state(changes(repo))
    all_rows = {r.capability for r in load_rows(name)}
    for role in wanted:
        unit, lease, took = taken[role]
        out = _run(chantier, role, unit, lease)
        path = Path(out[-1].removeprefix("Read ").removesuffix(" whole, first."))
        text = _check_file(path, role, name, changes(repo), all_rows)
        raw = path.read_bytes()
        assert _run(chantier, role, unit, lease) == out and path.read_bytes() == raw
        assert _state(changes(repo)) == planning  # nothing written in the planning folder
        facts = _part(text, "=== facts", "=== host rows: ")
        _check_prompt(out, role, facts, (name, root), took)
        if role in DRIVERS:
            _check_driver_facts(facts)


def _writes(facts: list[str], role: str) -> str:
    """The `writes:` value the brief's folder and worktree lines give: a worker's is the worktree
    and the CR folder, a Driver's the CR folder."""
    folder = next(ln for ln in facts if ln.startswith("folder: "))
    folder = folder.removeprefix("folder: ").removesuffix(" (work/, evidence/)")
    if role not in WORKERS:
        return folder
    tree = next(ln for ln in facts if ln.startswith("worktree: "))
    return f"{Path(tree[10:].split(' branch ')[0]).as_posix()}; {folder}"


def test_takes_brief_line_run_as_printed_prints_the_same_short_prompt(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_batch(repo, chantier, monkeypatch, "One")
    code, took, err = chantier("take", "CR-101", "--note", "why", "--epoch", "1")
    assert code == 0, err
    short, _ = brief_of(chantier, took)
    line = next(ln for ln in took if ln.startswith("brief: ") and " --lease " in ln)
    code, printed, err = chantier(*shlex.split(line.split(" chantier ", 1)[1]))
    assert code == 0, err
    batch = record(repo)["id"]
    _, direct, _ = chantier("brief", "cr-driver", "CR-101", "--lease", "1", "--batch", batch)
    assert printed == direct == short


@pytest.mark.parametrize("role", NAMES)
def test_a_role_with_no_unit_gets_a_role_only_brief(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    host(monkeypatch, "claude")
    code, out, err = chantier("brief", role)
    assert code == 0, err
    assert not any(ln.startswith(("writes:", "worktree:")) for ln in out)
    assert out[-1].startswith("Read ") and out[-1].endswith("none-" + role + ".md whole, first.")
    text = Path(out[-1].removeprefix("Read ").removesuffix(" whole, first.")).read_text("utf-8")
    assert text.count("=== floor\n") == 1 and "Repository: " in text


# The wrapped roles that get a brief file (the board's Griller gets none), and those of them whose
# wrapper also refuses a prompt that names no path to the brief or the card.
BRIEFED = [n for n in NAMES if _wrapped(n, "claude") and n != "board-griller"]
ASKS_A_PATH = (*WORKERS, "demo-explorer")


@pytest.mark.parametrize("role", BRIEFED)
def test_a_wrappers_refusal_paragraph_accepts_the_short_prompt_brief_prints(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    for name in ("claude", "copilot"):
        host(monkeypatch, name)
        out = _run(chantier, role, None, None)
        body = agent_file(role, name).read_text("utf-8")
        refusal = body[body.index("A prompt that does not start with ") :]
        assert out[0].startswith(f"chantier {role} ") and f"`chantier {role}" in refusal
        # the condition and the quoted answer both name the brief and the card, or no file at all
        times = 2 if role in ASKS_A_PATH else 0
        suffixes = re.findall(r"`<unit>(-[a-z-]+\.md)`", refusal)
        assert len(suffixes) == times and refusal.count(f"`{role}.md`") == times
        read = re.fullmatch(r"Read (.+) whole, first\.", out[-1])
        assert read is not None and all(Path(read[1]).name.endswith(s) for s in suffixes)


def test_the_refusals_name_the_word_that_is_wrong(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _world(repo, chantier, monkeypatch, "claude", "parallel")
    bad = str(repo)
    cases = [
        (("nobody",), "unknown role 'nobody'; roles: cr-driver, "),
        (("foreman", "CR-101"), "foreman has no unit"),
        (("cr-driver", "CR-101", "--lease", "9"), "lease 9 is not CR-101's live lease"),
        (("cr-driver", "CR-101"), "needs --lease"),
        (("cr-driver", "CR-102", "--lease", "1"), "is a release CR: its Driver is the release"),
        (("cr-driver", "CR-9", "--lease", "1"), "CR-9"),
        (("qa-driver", "O-7", "--lease", "1"), "O-7 is not an open QA order"),
        (("coder", "CR-101", "--lease", "1"), "--lease is for a Driver's unit only"),
        (("coder", "CR-101", "--epoch", "1"), "--epoch is for foreman and chief-of-staff only"),
        (("spec-writer", bad), "is not a CR folder"),
        (
            ("coder", "CR-101", "--cards", str(tmp_path)),
            str(tmp_path / "coder.md").replace("\\", "/"),
        ),
    ]
    for words, text in cases:
        code, out, err = chantier("brief", *words)
        assert (code, out) == (EXIT_PRECONDITION, []), (words, err)
        assert text.replace("\\", "/") in err.replace("\\", "/"), (words, err)


def test_cards_reads_the_card_and_the_floor_from_its_folder(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    host(monkeypatch, "claude")
    shipped = {}
    for role in NAMES:
        _, out, _ = chantier("brief", role)
        path = Path(out[-1].removeprefix("Read ").removesuffix(" whole, first."))
        shipped[role] = path.read_bytes()
        _, out, _ = chantier("brief", role, "--cards", str(REFS))
        assert path.read_bytes() == shipped[role]  # the same folder, the same bytes
    for name in ("floor.md", "chief-of-staff.md", "griller-skill.md", "coder.md"):
        (tmp_path / name).write_text(f"mine {name}\r\n", encoding="utf-8", newline="")
    for role, card in (("coder", "coder.md"), ("chief-of-staff", "chief-of-staff.md")):
        _, out, _ = chantier("brief", role, "--cards", str(tmp_path))
        text = Path(out[-1].removeprefix("Read ").removesuffix(" whole, first.")).read_text("utf-8")
        assert text.startswith(f"mine {card}\n\n=== floor\nmine floor.md\n\n=== facts\n")


def test_the_role_table_matches_the_shipped_wrappers_and_the_host_rows() -> None:
    assert len(ROLES) == ROLE_COUNT and list(ROLES) == NAMES
    for name, data in ROLES.items():
        assert (REFS / data.card).resolve().is_file()
        for host_name in ("claude", "copilot"):
            file = agent_file(name, host_name)
            assert file.is_file() == _wrapped(name, host_name)
            if name in WORKERS:
                assert f"Your card is `{Path(data.card).name}`" in file.read_text("utf-8")
                found = FIRST.search(file.read_text("utf-8"))
                assert found is not None and first_line_template(host_name, name) == found[1]
            known = {r.capability for r in load_rows(host_name)}
            assert set(data.rows or ()) <= known
        assert data.writes in {"none", "worktree", "cr-folder"}
    assert {n for n, r in ROLES.items() if r.unit == "cr"} >= set(WORKERS)
    assert {n for n in ROLES if not _wrapped(n, "claude")} == {
        "chief-of-staff",
        "griller",
        "foreman",
    }


def test_the_floor_is_short_lf_only_and_holds_the_ten_rules() -> None:
    raw = (REFS / "floor.md").read_bytes()
    assert len(raw) <= FLOOR_BYTES and b"\r" not in raw
    lines = raw.decode("utf-8").splitlines()
    assert lines[0] == "# The floor"
    assert [ln.split(".")[0] for ln in lines if re.match(r"\d+\. ", ln)] == [
        str(i) for i in range(1, 11)
    ]

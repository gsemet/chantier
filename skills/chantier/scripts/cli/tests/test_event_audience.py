"""The addressed events: the version 1 line and its one writer path, the reading of version 0 and
of newer lines, the watcher's filter by audience, its rate limit `events.wake_every` and its
configuration problems. No test sleeps: a watcher is driven with an injected monotonic time.

The audiences other than `project` are prepared lines: no writer produces one yet."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import changes, host, open_batch
from conftest import PLUGIN_ROOT, Chantier, Surface
from test_forge_hub import QUIET

from chantier import __version__
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE
from chantier.core.repo import Repo
from chantier.hub import autostart, journal
from chantier.hub import times as hub_times
from chantier.hub.watch import EVENTS, Rules, Watch, once
from chantier.playbook import config, events_check
from chantier.plugin_files import read_wake_rules

SRC = Path(__file__).resolve().parents[1] / "src" / "chantier"
DEFAULTS = PLUGIN_ROOT / "config" / "chantier.defaults.yml"
CARD = PLUGIN_ROOT / "skills" / "chantier" / "references" / "chief-of-staff.md"
BOARD = {"kind": "board", "action": "move", "items": ["x"], "text": "x", "wakes": True}
MERGED = {"kind": "merged", "batch": "b", "cr": "CR-1", "pr": "P", "into": "main", "merged_at": "t"}
CONFIG = {"kind": "config", "key": "batch.slots", "old": 4, "new": 6, "batch": None}
SECOND = 2
HEAD = ["v", "seq", "t", "kind", "source", "audience"]


def raw(repo: Path, *lines: dict[str, Any]) -> None:
    """Prepare a journal by hand: lines no writer produces any more."""
    folder = changes(repo)
    folder.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(x) + "\n" for x in lines)
    (folder / journal.FILE).write_text(text, encoding="utf-8")


@pytest.mark.parametrize("source", journal.SOURCES)
def test_an_append_writes_a_version_one_line_for_the_project(repo: Path, source: str) -> None:
    found = Repo.find()
    (one, two) = journal.append(found, [MERGED, {**BOARD, "audience": ["project", "user"]}], source)
    assert list(one)[: len(HEAD)] == HEAD and "by" not in one
    assert (one["v"], one["seq"], one["source"], one["audience"]) == (1, 1, source, ["project"])
    assert (two["seq"], two["audience"]) == (2, ["project", "user"])
    assert {k: one[k] for k in MERGED} == MERGED  # the payload is unchanged
    on_disk = json.loads((changes(repo) / journal.FILE).read_text("utf-8").splitlines()[0])
    assert on_disk == one


@pytest.mark.parametrize(
    ("source", "event"),
    [
        ("nobody", MERGED),
        ("hub", {**MERGED, "kind": "ci-red"}),
        ("hub", {**MERGED, "audience": ["Project"]}),
        ("hub", {**MERGED, "audience": ["role:"]}),
        ("hub", {**MERGED, "audience": ["cr:a b"]}),
        ("hub", {**MERGED, "audience": []}),
        ("hub", {**MERGED, "audience": "project"}),
    ],
)
def test_an_append_refuses_a_source_a_kind_or_an_audience_of_a_wrong_form(
    repo: Path, source: str, event: dict[str, Any]
) -> None:
    with pytest.raises(ValueError, match="journal"):
        journal.append(Repo.find(), [event], source)
    assert not (changes(repo) / journal.FILE).exists()


def test_a_version_zero_line_reads_as_the_projects_and_a_newer_one_wakes_no_one(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_batch(repo, chantier, monkeypatch, "Alpha")
    old = {"seq": 1, "t": "t", "by": "board", **BOARD}  # a line today's writers no longer produce
    later = {"v": 2, "seq": 2, "t": "t", "kind": "merged", "source": "x", "audience": ["project"]}
    raw(repo, old, later)
    found = Repo.find()
    entries, bad, newer = journal.read(found.changes)
    assert (entries[0]["source"], entries[0]["audience"]) == ("board", ["project"])
    assert (bad, newer, entries[1]["audience"]) == ([], [(2, 2)], [])
    w = Watch(found, 0, __version__)
    assert w.poll(0.0) is None and w.cursor == SECOND  # the cursor passes the newer line
    assert w.poll(float(QUIET)) == EVENTS
    w.close()
    assert [x for x in w.lines(EVENTS) if "board wrote" in x] == [journal.board_text(old)]
    assert len(w.events) == 1  # the newer line is told by no one
    (third,) = journal.append(found, [MERGED], "hub")
    assert third["seq"] == SECOND + 1
    status = chantier("status")[1]
    assert f"{journal.FILE}: line 2 is version 2, newer than this chantier: update it" in status


# (the lines' audiences, the watcher's --for values, its key, whether it ends)
FILTERS = [
    (["project"], [], "abc-1", True),
    (["role:x"], [], "abc-1", False),
    (["role:x"], ["role:x"], "abc-1", True),
    (["role:y"], ["role:x"], "abc-1", False),
    (["session:abc-1"], [], "abc-1", True),
    (["session:abc-2"], [], "abc-1", False),
    (["session:abc-1"], [], "none", False),
    (["user"], [], "abc-1", False),
    (["user"], ["user"], "abc-1", True),
    (["cr:CR-7"], ["cr:CR-7"], "abc-1", True),
    (["role:x", "session:abc-2"], [], "abc-1", False),
    (["role:x", "project"], [], "abc-1", True),
]


@pytest.mark.parametrize("case", FILTERS)
def test_a_watcher_ends_on_the_lines_for_it_and_passes_the_others(
    repo: Path, monkeypatch: pytest.MonkeyPatch, case: tuple[Any, ...]
) -> None:
    audience, wanted, key, ends = case
    monkeypatch.setattr(autostart, "session_key", lambda: key)
    found = Repo.find()
    w = Watch(found, 0, __version__, Rules(wanted))
    journal.append(found, [{**BOARD, "audience": audience}], "board")
    got = [w.poll(float(t)) for t in range(int(QUIET) + 5)]
    w.close()
    assert w.cursor == 1  # passed, whoever it was for
    assert (EVENTS in got, len(w.events)) == (ends, int(ends))
    assert [x.startswith("board wrote") for x in once(found, 0, wanted)[:-1]] == [True] * ends
    assert once(found, 0, wanted)[-1].startswith("watch: cursor 1;")  # the last line read


def test_the_start_line_lists_the_subscription_and_a_bad_for_is_refused_with_nothing_written(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    found = Repo.find()
    before = sorted(p.as_posix() for p in repo.rglob("*") if ".git/" not in p.as_posix())
    for args in (
        ("--for", "Role:x"),
        ("--for", "role:"),
        ("--once", "--after", "0", "--for", "x y"),
    ):
        code, _, err = chantier("watch", *args)
        assert (
            code == EXIT_USAGE and f'watch: --for "{args[-1]}": one of project, role:<name>' in err
        )
    assert before == sorted(p.as_posix() for p in repo.rglob("*") if ".git/" not in p.as_posix())
    assert not (found.git_dir / "chantier").exists()
    for key, wanted, listed in (
        ("none", [], "project"),
        ("abc-1", [], "project, session:abc-1"),
        (
            "abc-1",
            ["role:x", "project", "session:abc-1", "user"],
            "project, session:abc-1, role:x, user",
        ),
    ):
        monkeypatch.setattr(autostart, "session_key", lambda key=key: key)
        w = Watch(found, 3, __version__, Rules(wanted))
        line = w.start_line()
        w.close()
        assert line.startswith(f"watch: {found.root.name} from cursor 3 for {listed}, the hub")


def test_the_rate_limit_keeps_a_watcher_up_for_wake_every_and_the_shipped_value_changes_nothing(
    repo: Path,
) -> None:
    found = Repo.find()
    shipped = read_wake_rules(found)
    tree, _ = config.parse_text(DEFAULTS.read_text("utf-8"), str(DEFAULTS))
    assert tree is not None and (shipped["layer"], shipped["seconds"]) == ("defaults", 20)
    assert tree.value["events"][1].value["wake_every"][1].value == shipped["text"]
    ends = {}
    for name, every in (("shipped", hub_times.wake_every_s(shipped["seconds"])), ("60s", 60.0)):
        w = Watch(found, 0, __version__, Rules(wake_every=every))
        journal.append(found, [{**BOARD, "text": name}], "board")
        ends[name] = next(t for t in range(120) if w.poll(float(t)) == EVENTS)
        w.close()
    assert ends == {"shipped": int(QUIET), "60s": 60}
    assert hub_times.wake_every_s(None) == 0.0


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("events:\n  wake_every: 20s\n", None),
        ("events:\n  wake_every: 2m\n", None),
        ("events:\n  wake_every: 1h\n", None),
        ("events:\n  wake_every: default\n", None),
        (
            "events:\n  wake_every: 19s\n",
            'events: "wake_every" is <whole number><s|m|h>, 20s or more, found "19s"',
        ),
        (
            "events:\n  wake_every: 30\n",
            'events: "wake_every" is <whole number><s|m|h>, 20s or more, found "30"',
        ),
        (
            "events:\n  wake_every: 1.5m\n",
            'events: "wake_every" is <whole number><s|m|h>, 20s or more, found "1.5m"',
        ),
        ("events:\n  buffer: 5s\n", 'events: unknown key "buffer": one of wake_every'),
        ("events: 20s\n", '"events" holds its key: `wake_every:`'),
    ],
)
def test_the_events_block_is_checked_and_its_problems_are_its_own(
    text: str, problem: str | None
) -> None:
    tree, _ = config.parse_text(text, "chantier.yaml")
    assert tree is not None
    found: list[str] = []
    config.check(tree, {}, lambda n, m: found.append(f"chantier.yaml:{n}: {m}"))
    assert found == (
        [] if problem is None else [f"chantier.yaml:{found[0].split(':')[1]}: {problem}"]
    )
    assert all(events_check.own_problem(p) for p in found)
    assert not events_check.own_problem('chantier.yaml:1: unknown key "colour": the top-level keys')


def test_the_shipped_defaults_hold_events_wake_every_and_pass_the_checks() -> None:
    tree, problems = config.parse_text(DEFAULTS.read_text("utf-8"), str(DEFAULTS))
    assert tree is not None and not problems and events_check.missing(tree) == []
    found: list[str] = []
    config.check(tree, {}, lambda n, m: found.append(m), "events")
    assert found == []
    lacking = config.parse_text("batch:\n  slots: 4\n", "x")[0]
    assert lacking is not None and "events.wake_every" in events_check.missing(lacking)[0]


def _layer(surface: Surface, where: str, text: str) -> None:
    folder = surface.clone if where == "repository" else surface.project
    (folder / "chantier.yaml").write_text(text, encoding="utf-8")


# (the layers, the plugin, the `events:` line of `playbook`)
LINES = [
    ({}, "plugin", "events: wake every 20s"),
    ({"surface project": "2m"}, "plugin", "events: wake every 2m [surface project]"),
    ({"repository": "3m"}, "plugin", "events: wake every 3m [repository]"),
    ({"surface project": "2m", "repository": "default"}, "plugin", "events: wake every 20s"),
    ({}, "none", "events: wake every: not set"),
    ({"repository": "3m"}, "none", "events: wake every 3m [repository]"),
]


@pytest.mark.parametrize("case", LINES)
def test_playbook_prints_the_wake_rule_with_its_layer(
    surface: Surface,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    case: tuple[Any, ...],
) -> None:
    layers, plugin, line = case
    host(monkeypatch)
    for where, value in layers.items():
        _layer(surface, where, f"events:\n  wake_every: {value}\n")
    if plugin == "none":
        monkeypatch.setenv("CHANTIER_PLUGIN_ROOT", "")
    code, out, err = chantier("--project", "demo", "playbook")
    assert code == 0, err
    assert [x for x in out if x.startswith("events:")] == [line]
    assert out.index(line) == next(i for i, x in enumerate(out) if x.startswith("limits:")) + 1


def test_a_problem_in_the_events_block_refuses_the_watcher_and_one_elsewhere_is_named(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    (repo / "chantier.yaml").write_text("events:\n  wake_every: 5s\n", encoding="utf-8")
    code, _, err = chantier("watch")
    assert code == EXIT_PRECONDITION
    assert 'chantier.yaml:2: events: "wake_every" is' in err and "start the watcher again" in err
    assert not (Repo.find().git_dir / "chantier").exists()  # no lock taken
    code, out, _ = chantier("playbook")
    assert code == EXIT_PRECONDITION and any('"wake_every" is' in x for x in out)
    (repo / "chantier.yaml").write_text(
        "events:\n  wake_every: 2m\ncolour: red\n", encoding="utf-8"
    )
    rules = read_wake_rules(Repo.find())
    assert (rules["seconds"], rules["events_problems"]) == (120, [])  # the rule is still read
    assert rules["other"].startswith('chantier.yaml:3: unknown key "colour"')
    found = Repo.find()
    w = Watch(found, 0, __version__, Rules(note=rules["other"]))
    line = w.start_line()
    w.close()
    assert line.endswith(f"; configuration: {rules['other']}") and rules["other"] in line


def test_no_role_is_named_and_the_journal_has_one_writer() -> None:
    named = re.compile(r"role:[A-Za-z]")
    shipped = [*SRC.rglob("*.py"), DEFAULTS]
    assert [p.name for p in shipped if named.search(p.read_text("utf-8"))] == []
    writing = re.compile(r"open\(|write_text|write_bytes|\.write\(")
    refs = re.compile(r"journal\.FILE|forge-journal\.jsonl|FILE\b")
    writers = []
    for path in SRC.rglob("*.py"):
        if path.name == "journal.py" and path.parent.name == "hub":
            continue
        text = path.read_text("utf-8")
        if "forge-journal.jsonl" not in text and "journal.FILE" not in text:
            continue
        if any(refs.search(x) and writing.search(x) for x in text.splitlines()):
            writers.append(path.name)
    assert writers == []


def test_the_card_states_the_end_rule_in_its_watcher_line_outside_the_startup_core() -> None:
    lines = CARD.read_text("utf-8").splitlines()
    at = next(i for i, x in enumerate(lines) if x.startswith("- **The watcher**"))
    bullet = " ".join(x.strip() for x in lines[at : at + 8])
    assert "for it" in bullet and "events.wake_every" in bullet and "20 s" in bullet
    heading = next(x for x in reversed(lines[:at]) if x.startswith("## "))
    assert heading == "## While it runs" and "Startup core" not in heading

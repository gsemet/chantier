"""The three role cards cut by moment (CR-471): every rule is reached by an action, the entry
cards' lists of moments agree with the manifest, the moved rules are where the tables say, and no
link names an anchor the cut removed."""

import re
from pathlib import Path

import pytest
from conftest import PLUGIN_ROOT, SKILL
from test_startup_manifest import _lf_bytes, _manifest, _resolve, _sections, _text

REFS = SKILL / "references"
HOSTS = ("claude", "copilot")
HOST_CARD = {"claude": "hosts/claude-code.md", "copilot": "hosts/copilot.md"}
ENTRY = {"chief-of-staff": "chief-of-staff.md", "foreman": "foreman.md", "driver": "driver.md"}
PREFIXES = {
    "chief-of-staff": "chief-of-staff",
    "foreman": "foreman",
    **{p: "driver" for p in ("cr-driver", "stack-driver", "qa-driver", "release-driver", "driver")},
}
PIECES = (
    *("chief-of-staff*.md", "foreman*.md", "driver*.md"),
    *("stack-driver-*.md", "release-driver-*.md"),
)
COLUMNS = 4  # words, old card#section, new file#section, action
COMPACTION = (
    "After a compaction, read your entry action again, then the action of the moment you are in."
)


def _headings(path: Path) -> list[str]:
    """The card's level-2 headings, outside fenced code."""
    out, fenced = [], False
    for line in _lf_bytes(path).decode("utf-8").splitlines():
        fenced ^= line.startswith("```")
        if not fenced and line.startswith("## "):
            out.append(line)
    return out


def _reached(readings: list[list[object]], host: str) -> set[tuple[Path, str]]:
    """What the readings reach for a host: (file, "") for a whole file, (file, heading) else."""
    out: set[tuple[Path, str]] = set()
    for reading in readings:
        files, sections = _sections(reading, host)
        out |= {(f.resolve(), "") for f in files}
        out |= {(Path(s["file"]).resolve(), s["heading"]) for s in sections}
    return out


def _all_readings() -> list[list[object]]:
    manifest = _manifest()[0]
    return [*manifest["actions"].values(), *manifest["startup_sections"].values()]


def _role_cards() -> list[Path]:
    return sorted({p for pattern in PIECES for p in REFS.glob(pattern)})


@pytest.mark.parametrize("host", HOSTS)
def test_every_section_of_the_role_cards_is_reached_by_an_action(host: str) -> None:
    reached = _reached(_all_readings(), host)
    missing = [
        f"{card.name}#{heading[3:]}"
        for card in _role_cards()
        for heading in _headings(card)
        if (card.resolve(), "") not in reached and (card.resolve(), heading) not in reached
    ]
    assert missing == []


@pytest.mark.parametrize("host", HOSTS)
def test_the_foreman_actions_reach_every_section_batch_read_whole_at_the_base(host: str) -> None:
    manifest = _manifest()[0]
    names = [k for k in manifest["actions"] if k == "batch" or k.startswith(("batch:", "foreman:"))]
    readings = [manifest["actions"][k] for k in names] + [manifest["startup_sections"]["foreman"]]
    reached = _reached(readings, host)
    for card in (REFS / "concepts.md", REFS / HOST_CARD[host]):
        missing = [
            h
            for h in _headings(card)
            if (card.resolve(), "") not in reached and (card.resolve(), h) not in reached
        ]
        assert missing == [], card.name


def test_the_entry_cards_and_the_manifest_name_the_same_moments() -> None:
    actions = _manifest()[0]["actions"]
    pattern = re.compile(r"`((?:" + "|".join(PREFIXES) + r"):[a-z-]+)`")
    named: set[str] = set()
    for prefix, entry in ENTRY.items():
        text = _text(REFS / entry)
        own = {a for a in actions if ":" in a and PREFIXES.get(a.split(":")[0]) == prefix}
        assert own
        assert [a for a in own if f"`{a}`" not in text] == [], entry
        named |= set(pattern.findall(text))
    assert sorted(named - set(actions)) == []


def _moved_rules() -> list[tuple[str, str, str, str]]:
    lines = Path(__file__).with_name("moved_rules.tsv").read_text(encoding="utf-8").splitlines()
    rows = [tuple(line.split("\t")) for line in lines if line and not line.startswith("#")]
    assert all(len(r) == COLUMNS for r in rows)
    return rows  # type: ignore[return-value]


MOVED_RULES = _moved_rules()


@pytest.mark.parametrize(("words", "old", "new", "action"), MOVED_RULES)
def test_a_moved_rule_is_in_its_piece_gone_from_its_card_and_read_by_its_action(
    words: str, old: str, new: str, action: str
) -> None:
    file, _, heading = new.partition("#")
    assert words in _text(REFS / file, heading), new
    card, _, was = old.partition("#")
    data = _lf_bytes(REFS / card).decode("utf-8")
    place = data if was else data[: data.index("\n## ")]  # no section: the card's opening
    assert words not in " ".join(place.split()), old
    for host in HOSTS:
        reached = _reached([_manifest()[0]["actions"][action]], host)
        path = (REFS / file).resolve()
        assert (path, "") in reached or (path, f"## {heading}") in reached, (action, host)


def test_the_compaction_sentence_ends_each_list_of_moments() -> None:
    assert COMPACTION in _text(REFS / "session-start.md", "5. Reload")
    for entry in ("chief-of-staff.md", "foreman.md"):
        assert COMPACTION in _text(REFS / entry, "The moments"), entry
    driver = _lf_bytes(REFS / "driver.md").decode("utf-8")
    assert COMPACTION in " ".join(driver[: driver.index("\n## ")].split())


def test_the_one_host_form_has_both_hosts_and_the_paths_text_names_it() -> None:
    manifest = _manifest()[0]
    readings = [r for v in manifest["actions"].values() for r in v if isinstance(r, dict)]
    assert readings
    assert all(set(r) == {"claude", "copilot"} for r in readings)
    for reading in readings:
        assert all(_resolve(reading, host)["file"] for host in HOSTS)
    assert "{claude,copilot}" in manifest["paths"] and "that host only" in manifest["paths"]


def _slug(heading: str) -> str:
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def _linking_files() -> list[Path]:
    return [
        *REFS.rglob("*.md"),
        *(PLUGIN_ROOT / "skills").glob("*/SKILL.md"),
        PLUGIN_ROOT / "CONTRIBUTING.md",
        PLUGIN_ROOT / "evals" / "README.md",
        *(PLUGIN_ROOT / "docs").rglob("*.md"),
    ]


def test_no_link_names_an_anchor_the_entry_cards_lost() -> None:
    anchors = {
        name: {
            _slug(line.lstrip("#"))
            for line in _lf_bytes(REFS / name).decode("utf-8").splitlines()
            if re.match(r"#{1,6} ", line)
        }
        for name in ENTRY.values()
    }
    link = re.compile(r"(?<![\w-])(chief-of-staff|foreman|driver)\.md#([\w-]+)")
    broken = [
        f"{path.relative_to(PLUGIN_ROOT).as_posix()}: {name}.md#{anchor}"
        for path in _linking_files()
        for name, anchor in link.findall(_lf_bytes(path).decode("utf-8"))
        if anchor not in anchors[f"{name}.md"]
    ]
    assert broken == []


@pytest.mark.parametrize("card", ["driver.md", "debugger.md", "verifier.md"])
def test_the_cards_send_a_downloaded_ci_artifact_to_the_scratch_folder(card: str) -> None:
    text = (SKILL / "references" / card).read_text(encoding="utf-8")
    assert "work/scratch/artifacts-<run id>/" in " ".join(text.split())

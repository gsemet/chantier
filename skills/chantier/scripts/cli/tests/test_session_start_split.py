"""The split of `session-start.md`: each moved instruction is where the table of moves says, is
read by the reading that table names, and nothing of it is left in the common card."""

import json
import re
from pathlib import Path

import pytest
from conftest import PLUGIN_ROOT, SKILL
from test_startup_manifest import _lf_bytes, _text

from chantier.connectors import CONNECTORS

REFS = SKILL / "references"
START = REFS / "session-start.md"
COS = REFS / "session-start-chief-of-staff.md"
GRILLER = REFS / "session-start-griller.md"
TITLES = REFS / "titles.md"
SYNC = REFS / "sync-checkout.md"
MANIFEST = json.loads((REFS / "startup-manifest.json").read_text(encoding="utf-8"))
RULE = "read the file of the role the seat gives you, again when the role changes"

# (phrase, new file, heading, the manifest action that reads it, or "header": the common header)
MOVED_IN = [
    ("The board.** A persistent process", COS, "The board", "board"),
    (
        "I start the watcher, which starts the board if it is not running?",
        COS,
        "The watcher",
        "chief-of-staff",
    ),
    ("ask the board question alone", COS, "The board", "chief-of-staff"),
    ("Another project runs chantier from its checkout in plugin mode", COS, "The board", "board"),
    ("`board: writer not started: <reason>`", COS, "The board", "board"),
    ("keeps the `--project` that `$CHANTIER` holds", COS, "The board", "chief-of-staff"),
    (
        "The board a watcher starts is no background task of the session",
        COS,
        "Stopping the board by hand",
        "chief-of-staff",
    ),
    ("A reload starts nothing", COS, "Stopping the board by hand", "chief-of-staff"),
    ("never start either", START, "2. The seat and the role", "header"),
    ("never starts the board or the watcher", GRILLER, None, "header"),
    ("A title tells first whether the user talks to the session", TITLES, None, "chief-of-staff"),
    ("`[<code>] ⚙️ Project · Foreman (Batch <nn>)`", TITLES, None, "header"),
    ("Name the holders before syncing", SYNC, None, "sync"),
    ("Your own board and watcher, on your yes", SYNC, None, "sync"),
]
MOVED_OUT = [
    "The board a watcher starts is no background task of the session",
    "I start the watcher, which starts the board if it is not running?",
    "`board: writer not started: <reason>`",
    "A title tells first whether the user talks to the session",
    "Name the holders before syncing",
    "Another project runs chantier from its checkout in plugin mode",
    "## 3. Titles",
    "## 6. Sync the checkout",
]
KEPT = ["become chief of staff", "become a griller", "**Re-read the seat**", RULE.capitalize()]
NO_TOOL = [START, COS, GRILLER, TITLES, SYNC]


@pytest.mark.parametrize(("phrase", "path", "heading", "reading"), MOVED_IN)
def test_a_moved_instruction_is_in_its_new_card_and_read_by_its_reading(
    phrase: str, path: Path, heading: str | None, reading: str
) -> None:
    assert phrase in _text(path, heading), (phrase, path.name)
    if reading == "header":
        header = _text(START).split("## 1.")[0]
        assert f"]({path.name})" in header or path == START, path.name
    else:
        assert path.name in MANIFEST["actions"][reading], (reading, path.name)


@pytest.mark.parametrize("phrase", MOVED_OUT)
def test_a_moved_instruction_is_gone_from_the_common_card(phrase: str) -> None:
    assert phrase not in _text(START)


@pytest.mark.parametrize("phrase", KEPT)
def test_the_common_card_keeps_the_seat_and_the_role_change(phrase: str) -> None:
    assert phrase in _text(START, "2. The seat and the role")


def test_the_rule_is_in_the_common_header_and_in_both_skills() -> None:
    assert RULE in _text(START).split("## 1.")[0]
    for skill in ("chief-of-staff", "griller"):
        core = _text(PLUGIN_ROOT / "skills" / skill / "SKILL.md", "Startup core")
        assert "At the session's start, read `session-start.md`, then your role's file" in core
        assert "again when the role changes" in core


def test_every_role_file_is_linked_from_the_common_header() -> None:
    header = _text(START).split("## 1.")[0]
    for card in (COS, GRILLER, TITLES, SYNC):
        assert f"]({card.name})" in header, card.name


@pytest.mark.parametrize("path", NO_TOOL, ids=lambda p: p.name)
def test_the_startup_cards_name_no_forge_tool(path: Path) -> None:
    assert not re.search(r"\b(gh|glab)\b", _lf_bytes(path).decode("utf-8")), path.name


def test_each_connector_has_its_forge_card_and_the_doc_names_the_step() -> None:
    for connector in CONNECTORS:
        card = REFS / "forges" / f"{connector.name}.md"
        assert card.is_file(), card
        assert f"`{connector.program}`" in _text(card), card
        assert "forge-connectors.md" in _text(card), card
        assert (card.parent / "../../../../docs/forge-connectors.md").resolve().is_file()
    doc = _text(PLUGIN_ROOT / "docs" / "forge-connectors.md", "Adding a connector")
    assert "forges/<name>.md" in doc


def test_no_worker_driver_or_foreman_reading_names_a_session_start_file() -> None:
    moved = ("titles.md", "sync-checkout.md", "session-start")
    steering = {"chief-of-staff", "session-start", "board", "sync", "route", "reload"}
    for action, readings in MANIFEST["actions"].items():
        if action in steering:
            continue
        assert not [r for r in readings if any(m in r for m in moved)], action
    for role, readings in MANIFEST["startup_sections"].items():
        assert not [r for r in readings if isinstance(r, str) and "session-start" in r], role
    for role in ("foreman", "cr-driver", "coder"):
        assert role not in steering

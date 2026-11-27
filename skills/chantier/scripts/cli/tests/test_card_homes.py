"""Each protective rule of `docs/protective-rules.md` that lives in a card, a skill, the floor or a
host row keeps its home there. A key is the test file that first held the pins."""

from __future__ import annotations

import pytest
from conftest import SKILL

from chantier.commands.help import load_topics, section
from chantier.core.errors import ChantierError
from chantier.host_rows import load_rows

REFS = SKILL / "references"

FLOOR = {
    1: "Never merge without the user's word.",
    2: "Rebase only, with `--force-with-lease`, and only on the CR's own branch.",
    3: "No fallback.",
    4: "A CLI that cannot run is a stop.",
    5: "Never discard the worktree's work.",
    6: "An irreversible release action waits for the user.",
    7: "Only the user starts work.",
    8: "No image shows the username or the home folder.",
    9: "Report a refusal with its exact text; never work around it.",
    10: "Never stop a process by name or pattern; use `close --yes` only on the user's yes.",
}

# test file -> (its topics, its other homes)
HOMES = {
    "test_role_cards_split": (
        "batch-close-stopped batch-plan batch-plan-mode delivery-time grill-backlog "
        "handback-other hold main-checkout merge-gaps merge-series-stack "
        "merge-under-grant merge-words pr-extras recovery refused-push refused-rebase "
        "release-merged release-ship retake retro-critic retro-route-chantier "
        "stack-changes trials trouble-gate trouble-git trouble-remote trouble-worker",
        [
            "card chief-of-staff.md",
            "card foreman.md",
            "card release-driver.md",
            "card stack-driver.md",
            "card verifier.md",
            "floor 1",
            "floor 10",
            "floor 5",
            "floor 6",
            "floor 7",
            "floor 9",
        ],
    ),
    "test_startup_manifest": (
        "grill-surface seat session-start",
        [
            "card chief-of-staff.md",
            "card concepts.md#Starting an agent",
            "card foreman.md",
            "card griller-skill.md#Never",
            "skill chief-of-staff",
            "skill griller",
        ],
    ),
    "test_session_start_split": (
        "board-lines board-restart seat sync-offer watcher",
        [
            "card chief-of-staff.md",
            "card griller-skill.md#Never",
            "card sync-checkout.md",
            "skill chief-of-staff",
            "skill griller",
        ],
    ),
    "test_stack_chain_cards": (
        "cr-handback refused-push release-ship retake stack-record stack-restack",
        [
            "card cr-driver.md",
            "card stack-driver.md",
        ],
    ),
    "test_stack_shape": (
        "batch-plan-mode merge-series-stack stack-outside",
        [
            "card foreman.md",
            "floor 7",
        ],
    ),
    "test_reload_rules": (
        "batch-plan-mode merge-gaps merge-series-stack merge-words",
        [
            "card foreman.md",
            "floor 1",
        ],
    ),
    "test_came_back": (
        "hold order-drop project-rules refused-push refused-push-chief "
        "refused-push-chief-more refused-push-run retake stack-changes watcher-board",
        [
            "card chief-of-staff.md",
            "card cr-driver.md",
            "card foreman.md",
            "card routing.md",
            "floor 10",
            "floor 7",
            "floor 9",
        ],
    ),
    "test_release_tag": (
        "release-merged release-tag",
        [],
    ),
    "test_rebase_rules": (
        "refused-push refused-rebase",
        [],
    ),
    "test_cli_stop": (
        "",
        [
            "card concepts.md#Starting an agent",
            "floor 3",
            "floor 4",
            "floor 9",
            "skill chantier",
        ],
    ),
    "test_watcher_step": (
        "watcher watcher-events",
        [],
    ),
    "test_event_audience": (
        "seat watcher-events",
        [
            "card chief-of-staff.md",
        ],
    ),
    "test_board_restart": (
        "batch-close-stopped board-restart",
        [
            "card chief-of-staff.md",
            "floor 10",
        ],
    ),
    "test_command_names": (
        "",
        [
            "card sync-checkout.md",
            "skill chief-of-staff",
        ],
    ),
    "test_release_template_card": (
        "pr-extras release-evidence",
        [],
    ),
    "test_launch_modes": (
        "batch-close-stopped board-lines board-restart sync-offer",
        [
            "card chief-of-staff.md",
            "card concepts.md#Starting an agent",
            "card sync-checkout.md",
            "floor 10",
            "floor 4",
            "skill chantier",
            "skill chief-of-staff",
            "host name-env-holders",
        ],
    ),
}


def _file_gone(kind: str, name: str) -> bool:
    path, _, heading = name.partition("#")
    file = REFS / path if kind == "card" else SKILL.parent / path / "SKILL.md"
    if not file.is_file():
        return True
    if not heading:
        return False
    try:
        section(file, heading)
    except ChantierError:
        return True
    return False


def _gone(home: str) -> bool:
    kind, _, name = home.partition(" ")
    if kind == "topic":
        return name not in load_topics()
    if kind == "floor":
        lines = (REFS / "floor.md").read_text(encoding="utf-8").splitlines()
        return f"{name}. {FLOOR[int(name)]}" not in lines
    if kind == "host":
        return any(name not in {r.capability for r in load_rows(h)} for h in ("claude", "copilot"))
    return _file_gone(kind, name)


@pytest.mark.parametrize("pins", HOMES)
def test_every_rule_pinned_in_a_removed_card_has_its_home(pins: str) -> None:
    topics, other = HOMES[pins]
    homes = [f"topic {name}" for name in topics.split()] + other
    assert [home for home in homes if _gone(home)] == []


def test_a_home_that_is_gone_is_named() -> None:
    homes = ["topic gone", "card gone.md", "card foreman.md#Gone", "host gone", "floor 3"]
    assert [home for home in homes if _gone(home)] == homes[:-1]


def test_the_floor_reads_word_for_word() -> None:
    lines = (REFS / "floor.md").read_text(encoding="utf-8").splitlines()
    assert [ln for ln in lines if ln[:1].isdigit()] == [f"{n}. {FLOOR[n]}" for n in sorted(FLOOR)]

"""A rule a test pinned in a card the swap removed keeps its home (CR-510, specification section
6): a topic, a card and its level-2 heading, a skill, a floor line or a host row, as the family
inventories' `new home` column names it. A key is the test file that held the pins."""

from __future__ import annotations

import pytest
from conftest import SKILL

from chantier.commands.help import load_topics, section
from chantier.core.errors import ChantierError
from chantier.host_rows import load_rows

REFS = SKILL / "references"

FLOOR = {
    1: "Never merge without the user's word.",
    3: "No fallback.",
    4: "A CLI that cannot run is a stop.",
    5: "Never discard the worktree's work.",
    6: "An irreversible release action waits for the user.",
    7: "Only the user starts work.",
    9: "Report a refusal with its exact text; never work around it.",
    10: "Never stop a process by name or pattern; use `close --yes` only on the user's yes.",
}

# test file -> (its topics, its other homes)
HOMES = {
    "test_role_cards_split": (
        "batch-close-stopped batch-pause batch-plan batch-plan-mode compacting conflict-check "
        "conflicts cr-prompt cr-rounds delivery-time direct-mode forge-permissions "
        "grill-backlog handback-other hold lease lost-driver main-checkout matrix merge "
        "merge-gaps merge-series-stack merge-stack-ready merge-under-grant merge-words "
        "mode-switch options park pr-extras recovery refusals-to-say refused-push "
        "refused-push-answer refused-rebase release-chief release-end release-merged "
        "release-notes release-ship release-take retake retro-critic retro-route "
        "retro-route-chantier stack stack-changes stack-changes-chief stack-joins stack-make "
        "stack-run steering-messages steering-reports take-back trials trouble-gate "
        "trouble-git trouble-remote trouble-worker writer",
        [
            "card chief-of-staff.md",
            "card debugger.md",
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
        "first-turn foreman-start grill-surface reload restart seat session-start",
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
        "board board-lines board-restart reload seat sync-offer titles wakes watcher",
        [
            "card chief-of-staff.md",
            "card griller-skill.md#Never",
            "card sync-checkout.md",
            "skill chief-of-staff",
            "skill griller",
        ],
    ),
    "test_stack_chain_cards": (
        "cr-handback refused-push release-ship retake retake-notes stack-grows stack-record "
        "stack-restack",
        [
            "card cr-driver.md",
            "card stack-driver.md",
        ],
    ),
    "test_stack_shape": (
        "batch-plan-mode merge-series-stack stack stack-checks stack-merge stack-outside "
        "stack-takes",
        [
            "card foreman.md",
            "floor 7",
        ],
    ),
    "test_reload_rules": (
        "batch-plan-mode merge-gaps merge-recorded merge-series-stack merge-words",
        [
            "card foreman.md",
            "card status-layout.md",
            "card status-layout.md#The rules of every report",
            "floor 1",
        ],
    ),
    "test_came_back": (
        "batch-close checkpoints driver-question hold merge-recorded merge-stack-ready "
        "order-drop park park-back project-rules refused-push refused-push-answer "
        "refused-push-chief refused-push-chief-more refused-push-route refused-push-run "
        "restart retake retake-notes retro session-start-surface stack-changes "
        "stack-changes-chief stack-drop steering-messages take-back watcher-board "
        "where-cr-goes",
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
    "test_triage_moves": (
        "session-shell",
        [],
    ),
    "test_cli_stop": (
        "config cr-workers session-shell worker-shell",
        [
            "card concepts.md#Starting an agent",
            "floor 3",
            "floor 4",
            "floor 9",
            "skill chantier",
        ],
    ),
    "test_watcher_step": (
        "foreman-start watcher watcher-events watcher-lines",
        [],
    ),
    "test_event_audience": (
        "seat watcher-events",
        [
            "card chief-of-staff.md",
        ],
    ),
    "test_board_restart": (
        "batch-close-stopped board board-restart",
        [
            "card chief-of-staff.md",
            "floor 10",
            "host run-board",
        ],
    ),
    "test_board_running_lane": (
        "where-cr-goes",
        [],
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
        [
            "card release-template.md#The notes",
        ],
    ),
    "test_launch_modes": (
        "batch-close-stopped board-lines board-restart session-shell session-start-surface "
        "status-notes sync-offer worker-shell",
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

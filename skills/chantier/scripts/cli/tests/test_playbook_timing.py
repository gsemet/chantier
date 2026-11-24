"""The timing settings: refused with their line, resolved per layer, printed, recorded for a
running batch and carried to the board."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from batch_helpers import changes, host, open_batch, record
from conftest import PLUGIN_ROOT, Chantier, Surface

from chantier.board.state import steering_wake_min
from chantier.core.records import BatchRecord
from chantier.core.repo import Repo
from chantier.playbook import edit, layers, timing
from chantier.plugin_files import plugin_roles

DEFAULTS = PLUGIN_ROOT / "config" / "chantier.defaults.yml"
WAKE, SHIPPED_WAKE = 12, 55  # minutes
LINES_WITH_WARNING, WAKE_20M, WAKE_10M = 3, 1200, 600


T_CLAUDE = "hosts:\n  claude:\n    timing:\n"
T_COPILOT = T_CLAUDE.replace("claude", "copilot")
SESSION = "      session:\n        cache_ttl: "
TTL10 = T_CLAUDE + "      cache_ttl: 10m\n"
TTL20 = T_CLAUDE + SESSION + "20m\n"
RESOLUTION = [
    ("shipped", [], ("claude", "session", "cache_ttl", (3600, "defaults"))),
    ("not read", [], ("claude", "subagent", "steering_wake", None)),
    (
        "column above general in a layer",
        [("surface project", T_CLAUDE + "      cache_ttl: 10m\n" + SESSION + "20m\n")],
        ("claude", "session", "cache_ttl", (1200, "surface project")),
    ),
    (
        "stronger general above weaker column",
        [
            ("surface", T_CLAUDE + SESSION + "20m\n"),
            ("repository", T_CLAUDE + "      cache_ttl: 10m\n"),
        ],
        ("claude", "session", "cache_ttl", (600, "repository")),
    ),
    (
        "general above the shipped column",
        [("repository", T_CLAUDE + "      cache_ttl: 10m\n")],
        ("claude", "session", "cache_ttl", (600, "repository")),
    ),
    (
        "a reset back to the shipped default",
        [
            ("surface", T_CLAUDE + SESSION + "20m\n"),
            ("repository", T_CLAUDE + SESSION + "default\n"),
        ],
        ("claude", "session", "cache_ttl", (3600, "defaults")),
    ),
    (
        "copilot general and column",
        [("surface", T_COPILOT + "      steering_wake: 10m\n      gpt:\n        ci_reruns: 2\n")],
        ("copilot", "gpt", "steering_wake", (600, "surface")),
    ),
]


def _timing(user: list[tuple[str, str]]) -> dict[str, Any]:
    roles = {h: plugin_roles(h) for h in ("claude", "copilot")}
    defaults, problems = layers.read_defaults(DEFAULTS, roles)
    assert defaults is not None and not problems
    held = []
    for label, text in user:
        tree, bad = layers.read_text(text, f"{label}.yaml", label, roles)
        assert tree is not None, bad
        held.append(layers.Layer(label, Path(f"{label}.yaml"), f"{label}.yaml", tree))
    return timing.timing_from(held, defaults)


@pytest.mark.parametrize("case", RESOLUTION, ids=[c[0] for c in RESOLUTION])
def test_the_timing_resolves_per_layer_strongest_first(case: tuple[Any, ...]) -> None:
    _, user, (host_name, column, setting, want) = case
    got = _timing(user)[host_name]["columns"][column][setting]
    assert (got and (got["value"], got["layer"])) == want


def _printed(out: list[str]) -> list[str]:
    return [ln for ln in out if ln.startswith("timing:")]


def test_the_timing_lines_are_printed_recorded_and_kept_by_a_running_batch(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    assert _printed(chantier("playbook")[1]) == [
        "timing: Claude Code subagent: cache TTL 5 min, CI re-runs 1",
        "timing: Claude Code session: steering wake 55 min, cache TTL 60 min",
    ]
    file = repo / "chantier.yaml"
    file.write_text(T_CLAUDE + "      session:\n        steering_wake: 20m\n", encoding="utf-8")
    assert _printed(chantier("playbook")[1])[1] == (
        "timing: Claude Code session: steering wake 20 min [repository], cache TTL 60 min"
    )
    file.write_text(T_CLAUDE + "      steering_wake: 60m\n      cache_ttl: 5m\n", encoding="utf-8")
    _, out, _ = chantier("playbook")
    warning = (
        "timing: Claude Code session: steering wake 60 min is above the cache TTL 5 min: "
        "each wake starts cold"
    )
    assert (
        warning in out and len(_printed(out)) == LINES_WITH_WARNING
    )  # two columns and the warning
    file.write_text(T_CLAUDE + "      session:\n        steering_wake: 20m\n", encoding="utf-8")
    ids = open_batch(repo, chantier, monkeypatch, "Timing one")
    assert record(repo)["timing"]["columns"]["session"]["steering_wake"]["value"] == WAKE_20M
    brief = next(changes(repo).rglob("brief.md")).read_text(encoding="utf-8")
    assert (
        "- Timing: Claude Code subagent: cache TTL 5 min, CI re-runs 1; Claude Code session:"
        in brief
    )
    file.write_text(T_CLAUDE + "      session:\n        steering_wake: 25m\n", encoding="utf-8")
    _, kept, _ = chantier("playbook", "--batch", record(repo)["id"])
    _, took, _ = chantier("take", ids[0], "--epoch", 1)
    for lines in (kept, took):
        assert "steering wake 20 min [repository]" in "".join(_printed(lines))


def test_the_board_view_state_and_flat_list_carry_the_timing(surface: Surface) -> None:
    (surface.project / "chantier.yaml").write_text(
        T_COPILOT + "      steering_wake: 10m\n      gpt:\n        steering_wake: 12m\n",
        encoding="utf-8",
    )
    view = edit.config_view(Repo.find(project="demo", readonly=True))
    copilot, claude = view["timing"]["copilot"], view["timing"]["claude"]
    cell = copilot["settings"]["steering_wake"]["columns"]
    assert cell["gpt"]["text"] == "12 min" and not cell["gpt"]["default"]
    assert cell["claude"]["layer"] == "surface project" and cell["claude"]["value"] == WAKE_10M
    reruns = claude["settings"]["ci_reruns"]["columns"]
    assert reruns["session"] == {"not_used": True} and reruns["subagent"]["default"] is True
    assert [c["name"] for c in copilot["columns"]] == ["Claude models", "GPT models"]
    assert not any("timing" in o["path"] for o in view["others"])
    # the board's late mark: the session's wake on Claude Code, the longest on Copilot
    held = _timing([("surface project", T_COPILOT + "      gpt:\n        steering_wake: 12m\n")])
    assert steering_wake_min(BatchRecord(host="copilot", timing=held["copilot"])) == WAKE
    assert steering_wake_min(BatchRecord(host="claude", timing=held["claude"])) == SHIPPED_WAKE
    assert (
        steering_wake_min(BatchRecord(host="claude")) == SHIPPED_WAKE
    )  # no timing: the shipped defaults


CONFIGURED = [("30m", 30), ("20m", 20), ("58m", 58), ("60m", 60)]


@pytest.mark.parametrize("text,minutes", CONFIGURED, ids=[c[0] for c in CONFIGURED])
def test_a_configured_claude_code_wake_wins_up_to_the_bound(text: str, minutes: int) -> None:
    got = _timing([("repository", T_CLAUDE + f"      steering_wake: {text}\n")])
    assert steering_wake_min(BatchRecord(host="claude", timing=got["claude"])) == minutes


REFUSALS = [
    (T_CLAUDE + "      steering_wake: 30\n", "a duration of 1 minute or more"),
    (T_CLAUDE + "      cache_ttl: 30s\n", "a duration of 1 minute or more"),
    (T_CLAUDE + "      ci_reruns: -1\n", "a whole number, 0 or more"),
    (T_CLAUDE + "      steering_wake: 90m\n", "at most 60 minutes on Claude Code"),
    (T_COPILOT + "      steering_wake: 90s\n", "whole minutes on Copilot"),
    (T_CLAUDE + "      ci_reruns: 2\n      other: 1\n", 'unknown key "other"'),
    (T_CLAUDE + "      session:\n        ci_reruns: 2\n", "is not read by the session column"),
]


@pytest.mark.parametrize("text,fragment", REFUSALS, ids=[r[1] for r in REFUSALS])
def test_a_wrong_timing_setting_is_refused_with_its_line(text: str, fragment: str) -> None:
    roles = {h: plugin_roles(h) for h in ("claude", "copilot")}
    tree, problems = layers.read_text(text, "chantier.yaml", "repository", roles)
    assert tree is None and any(fragment in p for p in problems), problems

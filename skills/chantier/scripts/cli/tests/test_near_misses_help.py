"""The `--help` of each command that takes a near-miss form says so."""

from __future__ import annotations

import argparse

import pytest

from chantier import cli as cli_module
from chantier import near_misses


def _helps() -> dict[str, str]:
    parser = cli_module._parser()
    subs = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return {name: p.format_help() for name, p in subs.choices.items()}


@pytest.mark.parametrize("name", ["handoff", "log", "verdict", "wait"])
def test_help_says_a_valid_lease_renews(name: str) -> None:
    text = _helps()[name]
    assert "also accepted:" in text and "`--lease N`, renewed when valid" in text


def test_help_says_rules_ignores_a_lease_and_phase_splits() -> None:
    helps = _helps()
    assert "`--lease N`, ignored" in helps["rules"]
    assert '"<step> <detail>"' in helps["phase"]
    assert "--lease N" in helps["lease"] and "lease <unit> --lease N" in helps["lease"]


@pytest.mark.parametrize("name", ["summary", "triage", "abandon", "open", "wait"])
def test_help_lists_the_path_forms(name: str) -> None:
    helps = _helps()
    text = helps[name]
    if name == "summary":
        # the actions carry the forms, not the group
        parser = cli_module._parser()
        subs = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
        inner = next(
            a for a in subs.choices["summary"]._actions if isinstance(a, argparse._SubParsersAction)
        )
        text = "".join(p.format_help() for p in inner.choices.values())
    assert "the CR's short name" in text and "planning prefix" in text


def test_help_says_where_the_epoch_goes_on_every_epoch_command() -> None:
    helps = _helps()
    for name in near_misses.EPOCH_COMMANDS:
        assert "`--epoch N` before the command name" in helps[name], name

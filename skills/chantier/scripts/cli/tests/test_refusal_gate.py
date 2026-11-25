"""M9: every refusal the batch rails raise names, in backticks, the next command to run, or is
in a counted allow-list of final "stop now" refusals. A static scan of the shipped files."""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

import pytest

import chantier.cli
import chantier.core.leases
import chantier.rails
import chantier.rails_idle
import chantier.rails_release
from chantier.core.leases import reclaim_command
from chantier.core.records import Lease

FILES = {
    "rails": chantier.rails,
    "rails_release": chantier.rails_release,
    "rails_idle": chantier.rails_idle,
    "leases": chantier.core.leases,
}
COMMAND_HELPERS = {"reclaim_command"}  # a function whose output is a command
MIN_REFUSALS = 36  # the count at the base: a broken scan cannot pass empty
FRAGMENT_MAX = 40  # characters (the limit of M13)
MAX_ALLOWED = 7  # a growth of the allow-list is a visible edit of this number
# (module, enclosing function, a fragment of the static text of at most 40 characters): reason
ALLOW = {
    ("rails", "check_take", "nothing for a Driver to do"): "stop now: the CR has ended",
    ("rails", "check_take", "it starts once each is"): "stop now: it starts by itself once met",
    ("rails", "check_take", "a fix of the release must be merged"): "stop now: the release "
    "starts once its fixes end",
    ("rails_release", "fix_go", "only a ready fix merges"): "stop now: it merges once ready",
    ("leases", "lost", "stop now: nothing recorded"): "stop now: the unit is no longer the "
    "caller's",
    ("leases", "ttl_seconds", "is seconds, not"): "test seam: set only by the test suite",
    ("leases", "minute_seconds", "is seconds, not"): "test seam: set only by the test suite",
}
HELPER_SPAN = re.compile(r"<helper:(\w+)>")


def _static_text(node: ast.AST) -> str:
    """The static text of a message: constants, the constant parts of f-strings, both sides of a
    `+`; a formatted value is `<>`, a call of a command helper `<helper:name>`."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(_static_text(v) for v in node.values)
    if isinstance(node, ast.FormattedValue):
        call = node.value
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id in COMMAND_HELPERS
        ):
            return f"<helper:{call.func.id}>"
        return "<>"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _static_text(node.left) + _static_text(node.right)
    return "<>"


def _refusals() -> list[tuple[str, str, int, str]]:
    """(module, enclosing function, line, static text) of each `ChantierError(...)` call."""
    found: list[tuple[str, str, int, str]] = []
    for name, module in FILES.items():
        tree = ast.parse(Path(module.__file__ or "").read_text(encoding="utf-8"))

        def visit(node: ast.AST, func: str, name: str = name) -> None:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                func = node.name
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "ChantierError"
                and node.args
            ):
                found.append((name, func, node.lineno, _static_text(node.args[0])))
            for child in ast.iter_child_nodes(node):
                visit(child, func)

        visit(tree, "")
    return found


def _command_names() -> set[str]:
    parser = chantier.cli._parser()
    (sub,) = (a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return set(sub.choices)


def _names_a_command(text: str, commands: set[str]) -> bool:
    for span in re.findall(r"`([^`]*)`", text):
        first = span.split(maxsplit=1)[0] if span.split() else ""
        if first in commands or HELPER_SPAN.fullmatch(span):
            return True
    return False


def test_M9_every_refusal_names_the_next_command_or_is_allow_listed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    commands = _command_names()
    refusals = _refusals()
    assert len(refusals) >= MIN_REFUSALS, f"the scan found {len(refusals)} refusals"
    matched: set[tuple[str, str, str]] = set()
    bad: list[str] = []
    for module, func, line, text in refusals:
        if _names_a_command(text, commands):
            continue
        keys = [k for k in ALLOW if k[:2] == (module, func) and k[2] in text]
        if keys:
            matched.update(keys)
        else:
            bad.append(f"{module}.py:{line} ({func}): {text!r}")
    assert not bad, "a refusal names no next command and is not allow-listed:\n" + "\n".join(bad)
    assert not set(ALLOW) - matched, f"stale allow-list entries: {set(ALLOW) - matched}"
    assert all(len(k[2]) <= FRAGMENT_MAX for k in ALLOW)
    assert len(ALLOW) <= MAX_ALLOWED
    with capsys.disabled():
        n = len(ALLOW)
        print(f"\nM9: {len(refusals)} refusals scanned in {len(FILES)} files, {n} allow-listed")


@pytest.mark.parametrize("unit", ["CR-101", "stack", "O-1"])
def test_M9_the_reclaim_helper_returns_a_command(unit: str) -> None:
    lease = Lease(n=1, taken="t", renewed="t", expires="t")
    commands = _command_names()
    for short in (False, True):
        assert reclaim_command(unit, lease, short=short).split()[0] in commands

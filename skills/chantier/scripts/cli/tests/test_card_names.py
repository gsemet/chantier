"""No line the CLI or the hook can print names a card file that is gone (F18): every string of the
CLI's Python files and every literal of the hook is read for a card file's name."""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from functools import cache
from pathlib import Path

from conftest import PLUGIN_ROOT, SKILL

SRC = Path(__file__).resolve().parents[1] / "src"
HOOK = PLUGIN_ROOT / "hooks" / "register.tsx"
REFS = SKILL / "references"

# Every path the swap removed from references/. A name is allowed again only while a file of that
# name exists under references/.
_NAMES = """
chief-of-staff-any chief-of-staff-batch-end chief-of-staff-batch-start
chief-of-staff-direct chief-of-staff-grill chief-of-staff-merge chief-of-staff-release
chief-of-staff-steering chief-of-staff-writer driver-conflicts driver-handback-other
driver-matrix driver-pr-extras driver-refused driver-retake driver-session
driver-trouble driver foreman-conflict foreman-hold foreman-lost-driver foreman-merge
foreman-pause foreman-refused foreman-release foreman-stack host-core-claude-code
host-core-copilot hosts/copilot release-driver-end release-driver-merged
release-driver-notes release-driver-ship reload-rules role-core
session-start-chief-of-staff session-start-griller session-start stack-driver-changes
stack-driver-joins stack-driver-make stack-driver-restack startup-core titles
"""
REMOVED = (*(f"{name}.md" for name in _NAMES.split()), "startup-manifest.json")

_REFERENCE = re.compile(r"references/([\w./-]*\.(?:md|json))(?![\w-])")
_HOSTS = re.compile(r"(?<![\w-])hosts/([\w.-]*\.md)(?![\w-])")
_LITERAL = re.compile(r"""'(?:\\.|[^'\\\n])*'|"(?:\\.|[^"\\\n])*"|`(?:\\.|[^`\\])*`""")


@cache
def _gone() -> re.Pattern[str]:
    """The removed basenames that no file under references/ carries."""
    present = {p.name for p in REFS.rglob("*") if p.is_file()}
    names = sorted({name.rsplit("/", 1)[-1] for name in REMOVED} - present)
    return re.compile(rf"(?<![\w.-])(?:{'|'.join(map(re.escape, names))})(?![\w-])")


def _names(text: str) -> Iterator[str]:
    """The stale card names `text` holds."""
    for m in _REFERENCE.finditer(text):
        if not (REFS / m[1]).is_file():
            yield m[0]
    yield from _gone().findall(text)
    for m in _HOSTS.finditer(text):
        if not (REFS / "hosts" / m[1]).is_file():
            yield m[0]


def _python_strings(source: str) -> Iterator[tuple[int, str]]:
    """Every string constant: f-string parts and docstrings included."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value


def _hook_strings(source: str) -> Iterator[tuple[int, str]]:
    code = "\n".join("" if ln.lstrip().startswith("//") else ln for ln in source.split("\n"))
    for m in _LITERAL.finditer(code):
        yield code.count("\n", 0, m.start()) + 1, m[0]


def scan(file: str, strings: Iterator[tuple[int, str]]) -> list[str]:
    return sorted({f"{file}:{line}: {name}" for line, text in strings for name in _names(text)})


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_no_string_of_the_cli_or_the_hook_names_a_card_that_is_gone() -> None:
    found = [
        hit
        for path in sorted(SRC.rglob("*.py"))
        for hit in scan(path.relative_to(SRC).as_posix(), _python_strings(_read(path)))
    ]
    found += scan("hooks/register.tsx", _hook_strings(_read(HOOK)))
    assert found == []


def test_a_removed_card_named_in_a_source_fails_naming_it() -> None:
    source = 'skill = "x"\nline = f"{skill}/references/startup-core.md"\n'
    assert scan("prepared.py", _python_strings(source)) == [
        "prepared.py:2: references/startup-core.md",
        "prepared.py:2: startup-core.md",
    ]

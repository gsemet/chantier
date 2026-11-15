"""Every bullet of the scenario README's coverage list names a unit or a test that exists."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from conftest import PLUGIN_ROOT

README = PLUGIN_ROOT / "scenario" / "README.md"
RUNNER = PLUGIN_ROOT / "scenario" / "run_scenario.py"
TESTS = Path(__file__).parent
MARKER = re.compile(r"\((unit|test):\s*([^)]*)\)")


def bullets() -> list[str]:
    text = README.read_text("utf-8")
    section = text.split("## Coverage", 1)[1].split("\n## ", 1)[0]
    found: list[list[str]] = []
    for line in section.splitlines():
        if line.startswith("- "):
            found.append([line[2:]])
        elif found and line.strip():
            found[-1].append(line.strip())
    return [" ".join(parts) for parts in found]


def unit_names() -> set[str]:
    for node in ast.walk(ast.parse(RUNNER.read_text("utf-8"))):
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name, value = node.targets[0].id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name, value = node.target.id, node.value
        else:
            continue
        if name == "UNITS" and isinstance(value, ast.Dict):
            return {str(k.value) for k in value.keys if isinstance(k, ast.Constant)}
    raise AssertionError("UNITS is not defined in run_scenario.py")


def function_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text("utf-8"))
    return {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}


def problems(bullet: str, units: set[str]) -> list[str]:
    markers = MARKER.findall(bullet)
    head = bullet[:70]
    found = [f"no (unit: ...), (test: ...) in the bullet: {head!r}"]
    if not markers:
        return found
    names = [(k, v.strip()) for k, value in markers for v in value.split(",") if v.strip()]
    found = [problem(k, n, units) for k, n in names]
    return [f"{p}: {head!r}" for p in found if p]


def problem(kind: str, name: str, units: set[str]) -> str:
    if kind == "unit":
        return "" if name in units else f"unit {name!r} is not a key of UNITS"
    file, _, test = name.partition("::")
    path = TESTS / file
    if not path.is_file():
        return f"test file {file!r} does not exist"
    return "" if test in function_names(path) else f"test {test!r} is not in {file}"


def test_every_coverage_bullet_names_a_unit_or_a_test_that_exists() -> None:
    units = unit_names()
    found = bullets()
    assert found, "no bullet in the README's Coverage section"
    errors = [e for b in found for e in problems(b, units)]
    assert not errors, "\n" + "\n".join(errors)

"""The code's own targets: the sizes of files and functions, no import cycle, and one project
for the CLI. `just lint` holds the style; these two checks hold what a linter does not."""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

CLI = Path(__file__).resolve().parents[1]
MAX_FILE_LINES = 400
MAX_FUNCTION_LINES = 50
SCOPE = [
    path
    for path in sorted(CLI.rglob("*.py"))
    if not {".venv", "__pycache__"} & set(path.relative_to(CLI).parts)
]


def _module(path: Path) -> str:
    parts = list(path.relative_to(CLI / "src").with_suffix("").parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _imports(path: Path) -> set[str]:
    """The `chantier` modules a file imports, imports inside functions included."""
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("chantier"):
            found.add(node.module)
            found.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Import):
            found.update(a.name for a in node.names if a.name.startswith("chantier"))
    return found


def _cycle(graph: dict[str, set[str]]) -> list[str] | None:
    state: dict[str, int] = {}
    trail: list[str] = []

    def visit(name: str) -> list[str] | None:
        state[name] = 1
        trail.append(name)
        for nxt in sorted(graph[name]):
            if state.get(nxt) == 1:
                return [*trail[trail.index(nxt) :], nxt]
            if nxt in graph and nxt not in state and (found := visit(nxt)):
                return found
        trail.pop()
        state[name] = 2
        return None

    for name in sorted(graph):
        if name not in state and (found := visit(name)):
            return found
    return None


def _size_problems(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    problems = []
    if len(text.splitlines()) > MAX_FILE_LINES:
        problems.append(f"{path.relative_to(CLI)}: over {MAX_FILE_LINES} lines")
    functions = [
        n
        for n in ast.walk(ast.parse(text))
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    for node in functions:
        size = (node.end_lineno or node.lineno) - node.lineno + 1
        if size > MAX_FUNCTION_LINES:
            problems.append(f"{path.relative_to(CLI)}: {node.name} has {size} lines")
    return problems


def test_files_and_functions_are_small_and_the_imports_have_no_cycle() -> None:
    problems = [p for path in SCOPE for p in _size_problems(path)]
    graph = {_module(p): _imports(p) for p in SCOPE if (CLI / "src") in p.parents}
    cycle = _cycle({name: {m for m in deps if m in graph} for name, deps in graph.items()})
    if cycle:
        problems.append("import cycle: " + " -> ".join(cycle))
    assert not problems, "\n".join(problems)


def test_one_root_project_holds_the_dependencies_and_nothing_else_is_a_script() -> None:
    root = CLI.parents[3]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert all("==" in dep for dep in project["project"]["dependencies"]), "pin each with =="
    assert project["tool"]["uv"]["no-build"] is True
    assert not (CLI / "pyproject.toml").exists()
    assert not (CLI / "chantier.py").exists()
    blocks = [
        path.name
        for path in SCOPE
        if re.search(r"(?m)^# /// script\r?$", path.read_text(encoding="utf-8"))
    ]
    assert blocks == ["session_usage.py"], blocks

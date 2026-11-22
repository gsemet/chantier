"""The structure test of the plan's store reads (spec CR-419 section 6): the store-only modules
read the planning folder through the plan's store, never directly. It parses their source, as
shipped, with `ast` and names the module, the function and the line of a direct read. The reads
that stay direct (spec 5.5) are the table below, one entry per module and function with its
reason; an entry that no longer matches a call fails the test."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src" / "chantier"
PACKAGES = ("board", "hub", "status", "commands/cost", "lifecycle")
MODULES = (
    "core/repo.py",
    "core/surface_batches.py",
    "core/records.py",
    "core/seat.py",
    "core/waits.py",
    "core/batch_records.py",
    "summaries/store.py",
    "summaries/view.py",
    "core/batch.py",
    "core/leases.py",
    "gate_queue.py",
    "gate_slots.py",
    "rails.py",
    "history.py",
    "summaries/sources.py",
    "summaries/gaps.py",
    "summaries/origin.py",
    "summaries/title.py",
    "commands/crs.py",
)
READS = {
    "read_text",
    "read_bytes",
    "iterdir",
    "glob",
    "rglob",
    "is_file",
    "is_dir",
    "exists",
    "stat",
    "lstat",
    "open",
}
OS_READS = {"walk", "scandir", "listdir"}
IMPORTED = {"read_text", "read_json"}  # `core/files.py`'s, whose use is a direct read
WRITE_MODE = set("wax+")
IMPORT = "<import>"

# (module, function) -> why the read stays direct (spec 5.5); the function is the qualified name
# of the innermost definition around the call, `<module>` outside one.
EXEMPT: dict[tuple[str, str], str] = {
    ("board/state.py", "origin_of"): "the code repository's folder, not the planning folder",
    ("board/static.py", "*"): "the web client's files",
    ("board/command.py", "*"): "the web client's files",
    ("board/key.py", "*"): "the key, in the git folder",
    ("board/address.py", "*"): "an HTTP address",
    ("hub/state.py", "*"): "the git folder (chantier/server.json)",
    ("hub/lock.py", "*"): "the git folder (the locks)",
    ("core/repo.py", IMPORT): "checkout.yml and project.md, beside the planning folder",
    ("core/repo.py", "read_keyed"): "checkout.yml, the project's folder beside the planning folder",
    ("core/repo.py", "surface_projects"): "the surface's projects/, not the planning folder",
    ("core/repo.py", "Repo.find"): "the look made before a store exists",
    ("core/repo.py", "Repo._external"): "the look made before a store exists (clone, project.md)",
    ("core/repo.py", "Repo.missing_clone"): "the clone and the project's project.md",
    ("status/views.py", "_documents"): "a project file of the code repository, a spec's link",
    ("gate_slots.py", "lock_text"): "a held OS lock file, read past its locked byte (spec 5.3)",
    ("rails.py", "worktree_print"): "a CR's worktree (is_dir, and its untracked files' bytes)",
    ("commands/crs.py", "cr_worktree"): "a CR's worktree, a folder of the code repository",
}


def _is_store(node: ast.expr) -> bool:
    """A receiver that is a store: a name or an attribute whose last name holds `store`."""
    if isinstance(node, ast.Name):
        return "store" in node.id
    if isinstance(node, ast.Attribute):
        return "store" in node.attr
    return False


def _writes(call: ast.Call, mode_at: int) -> bool:
    """`open` with a literal mode that writes or appends."""
    mode: ast.expr | None = call.args[mode_at] if len(call.args) > mode_at else None
    for kw in call.keywords:
        if kw.arg == "mode":
            mode = kw.value
    return (
        isinstance(mode, ast.Constant)
        and isinstance(mode.value, str)
        and bool(WRITE_MODE & set(mode.value))
    )


class _Finder(ast.NodeVisitor):
    def __init__(self) -> None:
        self.found: list[tuple[str, int, str]] = []
        self.scope: list[str] = []

    def _in(self, node: ast.AST, name: str) -> None:
        self.scope.append(name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._in(node, node.name)

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._in(node, node.name)

    def _add(self, line: int, what: str, name: str | None = None) -> None:
        where = ".".join(self.scope) or "<module>"
        self.found.append((name or where, line, what))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module and node.module.endswith("core.files"):
            for alias in node.names:
                if alias.name in IMPORTED:
                    self._add(node.lineno, f"import of {alias.name}", IMPORT)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Name) and func.id in {"open", *IMPORTED}:
            if not (func.id == "open" and _writes(node, 1)):
                self._add(node.lineno, f"{func.id}()")
        elif isinstance(func, ast.Attribute):
            recv = func.value
            if isinstance(recv, ast.Name) and recv.id == "os" and func.attr in OS_READS:
                self._add(node.lineno, f"os.{func.attr}()")
            elif (
                func.attr in READS
                and not _is_store(recv)
                and (func.attr != "open" or not _writes(node, 0))
            ):
                self._add(node.lineno, f".{func.attr}()")
        self.generic_visit(node)


def direct_reads(source: str) -> list[tuple[str, int, str]]:
    """(function, line, call) of every direct read in `source`."""
    finder = _Finder()
    finder.visit(ast.parse(source))
    return finder.found


def listed() -> list[str]:
    rels = list(MODULES)
    for package in PACKAGES:
        rels += [p.relative_to(SRC).as_posix() for p in sorted((SRC / package).rglob("*.py"))]
    return rels


def _exempt(module: str, function: str) -> tuple[str, str] | None:
    for key in ((module, function), (module, "*")):
        if key in EXEMPT:
            return key
    return None


def test_the_store_only_modules_read_through_the_store() -> None:
    bad: list[str] = []
    used: set[tuple[str, str]] = set()
    for module in listed():
        for function, line, what in direct_reads((SRC / module).read_text(encoding="utf-8")):
            key = _exempt(module, function)
            if key:
                used.add(key)
            else:
                bad.append(f"{module}:{line} in {function}: {what}")
    assert not bad, "a direct read of the planning folder:\n" + "\n".join(bad)
    stale = sorted(set(EXEMPT) - used)
    assert not stale, f"an exemption that matches no call: {stale}"


def test_the_listed_modules_exist() -> None:
    assert all((SRC / module).is_file() for module in listed())
    assert len(listed()) > len(MODULES)


@pytest.mark.parametrize(
    ("source", "found"),
    [
        ("def f(p):\n    return p.read_text()\n", [("f", 2, ".read_text()")]),
        ("def f(p):\n    return (p / 'a').is_file()\n", [("f", 2, ".is_file()")]),
        ("import os\ndef f(p):\n    return os.walk(p)\n", [("f", 3, "os.walk()")]),
        ("def f(p):\n    return open(p)\n", [("f", 2, "open()")]),
        ("from chantier.core.files import read_json\n", [(IMPORT, 1, "import of read_json")]),
        ("def f(store, p):\n    return store.read_text(p)\n", []),
        ("class C:\n    def f(self):\n        return self.store.exists('a')\n", []),
        ("def f(p):\n    return open(p, 'ab')\n", []),
        ("def f(p):\n    return p.open(mode='w')\n", []),
    ],
)
def test_a_direct_read_in_a_prepared_source_is_found(
    source: str, found: list[tuple[str, int, str]]
) -> None:
    assert direct_reads(source) == found

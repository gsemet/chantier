"""The web board's structure: its modules, the lazy imports of its server, the frame it ships.
The behaviour (key, guard, state, files, costs, seats) belongs to `just scenario`."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

CLI = Path(__file__).resolve().parents[1]
BOARD = CLI / "src" / "chantier" / "board"
MODULES = [
    "command",
    "address",
    "key",
    "projects",
    "state",
    "files",
    "fingerprint",
    "costs",
    "seats",
    "app",
    "routes",
    "guard",
    "reply",
    "static",
    "context",
]
LAZY = ("starlette", "uvicorn")


def _top_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_the_board_is_one_package_of_small_modules_with_no_server_of_html() -> None:
    missing = [m for m in MODULES if not (BOARD / f"{m}.py").is_file()]
    gone = [m for m in ("collect", "render", "server") if (BOARD / f"{m}.py").exists()]
    assert not missing and not gone, f"missing {missing}, still there {gone}"


def test_the_web_framework_loads_only_when_the_board_serves() -> None:
    root = CLI.parents[3]
    ruff = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["ruff"]
    banned = ruff["lint"]["flake8-tidy-imports"]["banned-module-level-imports"]
    assert all(name in banned for name in LAZY), banned
    eager = [
        str(path.relative_to(CLI))
        for path in sorted((CLI / "src").rglob("*.py"))
        if set(LAZY) & _top_level_imports(path)
    ]
    assert not eager, eager


def test_the_frame_is_shipped_with_the_package() -> None:
    web = BOARD / "web"
    for name in (
        "index.html",
        "js/main.js",
        "js/core/store.js",
        "js/views/registry.js",
        "css/tokens.css",
        "css/shell.css",
        "js/i18n/en.js",
        "js/i18n/fr.js",
    ):
        assert (web / name).is_file(), name

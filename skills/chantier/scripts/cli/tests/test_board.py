"""The web board's structure: its modules, the lazy imports of its server, the frame it ships.
The behaviour (key, guard, state, files, costs, seats) belongs to `just scenario`."""

from __future__ import annotations

import ast
import io
import socket
import tomllib
import urllib.error
from pathlib import Path

import pytest
from batch_helpers import prepared
from conftest import Chantier

from chantier.board import address
from chantier.board.guard import NEEDS_KEY
from chantier.core.errors import EXIT_EXTERNAL

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
    "journal",
    "write_api",
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


def test_a_held_port_is_refused_with_the_port_and_the_way_out(
    repo: Path, chantier: Chantier
) -> None:
    prepared(repo, chantier, "Board one")
    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))
        held.listen()
        port = held.getsockname()[1]
        code, out, err = chantier("board", "--host", "127.0.0.1", "--port", str(port))
    assert code == EXIT_EXTERNAL and not out
    assert err.count("\n") == 1 and err.startswith("error: board not started: ")
    assert f"port {port}" in err and "--port" in err


@pytest.mark.parametrize(
    ("code", "body", "expected"),
    [(401, NEEDS_KEY, "another-key"), (401, "nope", "other"), (404, NEEDS_KEY, "other")],
)
def test_the_probe_tells_a_board_behind_another_key_from_any_other_answer(
    monkeypatch: pytest.MonkeyPatch, code: int, body: str, expected: str
) -> None:
    def call(*_a: object, **_k: object) -> None:
        raise urllib.error.HTTPError("u", code, "x", {}, io.BytesIO(body.encode()))  # type: ignore[arg-type]

    monkeypatch.setattr(address, "_call", call)
    assert address.probe("127.0.0.1", 1, "k") == expected

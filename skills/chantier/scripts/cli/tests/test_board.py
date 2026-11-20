"""The web board's structure: its modules, the lazy imports of its server, the frame it ships.
The behaviour (key, guard, state, files, costs, seats) belongs to `just scenario`."""

from __future__ import annotations

import ast
import io
import json
import socket
import subprocess
import tomllib
import urllib.error
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import prepared
from conftest import Chantier

from chantier.board import address, reply, routes
from chantier.board.context import Context, Request
from chantier.board.guard import NEEDS_KEY
from chantier.board.key import KeyFile
from chantier.board.projects import open_projects
from chantier.board.seats import Seats
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
    "config_api",
    "writer_api",
    "prs",
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
        "js/ui/batch-nav.js",
        "css/batch-nav.css",
        "css/tokens.css",
        "css/shell.css",
        "js/i18n/en.js",
        "js/i18n/fr.js",
        "fonts/Inter-Regular.woff2",
        "fonts/Inter-Medium.woff2",
        "fonts/OFL.txt",
    ):
        assert (web / name).is_file(), name
    assert "font-src 'self'" in reply.HTML_POLICY
    assert "img-src 'self' data:" in reply.HTML_POLICY  # the source the image copy was proved with


def test_a_held_port_is_refused_with_the_port_and_the_way_out(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared(repo, chantier, "Board one")

    def never_answers(*_a: object, **_k: object) -> None:
        raise TimeoutError("timed out")  # what `_call` raises after its 2 s on a silent port

    monkeypatch.setattr(address, "_call", never_answers)
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


def _git_init(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(folder)], check=True)


def _board_payload(root: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setenv("CHANTIER_ROOT", str(root))
    monkeypatch.chdir(root)
    projects = open_projects()
    ctx = Context(projects, KeyFile(root / "key.json"), Seats(projects), "0", lambda: None)
    body: dict[str, Any] = json.loads(routes.board(ctx, Request("GET", "/api/board", {}, {})).body)
    return body


def test_the_board_gives_a_surface_its_root_and_each_project_its_two_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    surface = tmp_path / "plans"
    _git_init(surface)
    for name in ("alpha", "beta"):
        (surface / "projects" / name / "changes").mkdir(parents=True)
    (surface / "projects" / "alpha" / "checkout.yml").write_text(
        "repo: ../../../code/  # as written\n", encoding="utf-8"
    )
    got = _board_payload(surface, monkeypatch)
    assert got["surface"] is True
    assert got["served"] == surface.resolve().as_posix()
    paths = {p["id"]: (p["folder"], p["repo"]) for p in got["projects"]}
    assert paths == {
        "alpha": ("projects/alpha/", "../../../code/"),
        "beta": ("projects/beta/", ".repo"),
    }


def test_the_board_adds_no_path_to_an_in_project_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git_init(tmp_path / "solo")
    (tmp_path / "solo" / ".agents" / "changes").mkdir(parents=True)
    got = _board_payload(tmp_path / "solo", monkeypatch)
    assert got["surface"] is False
    (line,) = got["projects"]
    assert "folder" not in line and "repo" not in line


@pytest.mark.parametrize(
    ("remote", "served"),
    [
        ("https://github.com/owner/repo.git", "https://github.com/owner/repo.git"),
        ("https://user:s3cret@github.com/owner/repo.git", "https://github.com/owner/repo.git"),
        ("ssh://git@github.com/owner/repo.git", "ssh://github.com/owner/repo.git"),
        ("", ""),
    ],
)
def test_the_board_gives_each_project_its_repository_path_and_its_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, remote: str, served: str
) -> None:
    _git_init(tmp_path / "solo")
    (tmp_path / "solo" / ".agents" / "changes").mkdir(parents=True)
    if remote:
        subprocess.run(
            ["git", "-C", str(tmp_path / "solo"), "remote", "add", "origin", remote], check=True
        )
    got = _board_payload(tmp_path / "solo", monkeypatch)
    (line,) = got["projects"]
    assert line["repo_path"] == (tmp_path / "solo").resolve().as_posix()
    assert line["origin"] == served
    assert got["served_origin"] == served

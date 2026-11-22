"""The web client lives outside the server's package, and the server serves the folder `--ui`
names (or none)."""

from __future__ import annotations

import ast
import os
import subprocess
from pathlib import Path

import pytest
from batch_helpers import prepared
from conftest import Chantier

from chantier.board import command, reply, routes, static
from chantier.board.context import Context, Request
from chantier.board.key import KeyFile
from chantier.board.projects import open_projects
from chantier.board.seats import Seats
from chantier.core.errors import EXIT_USAGE
from chantier.declare.serve import SHIPPED_UI

OK, NOT_FOUND, NO_KEY, SEE_OTHER = 200, 404, 401, 303
PKG = Path(__file__).resolve().parents[1] / "src" / "chantier"
REFUSAL = (
    "error: --ui {arg}: not a folder with an index.html: give a folder of static files, or none"
)
APPLIED = "--ui not applied: a board already serves this surface; stop it to change what it serves"


def _names_the_client(path: Path) -> list[str]:
    found: list[str] = []
    for node in ast.walk(ast.parse(path.read_text("utf-8"))):
        if isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
        elif isinstance(node, ast.Import):
            modules = [a.name for a in node.names]
        else:
            modules = []
        found += [f"{path.name}: import {m}" for m in modules if m.startswith("chantier.clients")]
        text = node.value if isinstance(node, ast.Constant) else None
        if isinstance(text, str) and (text == "clients" or "clients/" in text):
            found.append(f"{path.name}: {text!r}")
    return found


def test_the_web_client_is_outside_the_servers_package_which_names_nothing_of_it() -> None:
    assert not (PKG / "board" / "web").exists()
    assert (PKG / "clients" / "web" / "index.html").is_file()
    assert (PKG / "clients" / "web" / "DESIGN.md").is_file()
    assert SHIPPED_UI == PKG / "clients" / "web"
    assert not list((PKG / "clients" / "web").rglob("*.py"))  # clients/tui/ is Python
    named = [n for path in (PKG / "board").rglob("*.py") for n in _names_the_client(path)]
    assert not named, named


@pytest.fixture
def served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project's folder where a context can be made; the UI folder is `ui/` in it."""
    root = tmp_path / "solo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".agents" / "changes").mkdir(parents=True)
    monkeypatch.setenv("CHANTIER_ROOT", str(root))
    monkeypatch.chdir(root)
    return root


def _ask(root: Path, ui: Path | None, path: str, key: bool = True) -> reply.Reply:
    projects = open_projects()
    keyfile = root / "key.json"
    keyfile.write_text('{"key": "k1"}', encoding="utf-8")
    ctx = Context(projects, KeyFile(keyfile), Seats(projects), "0", lambda: None, ui)
    head = {"x-chantier-board-key": "k1", "host": "board"} if key else {"host": "board"}
    query = {"k": "k1"} if path.endswith("?k=k1") else {}
    return routes.handle(ctx, Request("GET", path.split("?", 1)[0], query, head))


def test_a_folder_is_served_by_its_files_and_types_inside_it_only(served: Path) -> None:
    ui = served / "ui"
    ui.mkdir()
    (ui / "index.html").write_text("<p>mine</p>", encoding="utf-8")
    (ui / "app.js").write_text("export {};", encoding="utf-8")
    (ui / "notes.txt").write_text("no", encoding="utf-8")
    (served / "outside.txt").write_text("secret", encoding="utf-8")
    (served / "outside.js").write_text("secret", encoding="utf-8")
    page = _ask(served, ui, "/")
    assert page.status == OK and page.body == b"<p>mine</p>"
    assert page.kind == "text/html; charset=utf-8"
    assert page.all_headers()["Content-Security-Policy"] == reply.HTML_POLICY
    assert _ask(served, ui, "/app.js").kind == "text/javascript; charset=utf-8"
    assert _ask(served, ui, "/notes.txt").status == NOT_FOUND
    assert _ask(served, ui, "/../outside.js").status == NOT_FOUND
    assert _ask(served, ui, "/", key=False).status == NO_KEY
    try:
        os.symlink(served / "outside.js", ui / "link.js")
    except (OSError, NotImplementedError):
        pytest.skip("this OS does not let the test make a symlink; the escape is not checked")
    assert _ask(served, ui, "/link.js").status == NOT_FOUND


@pytest.mark.parametrize("path", ["/", "/index.html", "/js/main.js"])
def test_with_no_ui_the_page_is_a_404_line_and_the_api_answers(served: Path, path: str) -> None:
    got = _ask(served, None, path)
    assert got.status == NOT_FOUND and got.body.decode().strip() == static.NO_UI
    assert _ask(served, None, "/api/board").status == OK
    exchange = _ask(served, None, "/?k=k1", key=False)
    assert exchange.status == SEE_OTHER and "Set-Cookie" in exchange.all_headers()


@pytest.fixture
def project(repo: Path, chantier: Chantier) -> Path:
    prepared(repo, chantier, "Board ui")
    return repo


def _server_json(repo: Path) -> Path:
    return repo / ".git" / "chantier" / "server.json"


@pytest.mark.parametrize("kind", ["missing", "file", "no-index"])
def test_a_ui_that_is_not_a_folder_with_an_index_is_refused_and_nothing_is_written(
    project: Path, chantier: Chantier, tmp_path: Path, kind: str
) -> None:
    arg = tmp_path / "ui"
    if kind == "file":
        arg.write_text("x", encoding="utf-8")
    elif kind == "no-index":
        arg.mkdir()
    code, out, err = chantier("serve", "--host", "127.0.0.1", "--port", "0", "--ui", arg)
    assert code == EXIT_USAGE and not out
    assert err.strip() == REFUSAL.format(arg=arg)
    assert not _server_json(project).exists()


@pytest.mark.parametrize("ui", ["none", "folder", None, "bad"])
def test_ui_on_a_board_already_running_is_not_applied_and_said(
    project: Path,
    chantier: Chantier,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ui: str | None,
) -> None:
    looked: list[int] = []

    def answers(*_a: object, **_k: object) -> tuple[str, int]:
        looked.append(1)
        return "127.0.0.1", 4321

    monkeypatch.setattr(command, "_answering", answers)
    good = tmp_path / "ui"
    good.mkdir()
    (good / "index.html").write_text("<p/>", encoding="utf-8")
    args: list[object] = ["serve", "--host", "127.0.0.1", "--port", "4321"]
    if ui is not None:
        args += ["--ui", {"none": "none", "folder": good, "bad": tmp_path / "nope"}[ui]]
    code, out, err = chantier(*args)
    if ui == "bad":
        assert code == EXIT_USAGE and not looked and "not a folder with an index.html" in err
        return
    assert code == 0 and looked
    assert out[0].startswith("board already running at http://")
    assert [line for line in out if line.startswith("--ui")] == ([APPLIED] if ui else [])

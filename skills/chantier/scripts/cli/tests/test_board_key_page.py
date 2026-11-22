"""CR-460: the refusal page with its field, the pasted key or link, the `SameSite=Lax` cookie, and
the web client's key notice (read from the files as they ship)."""

from __future__ import annotations

import base64
import hashlib
import re
from html import escape
from pathlib import Path
from urllib.parse import quote

import pytest
from conftest import Chantier
from test_board_prs import Board, served

from chantier.board import guard, key_page, routes
from chantier.board import key as keys
from chantier.board.context import Request
from chantier.board.reply import Reply
from chantier.commands import live

WEB = Path(__file__).resolve().parents[1] / "src" / "chantier" / "clients" / "web"
KEY = "abc-DEF_123"
LINKS = [
    "http://127.0.0.1:8765/?k={key}",
    "https://host.example:9/pre/fix/?p=x&k={key}&v=batch",
    "http://[::1]:8765/index.html?a=1&k={key}",
]
SEE_OTHER, NO_KEY = 303, 401
HTML = {"accept": "text/html,application/xhtml+xml"}
FRENCH = {**HTML, "accept-language": "fr-FR,en;q=0.5"}


@pytest.fixture
def board(repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch) -> Board:
    return served(repo, chantier, monkeypatch)


def _get(
    b: Board, path: str, query: dict[str, str] | None = None, head: dict[str, str] | None = None
) -> Reply:
    return routes.handle(
        b.ctx, Request("GET", path, query or {}, {"host": "board", **(head or {})})
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (KEY, KEY),
        (f"  {KEY}\n", KEY),
        (f"http://127.0.0.1:8765/?k={KEY}", KEY),
        (f"http://h/pre/?p=x&k={KEY}&v=y", KEY),
        (f"?k={KEY}", KEY),
        (f"k={KEY}", KEY),
        (f" http://h/?k={KEY} ", KEY),
        ("http://127.0.0.1:8765/", ""),
        ("http://127.0.0.1:8765/?p=x", ""),
        (quote(f"http://127.0.0.1:8765/?k={KEY}", safe=""), KEY),
        ("http://[bad/?k=x", ""),
        ("", ""),
    ],
)
def test_the_pasted_text_gives_the_key_or_nothing(raw: str, expected: str) -> None:
    assert guard.pasted_key(raw) == expected


@pytest.mark.parametrize("link", LINKS)
def test_every_link_the_live_client_reads_gives_the_same_key(link: str) -> None:
    text = link.format(key=KEY)
    assert live.from_link(text)[1] == KEY == guard.pasted_key(text)


@pytest.mark.parametrize("which", ["private", "read"])
@pytest.mark.parametrize("form", ["bare", "blanks", "link", "query", "encoded"])
def test_each_pasted_form_sets_only_its_own_cookie(board: Board, which: str, form: str) -> None:
    secret = board.key if which == "private" else board.ctx.key.read_current()
    k = {
        "bare": secret,
        "blanks": f" {secret} ",
        "link": f"http://127.0.0.1:8765/?k={secret}",
        "query": f"?k={secret}",
        "encoded": quote(f"http://127.0.0.1:8765/?k={secret}", safe=""),
    }[form]
    got = _get(board, "/", {"k": k, "p": "x"})
    cookie = got.headers["Set-Cookie"]
    name = board.ctx.cookie + ("" if which == "private" else "_read")
    assert got.status == SEE_OTHER and got.headers["Location"] == "./?p=x"
    assert cookie.startswith(f"{name}={secret};") and "SameSite=Lax" in cookie
    assert "Strict" not in cookie and "k=" not in got.headers["Location"]


def test_the_cookie_is_lax_and_never_strict() -> None:
    cookie = keys.set_cookie("v", "n")
    assert "SameSite=Lax" in cookie and "Strict" not in cookie and "HttpOnly" in cookie


def test_the_page_load_with_no_key_gets_the_form(board: Board) -> None:
    got = _get(board, "/", head=HTML)
    page = got.body.decode()
    assert got.status == NO_KEY and got.kind.startswith("text/html")
    assert '<form method="get" action="./">' in page and 'name="k"' in page
    assert "<script" not in page and 'name="viewport"' in page
    policy = got.all_headers()["Content-Security-Policy"]
    digest = base64.b64encode(hashlib.sha256(key_page.STYLE.encode()).digest()).decode()
    assert "script-src 'none'" in policy and "form-action 'self'" in policy
    assert f"style-src 'sha256-{digest}'" in policy
    assert got.all_headers()["Cache-Control"] == "no-store"
    assert key_page.WORDS["en"]["wrong"] not in page


def test_the_page_speaks_french_keeps_other_parameters_and_escapes(board: Board) -> None:
    got = _get(board, "/", {"p": "x", "v": "batch", "q": "<script>"}, FRENCH)
    page = got.body.decode()
    assert key_page.WORDS["fr"]["needs"] in page and key_page.WORDS["fr"]["open"] in page
    assert 'name="p" value="x"' in page and 'name="v" value="batch"' in page
    assert "<script>" not in page and "&lt;script&gt;" in page


def test_a_proxy_prefix_gets_a_relative_action(board: Board) -> None:
    page = _get(board, "/pre/fix/index.html", head={**HTML, "x-forwarded-host": "b.example"}).body
    assert b'action="./index.html"' in page


def test_a_wrong_key_on_a_page_load_says_so(board: Board) -> None:
    got = _get(board, "/", {"k": "nope"}, HTML)
    assert got.status == NO_KEY and escape(key_page.WORDS["en"]["wrong"]) in got.body.decode()
    assert "set-cookie" not in {k.lower() for k in got.headers}


@pytest.mark.parametrize(
    "path", ["/", "/api/board", "/api/v1/call/board.get", "/js/main.js", "/api/v1/projects/x/file"]
)
@pytest.mark.parametrize("wrong", [False, True])
def test_every_other_request_keeps_the_text_401(board: Board, path: str, wrong: bool) -> None:
    got = _get(board, path, {"k": "nope"} if wrong else None)
    assert got.status == NO_KEY and guard.NEEDS_KEY in got.body.decode()
    assert got.kind.startswith("text/plain")


# the web client, read from the repository as it ships
STORES = {"core/store.js", "api/griller.js"}
FORBIDDEN = re.compile(r"\b(localStorage|sessionStorage|document\.cookie)\b")


def _storage_users(files: dict[str, str]) -> set[str]:
    return {name for name, text in files.items() if FORBIDDEN.search(text)}


def _scripts() -> dict[str, str]:
    return {
        p.relative_to(WEB / "js").as_posix(): p.read_text("utf-8")
        for p in (WEB / "js").rglob("*.js")
    }


def test_web_storage_is_used_only_by_the_two_known_modules() -> None:
    scripts = _scripts()
    assert _storage_users(scripts) == STORES
    assert _storage_users({**scripts, "ui/other.js": "localStorage.setItem('k', key);"}) == {
        *STORES,
        "ui/other.js",
    }
    assert not _storage_users({"ui/key-notice.js": scripts["ui/key-notice.js"]})


@pytest.mark.parametrize("language", ["en", "fr"])
def test_the_key_notice_words_exist_in_both_languages(language: str) -> None:
    folder = WEB / "js" / "i18n"  # `<language>.js` and the `<language>-board.js` merged into it
    text = (folder / f"{language}.js").read_text("utf-8") + (
        folder / f"{language}-board.js"
    ).read_text("utf-8")
    for word in ("notice.key", "notice.key_field", "notice.key_open"):
        assert f"'{word}'" in text


def test_the_design_file_names_the_key_notice() -> None:
    assert "## The key notice" in (WEB / "DESIGN.md").read_text("utf-8")

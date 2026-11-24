"""The web board's menu and panel as shipped: no Kanban page, Notifications, Help last, the Grill
button off, the panel's backdrop, the History's filter words in both languages, and the public
key's reading of the board's feed. Static reads of the web client's files."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from chantier.board import overview

BOTH = 2  # the feed key is built in the view's two places
WEB = Path(__file__).resolve().parents[1] / "src" / "chantier" / "clients" / "web"
DOCS = Path(__file__).resolve().parents[5] / "docs"


def _read(*parts: str) -> str:
    return WEB.joinpath(*parts).read_text(encoding="utf-8")


def test_the_kanban_page_is_gone_but_the_batch_kanban_stays() -> None:
    registry = _read("js", "views", "registry.js")
    assert "kanban" not in re.findall(r"id: '(\w+)'", registry)
    for gone in (("js", "views", "kanban.js"), ("css", "views", "kanban.css")):
        assert not WEB.joinpath(*gone).exists()
    for present in ("batch-kanban.js", "kanban-cards.js"):
        assert WEB.joinpath("js", "views", present).exists()
    assert "kanban.css" not in _read("index.html")
    for path in WEB.rglob("*.js"):
        text = path.read_text(encoding="utf-8")
        assert "go: 'kanban'" not in text and 'data-go="kanban"' not in text, path.name
    assert not (DOCS / "web-board" / "kanban-pc.png").exists()
    assert "kanban-pc" not in (DOCS / "web-board.md").read_text(encoding="utf-8")


def test_the_menu_order_ends_with_help_and_history_is_on_all_projects() -> None:
    registry = _read("js", "views", "registry.js")
    ids = re.findall(r"^\s*(?:\{ )?id: '(\w+)'", registry, re.M)
    assert ids[0] == "home" and ids[-1] == "help" and ids.index("config") == len(ids) - 2
    assert "overview: history" in registry


@pytest.mark.parametrize(("lang", "word"), [("en", "Notifications"), ("fr", "Notifications")])
def test_the_inbox_is_shown_as_notifications(lang: str, word: str) -> None:
    text = _read("js", "i18n", f"{lang}.js")
    assert f"'nav.inbox': '{word}'" in text


@pytest.mark.parametrize("lang", ["en", "fr"])
def test_the_history_filters_have_their_words_and_no_kanban_word_is_left(lang: str) -> None:
    words = _read("js", "i18n", f"{lang}-history.js")
    for key in ("history.filter_kinds", "history.filter_projects", "history.project_open"):
        assert f"'{key}'" in words
    root = _read("js", "i18n", f"{lang}.js")
    assert "'overview.no_events'" in root and "'overview.history_link'" in root
    assert "'nav.kanban'" not in root and "'new.kanban'" not in root


def test_the_grill_button_is_hidden_by_a_constant() -> None:
    text = _read("js", "panel", "griller.js")
    assert re.search(r"export const GRILL_BUTTON = false;", text)
    assert re.search(r"!GRILL_BUTTON \|\| !grillable\(", text)


def test_a_click_on_the_backdrop_leaves_through_confirm_leave() -> None:
    main = _read("js", "main.js")
    click = re.search(r"\$\('#backdrop'\)\.addEventListener\('click'.*?\}\);", main, re.S)
    assert click
    assert click.group().index("confirmLeave()") < click.group().index("closePanel()")
    assert 'id="backdrop"' in _read("index.html")
    assert "--backdrop:" in _read("css", "tokens.css")


def test_the_board_feed_holds_only_what_the_public_key_may_read() -> None:
    assert overview.FEED_ROWS == 20  # noqa: PLR2004
    source = Path(overview.__file__).read_text(encoding="utf-8")
    assert "cost" not in json.dumps(re.findall(r'"(\w+)"', source.split("def board_data")[0]))


def test_the_history_feed_key_holds_the_project() -> None:
    feed = (WEB / "js" / "views" / "history-feed.js").read_text(encoding="utf-8")
    assert "export const askedKey = (project, period, date) =>" in feed
    assert "askedKey(project, period, date)" in feed
    view = (WEB / "js" / "views" / "history.js").read_text(encoding="utf-8")
    assert (
        view.count("askedKey(snapshot().project,") + view.count("askedKey(state.project,") == BOTH
    )

"""The board's Griller in the web client, read as the files ship: its words in both languages and
used, its one place for the server's command, its sheet and its wiring in the panel."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[1] / "src" / "chantier" / "clients" / "web"
KEY = re.compile(r"^\s*'([\w.]+)':", re.M)


def _read(*parts: str) -> str:
    return WEB.joinpath(*parts).read_text(encoding="utf-8")


def test_the_words_are_the_same_keys_in_both_languages_and_all_used() -> None:
    keys = {lang: KEY.findall(_read("js", "i18n", f"{lang}-griller.js")) for lang in ("en", "fr")}
    assert keys["en"] and sorted(keys["en"]) == sorted(keys["fr"])
    for lang in ("en", "fr"):
        assert "...griller," in _read("js", "i18n", f"{lang}.js")
    code = _read("js", "panel", "griller.js") + _read("js", "panel", "griller-view.js")
    used = set(re.findall(r"'(griller\.[\w.]+)'", code))
    assert used == set(keys["en"])


def test_the_server_command_is_named_in_one_place_and_the_warning_is_word_for_word() -> None:
    named = [
        p.relative_to(WEB).as_posix()
        for p in (WEB / "js").rglob("*.js")
        if "BOARD_COMMAND = " in p.read_text(encoding="utf-8")
    ]
    assert named == ["js/panel/griller-view.js"]
    assert "'chantier board'" in _read("js", "panel", "griller-view.js")
    words = _read("js", "i18n", "en-griller.js")
    assert "`{command} --new-key` replaces both keys." in words
    assert "Your first message is your yes." in words
    assert "This conversation is shared: anyone holding the private key" in words


@pytest.mark.parametrize(
    ("file", "needles"),
    [
        ("index.html", ["css/griller.css"]),
        ("js/panel/panel.js", ["grillAction", "grillerPlace", "bindGriller", "syncGriller"]),
        ("js/panel/head.js", ["actions", 'data-place="panel-actions"']),
        ("js/panel/griller.js", ["BUCKETS", "data-grill", "watchGriller", "confirmDialog"]),
        ("js/api/griller.js", ["sessionStorage", "griller.send", "griller.stop", "griller.end"]),
        ("DESIGN.md", ["## The board's Griller"]),
    ],
)
def test_the_button_the_sheet_and_the_feed_are_wired(file: str, needles: list[str]) -> None:
    text = _read(*file.split("/"))
    assert all(needle in text for needle in needles), file


def test_only_the_transport_opens_the_feed() -> None:
    api = _read("js", "api", "griller.js")
    assert "from '../core/transport.js'" in api
    assert "WebSocket" not in api and "fetch(" not in api


def test_with_the_constant_off_the_panel_draws_no_grill_button() -> None:
    code = _read("js", "panel", "griller.js")
    assert re.search(r"^export const GRILL_BUTTON = false;$", code, re.M)
    body = code.split("export function grillAction(", 1)[1].split("\n}\n", 1)[0]
    guard = body.index("if (!GRILL_BUTTON || !grillable(target)) return '';")
    assert body.count("data-grill") == 1 and guard < body.index("data-grill")
    panel = _read("js", "panel", "panel.js")
    assert "grillAction(state, target)" in panel  # the one caller draws what the function returns
    assert "data-grill" not in panel

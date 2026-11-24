"""The History view's client files, read as they ship: the registry entry, the words in both
languages, the address keys and the sheet's link."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[1] / "src" / "chantier" / "clients" / "web"
KEY = re.compile(r"^\s*'([\w.]+)':", re.M)


def _read(*parts: str) -> str:
    return WEB.joinpath(*parts).read_text(encoding="utf-8")


def test_history_is_listed_right_after_prs_and_before_costs() -> None:
    text = _read("js", "views", "registry.js")
    ids = re.findall(r"^\s*(?:\{ )?id: '(\w+)'", text, re.M)
    assert ids.index("history") == ids.index("prs") + 1 == ids.index("costs") - 1
    entry = re.search(r"\{ id: 'history'[^}]*\}", text)
    assert entry
    assert "icon: 'history'" in entry.group() and "word: 'nav.history'" in entry.group()
    assert "count" not in entry.group() and "overview: history" in entry.group()
    assert "history:" in _read("js", "ui", "icons.js")


def test_history_words_are_the_same_keys_in_both_languages_and_merged() -> None:
    keys = {lang: KEY.findall(_read("js", "i18n", f"{lang}-history.js")) for lang in ("en", "fr")}
    assert keys["en"] and sorted(keys["en"]) == sorted(keys["fr"])
    assert len(set(keys["en"])) == len(keys["en"])
    for lang, nav in (("en", "History"), ("fr", "Historique")):
        text = _read("js", "i18n", f"{lang}.js")
        assert f"'nav.history': '{nav}'" in text and "...history," in text
    used = set(
        re.findall(r"""\bt[n]?\(\s*'(history\.[\w.]+)'""", _read("js", "views", "history.js"))
    )
    assert used <= set(keys["en"]) | {"history.rounds", "history.undated", "history.unreadable"}


@pytest.mark.parametrize(
    ("file", "needles"),
    [
        ("js/core/router.js", ["HISTORY_PERIODS", "'hp'", "'hd'", "historyOf", "historyPeriod"]),
        ("js/model/targets.js", ["'h:'"]),
        ("index.html", ["css/views/history.css"]),
    ],
)
def test_the_address_the_target_and_the_sheet_are_wired(file: str, needles: list[str]) -> None:
    text = _read(*file.split("/"))
    assert all(needle in text for needle in needles)
    if file == "index.html":
        assert text.index("views/prs.css") < text.index("views/history.css")

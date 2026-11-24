"""The Dashboard's client files, read as they ship: the chart's hover band is behind the series,
the registry entry shows on All projects between History and Help, and the words the root page
adds are in both languages."""

from __future__ import annotations

import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "src" / "chantier" / "clients" / "web"
KEY = re.compile(r"^\s*'([\w.]+)':", re.M)
USED = re.compile(r"""\bt\(\s*'(dashboard\.[\w.]+)'""")


def _read(*parts: str) -> str:
    return WEB.joinpath(*parts).read_text(encoding="utf-8")


def _rule(css: str, selector: str) -> str:
    found = re.search(rf"(?:^|\n|,\s*)\s*{re.escape(selector)}\s*(?:,[^{{]*)?\{{([^}}]*)\}}", css)
    assert found, selector
    return found[1]


def test_the_hover_band_is_behind_the_series_of_both_chart_kinds() -> None:
    css, js = _read("css", "components", "chart.css"), _read("js", "ui", "chart.js")
    # one plot holds the drawing of lines and of bars alike, and the columns that carry the band
    assert js.count('<div class="chart-plot">') == 1 and js.count("chart-svg") == 1
    assert "chart-bar" in js and "chart-line" in js
    svg, cols = _rule(css, ".chart-svg"), _rule(css, ".chart-cols")
    assert "pointer-events: none" in svg  # the columns still catch the pointer, focus and taps
    z = re.search(r"z-index:\s*(-?\d+)", svg)
    zc = re.search(r"z-index:\s*(-?\d+)", cols)
    # stacked above the columns by an explicit order, or (no order at all) by the markup's
    if z or zc:
        assert int(z[1] if z else 0) > int(zc[1] if zc else 0)
    else:
        assert js.index("chart-svg") > js.index("${columns(full)}")
    band = _rule(css, ".chart-col:hover")
    assert "background: var(--accent-tint)" in band
    assert re.search(r"\.chart-col:hover,\s*\.chart-col:focus\s*\{", css)  # the same fill on focus
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", band)
    assert "outline: 1px solid var(--accent)" in _rule(css, ".chart-col:focus-visible")


def test_dashboard_shows_on_all_projects_between_history_and_help() -> None:
    text = _read("js", "views", "registry.js")
    entry = re.search(r"\{\s*id: 'dashboard'[^}]*\}", text)
    assert entry and "overview: dashboard" in entry.group()
    shown = [
        found[1]
        for block in re.findall(r"\{\s*id: '\w+'[^}]*\}", text)
        if "overview" in block and (found := re.search(r"id: '(\w+)'", block))
    ]
    assert shown == ["home", "inbox", "history", "dashboard", "help"]  # Home, Notifications, ...
    assert "nav.dashboard" in entry.group()


def test_the_words_the_root_page_adds_are_in_both_languages_and_the_views_use_known_ones() -> None:
    keys = {
        lang: set(KEY.findall(_read("js", "i18n", f"{lang}-dashboard.js"))) for lang in ("en", "fr")
    }
    assert keys["en"] == keys["fr"]
    added = {
        "dashboard.live_all",
        "dashboard.per_project",
        "dashboard.project_open",
        "dashboard.batch_projects",
        "dashboard.batch_projects.one",
    }
    assert added <= keys["en"]
    used: set[str] = set()
    for name in ("dashboard.js", "dashboard-tiles.js", "dashboard-spend.js"):
        used |= set(USED.findall(_read("js", "views", name)))
    used |= set(USED.findall(_read("js", "ui", "chart.js")))
    used |= {"dashboard.batch_projects", "dashboard.batch_projects.one"}  # chosen by a count
    assert used <= keys["en"]

"""The Batch graph's arrows and the mode switch's tooltips (`clients/web/DESIGN.md`), read from the
shipped files: one head per waiting CR, the lit arrows drawn again above the cards, a tip on each
mode word of a live batch."""

from __future__ import annotations

import re

from test_board_design import WEB


def _read(*parts: str) -> str:
    return WEB.joinpath(*parts).read_text(encoding="utf-8")


def _rule(css: str, selector: str) -> str:
    """The declarations of the rule whose selector list holds `selector`."""
    found = re.search(r"(?:^|,)\s*" + re.escape(selector) + r"\s*(?:,[^{]*)?\{([^}]*)\}", css, re.M)
    assert found, selector
    return found.group(1)


def _number(text: str, prop: str) -> int | str:
    found = re.search(prop + r":\s*([\d.]+)", text)
    assert found, prop
    return found.group(1)


def test_the_graph_draws_one_head_per_cr_and_the_lit_arrows_on_top() -> None:
    graph = _read("js", "views", "batch-graph.js")
    assert "marker-end" not in graph[graph.index("function path(") : graph.index("function head(")]
    drawn = graph[graph.index("function head(") : graph.index("let lit")]
    assert 'class="head"' in drawn and "data-to=" in drawn
    assert 'class="edges top"' in graph[graph.index("export function graphBlock") :]
    lit = graph[graph.index("export function light") : graph.index("export function relight")]
    assert "path.head" in lit and "svg.edges.top" in lit
    assert 'marker-end="url(#ar)"' in _read("js", "views", "batch-gantt.js")

    css = _read("css", "views", "batch-graph.css")
    top, lvl = _rule(css, ".batch svg.edges.top"), _rule(css, ".batch .lvl")
    assert int(_number(top, "z-index")) > int(_number(lvl, "z-index"))
    hl = _rule(css, ".batch svg.edges .head.hl")
    assert "fill: var(--accent)" in hl and "stroke: none" in hl
    assert _number(_rule(css, ".batch svg.edges .head.dim"), "opacity") == _number(
        _rule(css, ".batch svg.edges path.dim"), "opacity"
    )


def test_each_mode_word_of_a_live_batch_has_a_tip_in_both_languages() -> None:
    head = _read("js", "views", "batch-head.js")
    for needle in ('aria-describedby="mstip-', 'id="mstip-', 'role="tooltip"'):
        assert needle in head
    assert "mode.switch_to" in head and "mode.current" in head

    batch = _read("css", "views", "batch.css")
    assert not re.search(r"\.bmode \.ms span", batch)
    for state in ("hover", "focus", "focus-within"):
        assert f".bmode .ms > span:{state} .tip" in batch
    assert "right: 0" in _rule(batch, ".bmode .ms .tip")

    for lang in ("en", "fr"):
        words = _read("js", "i18n", f"{lang}.js")
        assert re.search(r"'mode\.switch_to': .*\{mode\}", words), lang
        assert "'mode.current':" in words, lang
    english = 'To switch, ask the Chief of Staff to "change the batch to {mode}"'
    assert english in _read("js", "i18n", "en.js")

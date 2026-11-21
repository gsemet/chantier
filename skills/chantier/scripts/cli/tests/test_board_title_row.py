"""The Batch page's title row (`clients/web/DESIGN.md`): the mode and the legend sit in it, built by
`batch-head.js`, scoped under `.bmode`, with their phone rules."""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest
from test_board_design import CSS, WEB, rules


def _declared(sheet: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for selector, props in rules(sheet):
        for one in selector.split(", "):
            out.setdefault(one, {}).update(props)
    return out


def _title_row() -> list[str]:
    row = re.search(
        r'<div class="titlerow">(.*?)<div class="notice"',
        (WEB / "index.html").read_text(encoding="utf-8"),
        re.S,
    )
    return [row.group(1)] if row else []


def _nav_sheet() -> list[str]:
    return [
        str(_declared((CSS / "batch-nav.css").read_text(encoding="utf-8")).get(".bmode[hidden]"))
    ]


def _head_script() -> list[str]:
    head = (WEB / "js" / "views" / "batch-head.js").read_text(encoding="utf-8")
    return [
        n
        for n in (
            'class="mpill"',
            'aria-describedby="mtip"',
            'id="mtip" role="tooltip">${words.text}',
            'class="lgpill"',
            'id="lgtip"',
            'class="ms"',
        )
        if n not in head
    ] + (["steeringFactoryWord"] if "steeringFactoryWord" in head else [])


def _batch_script() -> list[str]:
    batch = (WEB / "js" / "views" / "batch.js").read_text(encoding="utf-8")
    return [n for n in ('class="mode"', "lgrow", "legend(") if n in batch]


def _batch_sheet() -> list[str]:
    sheet = (CSS / "views" / "batch.css").read_text(encoding="utf-8")
    declared = _declared(sheet)
    bad = [
        s
        for s in declared
        if re.match(r"\.batch \.(mode|mb|ms|lg|tip)", s) or s in (".bmode .mode", ".bmode .mb")
    ]
    if declared[".bmode .tip"].get("white-space") != "normal":
        bad.append("tip white-space")
    for pill in ("mpill", "lgpill"):
        bad += [
            f"{pill}{st}"
            for st in (":hover", ":focus", ":focus-within")
            if f".bmode .{pill}{st} .tip" not in declared
        ]
        if declared[f".bmode .{pill}"].get("cursor") != "help":
            bad.append(f"{pill} cursor")
    phone = _declared(sheet[sheet.index("@media (max-width: 760px)") :])
    want = {
        ".bmode .lghint": ("display", "none"),
        ".bmode .ms": ("display", "none"),
        ".bmode": ("position", "relative"),
        ".bmode .mpill": ("position", "static"),
        ".bmode .lgpill": ("position", "static"),
        ".bmode .tip": ("max-width", "100%"),
    }
    bad += [f"phone {s}" for s, (k, v) in want.items() if phone.get(s, {}).get(k) != v]
    return bad


@pytest.mark.parametrize(
    ("check", "expected"),
    [
        (_title_row, 'id="batch-mode"'),  # the slot is in the title row
        (_nav_sheet, "display': 'none'"),  # and is hidden by its own rule
        (_head_script, None),  # batch-head.js builds both pills and the switch, no factory word
        (_batch_script, None),  # batch.js draws no band and no legend
        (_batch_sheet, None),  # batch.css scopes the slot under .bmode, with the phone block
    ],
)
def test_the_batch_mode_and_legend_sit_in_the_title_row(
    check: Callable[[], list[str]], expected: str | None
) -> None:
    found = check()
    if expected is None:
        assert found == []
    else:
        assert any(expected in part for part in found)

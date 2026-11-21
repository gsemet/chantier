"""The board's design rules (`clients/web/DESIGN.md`), checked on the sheets: the token table agrees
with `tokens.css`, no side accent border, no raw length where a token belongs. Each check is a
function from a text to a list of problems, so a prepared text can feed it (`test_checker`)."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[1] / "src" / "chantier" / "clients" / "web"
CSS = WEB / "css"
DESIGN = WEB / "DESIGN.md"
SEPARATORS = ("1px solid var(--line)", "1px solid var(--side-line)")
SIDE = re.compile(r"^border-(left|right|inline)(-|$)")
BORDER_PARTS = {"border-width", "border-style", "border-color"}
RADIUS = re.compile(r"^border(-[a-z]+)*-radius$")
KIND_OF = {  # property -> the token kinds it may take
    "font-size": {"type"},
    "font": {"type", "font"},
    "gap": {"space", "size"},
    "row-gap": {"space", "size"},
    "column-gap": {"space", "size"},
}
LITERAL = re.compile(r"(?<![\w.-])-?(\d+\.?\d*|\.\d+)(%|[a-z]+)(?![\w-])")
VAR = re.compile(r"var\(\s*(--[\w-]+)")
ROW = re.compile(r"^\|\s*`(--[\w-]+)`\s*\|\s*`(.*?)`\s*\|\s*(\w+)\s*\|")
PART = re.compile(r"^\|\s*(\w+)\s*\|\s*`(css/[^`]+)`\s*\|\s*`(js/[^`]+)`\s*\|(.*)\|\s*$")
LAYOUT = re.compile(
    r"^(grid(-.+)?|flex(-.+)?|order|align-self|justify-self|place-self|(min-|max-)?(width|height)"
    r"|overflow(-.+)?|scroll-snap-.+|margin(-.+)?)$"
)
CLASS = re.compile(r"\.([A-Za-z_][\w-]*)")
CLASS_ATTR = re.compile(r'class="([^"]*)"')
LITERAL_LIST = re.compile(r"""(?<![=\w])['"`]([\w $\{\}.-]+)['"`]""")


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _uncomment(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def rules(css: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """Every rule of a sheet, nested ones apart, as (selector, [(property, value)])."""
    out: list[tuple[str, list[tuple[str, str]]]] = []
    stack: list[tuple[str, list[tuple[str, str]]]] = []
    buf, depth = "", 0
    for ch in _uncomment(css):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if depth == 0 and ch == "{":
            stack.append((_collapse(buf), []))
            buf = ""
        elif depth == 0 and ch in ";}":
            if ":" in buf and stack:
                prop, _, value = buf.partition(":")
                stack[-1][1].append((prop.strip().lower(), _collapse(value)))
            buf = ""
            if ch == "}" and stack:
                out.append(stack.pop())
        else:
            buf += ch
    return out


def tokens(css: str) -> dict[str, str]:
    """The custom properties of a sheet's `:root`, values collapsed."""
    return {p: v for sel, ds in rules(css) if sel == ":root" for p, v in ds if p.startswith("--")}


def table(markdown: str) -> dict[str, tuple[str, str]]:
    """DESIGN.md's token table: name -> (value, kind)."""
    rows = (ROW.match(line) for line in markdown.splitlines())
    return {m[1]: (_collapse(m[2]), m[3]) for m in rows if m}


def check_table(design: str, root: str) -> list[str]:
    have, want = table(design), tokens(root)
    out = [f"token {n} is not in DESIGN.md's table" for n in want if n not in have]
    out += [f"DESIGN.md's table names {n}, not in tokens.css" for n in have if n not in want]
    out += [
        f"token {n}: tokens.css holds {want[n]!r}, DESIGN.md {have[n][0]!r}"
        for n in want
        if n in have and want[n] != have[n][0]
    ]
    return out


def check_side(css: str) -> list[str]:
    """(a) A side border is `0`, `none` or a plain separator; border parts take one value."""
    out = []
    for sel, decls in rules(css):
        radius = any(RADIUS.match(p) for p, _ in decls)
        for prop, value in decls:
            if SIDE.match(prop) and value not in ("0", "none", *SEPARATORS):
                out.append(f"{sel}: {prop}: {value} is a side accent border")
            elif SIDE.match(prop) and value not in {"0", "none"} and radius:
                out.append(f"{sel}: a separator {prop} on an element with a radius")
            elif prop in BORDER_PARTS and len(value.split()) > 1:
                out.append(f"{sel}: {prop}: {value} sets sides apart")
    return out


def _kinds(prop: str) -> set[str] | None:
    if prop in KIND_OF:
        return KIND_OF[prop]
    if RADIUS.match(prop):
        return {"radius"}
    if re.match(r"^(margin|padding)(-|$)", prop):
        return {"space", "size"}
    return None


def check_raw(css: str, kinds: dict[str, str]) -> list[str]:
    """(b) No literal length in spacing, radius and type properties; tokens of the right kind."""
    out = []
    for sel, decls in rules(css):
        for prop, value in decls:
            want = _kinds(prop)
            if want is None:
                continue
            if LITERAL.search(VAR.sub("", value)):
                out.append(f"{sel}: {prop}: {value} holds a raw length")
            out += [
                f"{sel}: {prop}: {name} is not a {'/'.join(sorted(want))} token"
                for name in VAR.findall(value)
                if kinds.get(name) not in want
            ]
    return out


def components(markdown: str) -> dict[str, tuple[str, list[str]]]:
    """DESIGN.md's component table: name -> (sheet, classes), a trailing `-*` a prefix."""
    rows = (PART.match(line) for line in markdown.splitlines())
    return {m[1]: (m[2], re.findall(r"`([^`]+)`", m[4])) for m in rows if m}


def _owner(name: str, parts: dict[str, tuple[str, list[str]]]) -> str | None:
    """The sheet that owns a class of the component table, or None."""
    for sheet, classes in parts.values():
        for c in classes:
            if name == c or (c.endswith("-*") and name.startswith(c[:-1])):
                return sheet
    return None


def check_components(css: str, sheet: str, parts: dict[str, tuple[str, list[str]]]) -> list[str]:
    """(c) A component's class is styled in its own sheet, or only placed and sized in a page's."""
    out = []
    for sel, decls in rules(css):
        for name in CLASS.findall(sel):
            home = _owner(name, parts)
            layout = all(LAYOUT.match(p) or p.startswith("--") for p, _ in decls)
            if home and home != sheet and not layout:
                out.append(f"{sel}: styles .{name}, which belongs to {home}")
    return out


def _is_card(token: str) -> bool:
    return token == "card" or token.startswith("card-")


def check_card(js: str) -> list[str]:
    """The class `card` or a `card-*` class is written by `ui/card.js` only."""
    lists = CLASS_ATTR.findall(js)
    lists += LITERAL_LIST.findall(CLASS_ATTR.sub("", js))
    return [f"class list {v!r} writes a card class" for v in lists if any(map(_is_card, v.split()))]


def _sheets() -> list[Path]:
    return [p for p in sorted(CSS.rglob("*.css")) if p.name != "tokens.css"]


def _kinds_of_design() -> dict[str, str]:
    return {n: k for n, (_, k) in table(DESIGN.read_text(encoding="utf-8")).items()}


def test_token_table() -> None:
    root = (CSS / "tokens.css").read_text(encoding="utf-8")
    assert not check_table(DESIGN.read_text(encoding="utf-8"), root)


def test_sheets() -> None:
    kinds = _kinds_of_design()
    out = []
    for path in _sheets():
        css = path.read_text(encoding="utf-8")
        name = path.relative_to(CSS).as_posix()
        out += [f"{name}: {p}" for p in check_side(css) + check_raw(css, kinds)]
    assert not out, "\n".join(out)


def test_components() -> None:
    """(c) on every real sheet: a component's class styled only in its own sheet."""
    parts = components(DESIGN.read_text(encoding="utf-8"))
    assert parts, "DESIGN.md's component table is empty"
    out = [f"DESIGN.md names {s}, not a file" for s, _ in parts.values() if not (WEB / s).is_file()]
    for path in _sheets():
        sheet = path.relative_to(WEB).as_posix()
        out += [f"{sheet}: {p}" for p in check_components(path.read_text("utf-8"), sheet, parts)]
    assert not out, "\n".join(out)


def test_one_card() -> None:
    """Every real script but `ui/card.js` and the words leaves the card's classes to it."""
    js = WEB / "js"
    out = []
    for path in sorted(js.rglob("*.js")):
        name = path.relative_to(js).as_posix()
        if name == "ui/card.js" or name.startswith("i18n/"):
            continue
        out += [f"js/{name}: {p}" for p in check_card(path.read_text("utf-8"))]
    assert not out, "\n".join(out)


Check = Callable[..., list[str]]
KINDS = {"--space-2": "space", "--radius": "radius", "--text": "type"}
REFUSED = [
    (check_side, ".a { border-left: 3px solid var(--accent) }"),
    (check_side, ".a { border-left: 1px solid var(--line); border-radius: var(--radius) }"),
    (check_side, ".a { border-width: 0 1px }"),
    (check_raw, ".a { padding: 10px }"),
    (check_raw, ".a { font-size: var(--local) }"),
    (check_raw, ".a { border-radius: var(--space-2) }"),
    (check_raw, ".a { gap: 99%; margin: 0 auto 1.5em }"),
    (check_components, ".card { color: var(--ink) }"),
    (check_components, ".kanban .card-top { padding: 0 }"),
    (check_card, '<div class="card pi">'),
    (check_card, "const c = `prc card ${cls}`;"),
    (check_card, "el.className = 'card-meta'"),
]
PARTS = {"card": ("css/components/card.css", ["card", "card-*"])}
ALLOWED = [
    (check_side, ".a { border-top: 1px solid var(--line) }"),
    (check_side, ".side { border-right: 1px solid var(--side-line) }"),
    (check_side, ".a { border-left: 0; border-right: none }"),
    (check_raw, ".a { margin: calc(-1 * var(--space-2)) 0; padding: 0 auto }"),
    (check_raw, ".a { font: inherit; border-radius: var(--radius) 0; gap: var(--space-2) }"),
    (check_raw, ".a { --w: 12px; font-size: var(--text); /* 9px */ }"),
    (check_components, ".kanban .card { flex: 0 0 290px; max-height: 100%; margin: 0 }"),
    (check_components, ".tri > .card { --w: 280px; flex: 1 1 var(--w) }"),
    (check_card, '<div data-key="card-3" class="column">'),
]


def _run(check: Check, text: str) -> list[str]:
    if check is check_raw:
        return check(text, KINDS)
    if check is check_components:
        return check(text, "css/views/page.css", PARTS)
    return check(text)


@pytest.mark.parametrize(("check", "text"), REFUSED)
def test_checker_refuses(check: Check, text: str) -> None:
    assert _run(check, text)


@pytest.mark.parametrize(("check", "text"), ALLOWED)
def test_checker_allows(check: Check, text: str) -> None:
    assert not _run(check, text)


def test_checker_table() -> None:
    assert check_table("| `--a` | `1px` | space | x |", ":root { --a: 1px; --b: 2px }") == [
        "token --b is not in DESIGN.md's table"
    ]


def test_a_card_title_is_one_line_with_its_full_text_on_hover() -> None:
    sheet = (CSS / "components" / "card.css").read_text(encoding="utf-8")
    declared = dict(next(d for s, d in rules(sheet) if s == ".card-title"))
    assert declared["white-space"] == "nowrap" and declared["text-overflow"] == "ellipsis"
    assert not any("line-clamp" in p for s, d in rules(sheet) if "card-title" in s for p, _ in d)
    script = (WEB / "js" / "ui" / "card.js").read_text(encoding="utf-8")
    assert 'class="card-title" title="' in script


BATCH_KEYS = (
    "tab_kanban",
    "kanban_pending",
    "kanban_actives",
    "kanban_done",
    "kanban_pending_sub",
    "kanban_actives_sub",
    "kanban_done_sub",
    "kanban_closed",
)
NO_WRITE = ("draggable", "dragstart", "'drop'", '"drop"', "ondrop", "drop:", "data-col", "call(")


def _web(*parts: str) -> str:
    return (WEB.joinpath(*parts)).read_text(encoding="utf-8")


def _check_tabs() -> bool:
    return re.search(r"TABS = \[\s*'kanban'", _web("js", "core", "router.js")) is not None


def _check_words() -> bool:
    texts = (_web("js", "i18n", f"{lang}-batch.js") for lang in ("en", "fr"))
    return all(f"'batch.{key}'" in text for text in texts for key in BATCH_KEYS)


def _check_closed_note() -> bool:
    return "batch.kanban_closed" in _web("js", "views", "batch.js")


def _check_shell() -> bool:
    sheet = _web("css", "shell.css")
    return ".main:has(.view > .kanban)" in sheet and ".main:has(.kanban)" not in sheet


def _check_parts() -> bool:
    text = _web("js", "views", "batch-kanban.js")
    return bool(
        re.search(r"import \{[^}]*\bcolumn\b[^}]*\} from '\.\./ui/column\.js'", text)
        and re.search(r"import \{[^}]*\bcrCard\b[^}]*\} from '\./kanban-cards\.js'", text)
    )


def _check_read_only() -> bool:
    return not any(word in _web("js", "views", "batch-kanban.js") for word in NO_WRITE)


def _check_stage() -> bool:
    text = _web("js", "views", "batch-kanban.js")
    return ".stage" in text and ".folder" not in text


@pytest.mark.parametrize(
    "check",
    [
        _check_tabs,
        _check_words,
        _check_closed_note,
        _check_shell,
        _check_parts,
        _check_read_only,
        _check_stage,
    ],
)
def test_the_batch_kanban_as_shipped(check: Callable[[], bool]) -> None:
    assert check()


def test_a_batch_view_draws_the_batch_folder_chip_not_a_priority() -> None:
    js = WEB / "js"
    assert not [f.name for f in js.rglob("*.js") if "c.priority" in f.read_text(encoding="utf-8")]
    for view in ("graph", "gantt", "timecards", "pr-card"):
        text = (js / "views" / f"batch-{view}.js").read_text(encoding="utf-8")
        assert "priority: c.stage" in text, view
    chip = (CSS / "components" / "chip.css").read_text(encoding="utf-8")
    assert not re.search(r"\.tag\.pri-(1-pending|2-actives|3-done)", chip)


def test_the_dashboard_sits_between_costs_and_configuration_and_its_chart_is_linked() -> None:
    """The Dashboard entry: after Costs, before Configuration, no overview, no count; its chart
    sheet is linked right after the column's."""
    registry = _web("js", "views", "registry.js")
    ids = re.findall(r"^\s*(?:\{\s*)?id: '(\w+)'", registry, re.M)
    at = ids.index("dashboard")
    assert (ids[at - 1], ids[at + 1]) == ("costs", "config")
    entry = re.search(r"\{[^{}]*id: 'dashboard'[^{}]*\}", registry)
    assert entry and "overview" not in entry[0] and "count" not in entry[0]
    links = re.findall(r'<link rel="stylesheet" href="(css/[^"]+)"', _web("index.html"))
    assert links[links.index("css/components/column.css") + 1] == "css/components/chart.css"
    assert links[links.index("css/views/costs-stamp.css") + 1] == "css/views/dashboard.css"


@pytest.mark.parametrize("lang", ["en", "fr"])
def test_the_fold_and_the_writes_count_explanation_ship(lang: str) -> None:
    words = (WEB / "js" / "i18n" / f"{lang}-write.js").read_text(encoding="utf-8")
    for key in ("triage.fold", "triage.unfold", "journal.what", "journal.why", "journal.todo"):
        assert f"'{key}':" in words
    assert "'journal.tip':" in words
    assert not any(
        "journal.note" in p.read_text(encoding="utf-8") for p in (WEB / "js").rglob("*.js")
    )
    column = (WEB / "js" / "ui" / "column.js").read_text(encoding="utf-8")
    assert all(w in column for w in ("data-fold", "aria-expanded", "column-folded"))
    journal = (WEB / "js" / "journal" / "journal.js").read_text(encoding="utf-8")
    panel = journal[journal.index("export function journalPanel") :]
    assert panel.index("journal.what") < panel.index("<ul")
    assert re.search(r'title="\$\{t\(.journal\.tip.\)\}"', journal)
    design = DESIGN.read_text(encoding="utf-8")
    assert "## Triage: folded rows and the writes count" in design

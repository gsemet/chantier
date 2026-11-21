"""The board's Help page (`views/help.js`, `help-topics.js`): a view of the registry, every topic
in both languages within its word cap, and its links to real pages."""

from __future__ import annotations

import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "src" / "chantier" / "clients" / "web"

CONCEPTS = [
    *("change_request", "grill", "planning_folder", "batch", "cr_lifecycle", "planning_modes"),
    *("steering", "batch_modes", "project_rules", "gates", "costs", "boards"),
]
ROLES = [
    *("chief_of_staff", "griller", "foreman", "driver", "spec_writer", "investigator", "coder"),
    *("inspector", "verifier", "debugger", "conflict_resolver", "stack_driver", "release_driver"),
]
STRING = r"'((?:[^'\\]|\\.)*)'|" r'"((?:[^"\\]|\\.)*)"'
REPO = "https://github.com/gsemet/chantier"


def _slug(heading: str) -> str:
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def _anchor_exists(page: Path, anchor: str) -> bool:
    heads = re.findall(r"^#{1,6}\s+(.*?)\s*$", page.read_text(encoding="utf-8"), flags=re.M)
    return anchor in {_slug(h) for h in heads}


TOPIC = re.compile(r"id: '(\w+)',\s*group: '(\w+)',\s*doc: (null|'[^']*')")


def _read(*parts: str) -> str:
    return Path(WEB, "js", *parts).read_text(encoding="utf-8")


def _help_words(rows: list[tuple[str, str, str]]) -> list[str]:
    problems = []
    for lang, cap in (("en", 150), ("fr", 175)):
        text = _read("i18n", f"{lang}-help.js")
        for i, _, _ in rows:
            problems += [
                f"{lang} {i}.{part}"
                for part in ("name", "line", "body")
                if f"'help.{i}.{part}':" not in text
            ]
            m = re.search(rf"'help\.{i}\.body': {STRING}", text)
            if not m or len((m.group(1) or m.group(2)).split()) > cap:
                problems.append(f"{lang} {i}.body is missing or over {cap} words")
    return problems


def _help_links(rows: list[tuple[str, str, str]]) -> list[str]:
    root = Path(__file__).resolve().parents[5]
    problems = []
    for _, _, doc in rows:
        url = doc.strip("'")
        if doc == "null":
            continue
        base, _, anchor = url.partition("#")
        docs = f"{REPO}/blob/main/"
        page = root / (base.removeprefix(docs) if base.startswith(docs) else "README.md")
        if not url.startswith(REPO) or not page.is_file():
            problems.append(f"{url}: no such page")
        elif anchor and not _anchor_exists(page, anchor):
            problems.append(f"{url}: no such heading")
    return problems


def test_the_help_page_is_a_view_with_both_languages_and_real_links() -> None:
    registry = _read("views", "registry.js")
    order = re.findall(r"id: '(\w+)'", registry)
    after = "inbox" if "inbox" in order else "home"
    assert order[order.index(after) + 1] == "help"
    entry = registry[registry.index("id: 'help'") :].split("}")[0]
    assert "overview" in entry and "count" not in entry

    rows = TOPIC.findall(_read("views", "help-topics.js"))
    ids = [r[0] for r in rows]
    assert all(re.fullmatch(r"[a-z_]+", i) for i in ids)
    assert ids == CONCEPTS + ROLES
    assert [r[1] for r in rows] == ["concepts"] * len(CONCEPTS) + ["roles"] * len(ROLES)
    assert ids.index("investigator") + 1 == ids.index("coder")
    assert ids.index("verifier") + 1 == ids.index("debugger")
    assert _help_words(rows) == []
    assert _help_links(rows) == []

    view, router = _read("views", "help.js"), _read("core", "router.js")
    assert "attrs: '" not in view and 'attrs: "' not in view
    assert "topic: null" not in view and "closeTopic" in view
    assert "export function closeTopic" in router and "history.back()" in router
    assert "replaceState(history.state" in router
    for name in ("help.js", "help-topics.js"):
        assert not re.search(r"core/(transport|api)\.js|/api/", _read("views", name)), name

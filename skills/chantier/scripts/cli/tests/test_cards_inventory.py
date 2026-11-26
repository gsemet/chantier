# The review of the old cards against the new (CR-511): every rule of the base has a home that
# resolves at head, and a check. The inventory is `docs/proofs/cards-inventory.md`
# (`cards_inventory.py` reads it). A row with no home yet is `open:` and is listed in
# `docs/proofs/cards-inventory-open.tsv`, no other row.

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable

import pytest
from cards_inventory import (
    OPENED,
    Inventory,
    Row,
    cells,
    check_resolves,
    home_resolves,
    inventory,
    kind_a_homed,
    known_open,
    open_lines,
    topics,
)

RARE = "none (rare)"
HEADINGS = ["Base", "Sources", "Rows", "No-rule lines"]
HEADINGS += ["For the owner", "Hand-over checklist"]
REASONS = {"heading", "blank", "example", "table-header"}
REASONS |= {"code", "link", "transition", "front-matter"}
ITEMS = "P1 P2 P3 P4 P5 P6 sc03 sc06 sc07 sc08"
ITEMS += " sc09-Q2 sc13 sc15 sc19-S sc20-U"
ITEMS += " sc20-Q2 sc20-L sc21-B1b sc21-B1e"
ITEMS += " sc21-B6 sc21-Q1 sc21-C sc22-B sc22-J"
ITEMS += " sc22-C sc22-S sc22-D sc23-1 sc24-1"
ID = re.compile(r"[A-Z]{1,2}-B?\d{3,4}")
OPEN_COLUMNS = ["id", "kind", "reason"]


def schema_problems(inv: Inventory) -> list[str]:
    ids = [r.id for r in inv.rows]
    found = [f"twice: {i}" for i, n in Counter(ids).items() if n > 1]
    found += [f"id: {i}" for i in ids if not ID.fullmatch(i)]
    found += [f"kind: {r.id}" for r in inv.rows if r.kind not in set("abcdef")]
    found += [f"empty: {r.id}" for r in inv.rows if not all(r)]
    found += [f"reason: {s}" for s, why in inv.no_rule if why not in REASONS]
    return found


def home_problems(inv: Inventory) -> list[str]:
    return [r.id for r in inv.rows if not home_resolves(r)]


def kind_a_problems(inv: Inventory) -> list[str]:
    rows = [r for r in inv.rows if r.kind == "a" and not known_open(r)]
    return [r.id for r in rows if not kind_a_homed(r.home)]


def open_problems(inv: Inventory) -> list[str]:
    held = {(r.id, r.kind) for r in inv.rows if r.home.startswith(OPENED)}
    lines = open_lines()[1:]
    good = [x for x in lines if len(x) == len(OPEN_COLUMNS) and x[-1].strip()]
    named = {(x[0], x[1]) for x in good}
    found = [f"bad line: {x[0]}" for x in lines if x not in good]
    found += [f"twice: {i}" for i, n in Counter(x[0] for x in good).items() if n > 1]
    found += [f"unlisted: {i}" for i, _ in sorted(held - named)]
    return found + [f"not open: {i}" for i, _ in sorted(named - held)]


def header_problems(inv: Inventory) -> list[str]:
    wanted = {"Sources": "path lines lf_bytes blob", "Rows": " ".join(Row._fields)}
    wanted["No-rule lines"] = "source reason"
    found = []
    for name, columns in wanted.items():
        lines = [x for x in inv.sections.get(name, []) if x.startswith("|")]
        if not lines or cells(lines[0]) != columns.split():
            found.append(f"header: {name}")
    return found


def rare_homed(home: str) -> bool:
    if home.startswith("incidents"):
        return True
    topic = topics().get(home.removeprefix("topic "))
    return home.startswith("topic ") and bool(topic and topic.review_by)


def check_problems(inv: Inventory) -> list[str]:
    return [r.id for r in inv.rows if not check_resolves(r)]


def covered(inv: Inventory) -> tuple[dict[str, set[int]], list[str]]:
    lines: dict[str, set[int]] = {path: set() for path in inv.sources}
    wrong: list[str] = []
    for source in [r.source for r in inv.rows] + [s for s, _ in inv.no_rule]:
        found = re.fullmatch(r"(.+):(\d+)(?:-(\d+))?", source)
        path, first = (found[1], int(found[2])) if found else ("", 0)
        last = int(found[3] or first) if found else 0
        if path not in lines or not 1 <= first <= last <= inv.sources[path]:
            wrong.append(f"range: {source}")
        else:
            lines[path] |= set(range(first, last + 1))
    return lines, wrong


def coverage_problems(inv: Inventory) -> list[str]:
    lines, found = covered(inv)
    for path, count in inv.sources.items():
        missed = sorted(set(range(1, count + 1)) - lines[path])
        found += [f"uncovered: {path}:{n}" for n in missed]
    return found


def report(found: list[str]) -> str:
    return f"{len(found)} problems, first ones: {found[:20]}"


def test_schema() -> None:
    inv = inventory()
    assert list(inv.sections) == HEADINGS
    base = [x for x in inv.sections["Base"] if x.startswith("base: ")]
    assert len(base) == 1 and re.fullmatch(r"base: [0-9a-f]{40}", base[0])
    assert inv.rows and inv.sources
    found = header_problems(inv) + schema_problems(inv)
    assert not found, report(found)


def test_open_list() -> None:
    assert open_lines()[0] == OPEN_COLUMNS
    found = open_problems(inventory())
    assert not found, report(found)


def test_homes_resolve() -> None:
    found = home_problems(inventory())
    assert not found, report(found)


def test_kind_a_homes() -> None:
    found = kind_a_problems(inventory())
    assert not found, report(found)


def test_rare_rules() -> None:
    rows = [r for r in inventory().rows if r.trigger == RARE]
    found = [r.id for r in rows if not (known_open(r) or rare_homed(r.home))]
    assert not found, report(found)


def test_checks_resolve() -> None:
    found = check_problems(inventory())
    assert not found, report(found)


def test_coverage() -> None:
    found = coverage_problems(inventory())
    assert not found, report(found)


def owner_lists(lines: list[str]) -> list[list[str]]:
    found: list[list[str]] = []
    for line in lines:
        if line.startswith("### "):
            found.append([])
        elif line.startswith("- "):
            found[-1].append(line)
    return found


def listed(rows: list[Row], keep: Callable[[Row], bool]) -> list[str]:
    return [f"- `{r.id}`: {r.home}; check: {r.check}" for r in rows if keep(r)]


def test_owner_lists() -> None:
    inv = inventory()
    wanted: list[Callable[[Row], bool]] = [
        lambda r: r.kind == "a",
        lambda r: r.home.startswith(("inferable", "incidents")),
        lambda r: r.home.startswith("removed: "),
        lambda r: r.kind == "a" and r.check == "quote",
    ]
    lists = owner_lists(inv.sections["For the owner"])
    assert len(lists) == len(wanted)
    for got, keep in zip(lists, wanted, strict=True):
        assert sorted(got) == sorted(listed(inv.rows, keep))


def test_checklist_closed() -> None:
    lines = [x for x in inventory().sections["Hand-over checklist"] if x]
    closed = re.compile(r"- (\S+): .*(done|known gap): \S.*")
    found = [x for x in lines if not closed.fullmatch(x)]
    assert not found, report(found)
    ids = {x.split()[1].rstrip(":") for x in lines}
    assert not set(ITEMS.split()) - ids


def made(*rows: tuple[str, str, str]) -> Inventory:
    # each row: its id, its home, its check; kind a, all on line 1 of a two-line source
    full = [Row(i, "r", "t", "b", "p:1", "a", home, check) for i, home, check in rows]
    return Inventory({}, full, {"p": 2}, [])


def homed(home: str) -> Inventory:
    return made(("X-900", home, "quote"))


def checked(check: str) -> Inventory:
    return made(("X-900", "floor 1", check))


GOOD = ("X-900", "floor 1", "quote")
REFUSALS = {
    "duplicate": (schema_problems, made(GOOD, GOOD)),
    "a-topic": (kind_a_problems, homed("topic lease")),
    "a-inferable": (kind_a_problems, homed("inferable")),
    "a-dot-topic": (kind_a_problems, homed('card ./topics/ci.md: "x"')),
    "a-data": (kind_a_problems, homed('card topics.json: "x"')),
    "a-shared": (kind_a_problems, homed('card concepts.md: "x"')),
    "a-unlisted": (kind_a_problems, homed("open: x")),
    "unlisted": (open_problems, homed("open: x")),
    "open-home": (home_problems, homed("open: x")),
    "no-topic": (home_problems, homed("topic no-such")),
    "no-floor": (home_problems, homed("floor .")),
    "no-answer": (home_problems, homed("removed: answer 999 - x")),
    "no-target": (home_problems, homed('refusal: "refused"')),
    "outside": (home_problems, homed("proof file docs/proofs/../../README.md")),
    "no-test": (check_problems, checked("test a.py::b")),
    "no-row": (check_problems, checked("quiz coder/floor-5-coder-failing-round")),
    "no-header": (header_problems, made(GOOD)),
    "uncovered": (coverage_problems, made(GOOD)),
}


@pytest.mark.parametrize("case", REFUSALS)
def test_refusals(case: str) -> None:
    problems, bad = REFUSALS[case]
    assert problems(bad)

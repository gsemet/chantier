# The inventory of the old cards' rules (CR-511), `docs/proofs/cards-inventory.md`: its tables, and
# what makes a row's home and a row's check resolve at head. `test_cards_inventory.py` holds it.

from __future__ import annotations

import ast
import json
import re
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import NamedTuple

from conftest import PLUGIN_ROOT, SKILL

from chantier.commands.help import Topic, load_topics
from chantier.host_rows import load_rows
from chantier.roles_data import load_roles

REFS = SKILL / "references"
TESTS = Path(__file__).resolve().parent
SRC = TESTS.parent / "src"
PROOFS = PLUGIN_ROOT / "docs/proofs"
INVENTORY = PROOFS / "cards-inventory.md"
OPEN = PROOFS / "cards-inventory-open.tsv"
OPENED = "open: "
SPAN_MAX = 40
TARGETED = ("card", "refusal", "next", "--help")
FORMS = "|".join((*TARGETED, "facts", "incidents"))
SPANNED = re.compile(f'({FORMS})(.*?): "(.*)"')
# a program answer (there are less than 30), or a child's question or item
ANSWER = r"answer [12]?\d"
CHILD = r"sc\d\d(-Q\d+| B\w+)"
REMOVED = re.compile(rf"removed: ({ANSWER}|{CHILD}) - \S.*")


class Row(NamedTuple):
    id: str
    role: str
    trigger: str
    behaviour: str
    source: str
    kind: str
    home: str
    check: str


class Inventory(NamedTuple):
    sections: dict[str, list[str]]
    rows: list[Row]
    sources: dict[str, int]
    no_rule: list[tuple[str, str]]


def cells(line: str) -> list[str]:
    parts = re.split(r"(?<!\\)\|", line.strip()[1:-1])
    return [p.strip().replace("\\|", "|") for p in parts]


def table(lines: list[str]) -> list[list[str]]:
    # the first two lines of a table are its header and its rule
    return [cells(x) for x in lines if x.startswith("|")][2:]


@cache
def inventory() -> Inventory:
    sections: dict[str, list[str]] = {}
    current: list[str] = []
    for line in INVENTORY.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = sections.setdefault(line[3:], [])
        else:
            current.append(line)
    rows = [Row(*c) for c in table(sections.get("Rows", []))]
    sources = {c[0]: int(c[1]) for c in table(sections.get("Sources", []))}
    no_rule = [(c[0], c[1]) for c in table(sections.get("No-rule lines", []))]
    return Inventory(sections, rows, sources, no_rule)


def flat(text: str) -> str:
    return " ".join(text.split())


@cache
def read_flat(path: Path) -> str:
    return flat(path.read_text(encoding="utf-8"))


@cache
def code(register: bool) -> tuple[str, ...]:
    paths = sorted(SRC.rglob("*.py"))
    if register:
        paths.append(PLUGIN_ROOT / "hooks/register.tsx")
    return tuple(read_flat(p) for p in paths)


def case_rules(case: Path) -> list[str]:
    rules: list[str] = json.loads(case.read_text("utf-8")).get("rules", [])
    return rules


@cache
def quizzed() -> frozenset[str]:
    cases = (PLUGIN_ROOT / "evals/quiz").rglob("*.json")
    return frozenset(i for case in cases for i in case_rules(case))


@cache
def open_lines() -> list[list[str]]:
    return [x.split("\t") for x in OPEN.read_text("utf-8").splitlines()]


@cache
def listed_open() -> frozenset[str]:
    return frozenset(x[0] for x in open_lines()[1:])


def known_open(row: Row) -> bool:
    return row.home.startswith(OPENED) and row.id in listed_open()


@cache
def topics() -> dict[str, Topic]:
    return load_topics()


@cache
def host_ids() -> frozenset[str]:
    return frozenset(r.capability for h in ("claude", "copilot") for r in load_rows(h))


def card_resolves(target: str, span: str) -> bool:
    path = (REFS / target).resolve()
    inside = path.is_relative_to(PLUGIN_ROOT / "skills")
    return inside and path.is_file() and span in read_flat(path)


@cache
def spanned_resolves(home: str) -> bool:
    found = SPANNED.fullmatch(home)
    if not found:
        return False
    form, target, span = found[1], found[2].strip(), found[3]
    if len(span) > SPAN_MAX or not span.strip() or re.search(r'[|"]', span):
        return False
    if form in TARGETED and not target:
        return False
    if form == "card":
        return card_resolves(target, flat(span))
    if form == "incidents":
        return flat(span) in read_flat(PLUGIN_ROOT / "docs/incidents.md")
    return any(flat(span) in text for text in code(form == "refusal"))


def floor_resolves(number: str) -> bool:
    text = read_flat(REFS / "floor.md")
    return number.isdigit() and f" {number}. " in text


@cache
def proof_resolves(path: str) -> bool:
    full = (PLUGIN_ROOT / path).resolve()
    inside = full.is_relative_to(PROOFS.resolve())
    return path.startswith("docs/proofs/") and inside and full.is_file()


NAMED: dict[str, Callable[[str], bool]] = {
    "floor ": floor_resolves,
    "topic ": lambda name: name in topics(),
    "host row ": lambda name: name in host_ids(),
    "proof file ": proof_resolves,
}


def home_resolves(row: Row) -> bool:
    if row.home.startswith(OPENED):
        return known_open(row)
    if row.home == "inferable":
        return row.id in quizzed()
    if row.home.startswith("removed: "):
        return REMOVED.fullmatch(row.home) is not None
    for prefix, resolves in NAMED.items():
        if row.home.startswith(prefix):
            return resolves(row.home.removeprefix(prefix))
    return spanned_resolves(row.home)


@cache
def role_cards() -> frozenset[Path]:
    return frozenset((REFS / r.card).resolve() for r in load_roles())


def kind_a_homed(home: str) -> bool:
    # the floor, a role's card (`card:` of roles.yaml) or a refusal: nothing else is read
    # by the session that the rule binds
    if home.startswith("floor "):
        return True
    found = SPANNED.fullmatch(home)
    if not found or found[1] == "refusal":
        return bool(found)
    target = (REFS / found[2].strip()).resolve()
    return found[1] == "card" and target in role_cards()


@cache
def functions(path: Path) -> frozenset[str]:
    tree = ast.parse(path.read_text("utf-8"))
    return frozenset(n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))


@cache
def units() -> frozenset[str]:
    runner = PLUGIN_ROOT / "scenario/run_scenario.py"
    for node in ast.walk(ast.parse(runner.read_text("utf-8"))):
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        target = node.targets[0] if isinstance(node, ast.Assign) else node.target
        if getattr(target, "id", "") == "UNITS" and isinstance(node.value, ast.Dict):
            keys = node.value.keys
            return frozenset(str(k.value) for k in keys if isinstance(k, ast.Constant))
    return frozenset()


def named_test(name: str) -> bool:
    file, _, function = name.partition("::")
    path = TESTS / file
    return path.is_file() and function in functions(path)


def rail_named(name: str) -> bool:
    card = (PLUGIN_ROOT / "evals/SCORECARD.md").read_text("utf-8")
    return name in re.findall(r"^\| (J\d+) \|", card, re.M)


def quiz_named(name: str, rid: str) -> bool:
    case = PLUGIN_ROOT / f"evals/quiz/{name}.json"
    return case.is_file() and rid in case_rules(case)


# each takes the name the check cites and the row's id
CHECKS: dict[str, Callable[[str, str], bool]] = {
    "test ": lambda name, _: named_test(name),
    "scenario ": lambda name, _: name in units(),
    "rail ": lambda name, _: rail_named(name),
    "quiz ": quiz_named,
}


def check_resolves(row: Row) -> bool:
    if row.check == "quote":
        return home_resolves(row)
    for prefix, resolves in CHECKS.items():
        if row.check.startswith(prefix):
            return resolves(row.check.removeprefix(prefix), row.id)
    return False

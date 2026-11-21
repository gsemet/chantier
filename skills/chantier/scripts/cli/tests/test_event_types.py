"""The journal's published types (`name@N`): the shipped schemas against the models, the recipe's
merge, the formats the models fix, the writer's refusals and duplicate rule per type, and the
reading of lines no writer produces any more or yet (versions 0 and 1, an unknown type, a refused
payload). The prepared cases are named as such: the shipped file and the writers cannot make them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import changes, open_batch
from conftest import Chantier

from chantier.core.repo import Repo
from chantier.hub import journal, schemas
from chantier.hub.watch import once

SHIPPED = Path(__file__).resolve().parents[1] / "src" / "chantier" / "hub" / "schemas.json"
HEAD = ["v", "seq", "t", "type", "source", "audience"]
MERGED = schemas.PUBLISHED["merged@1"].example
RED = schemas.PUBLISHED["checks-red@1"].example
UNKNOWN, REFUSED, BOARDS, TOLD = 6, 7, 2, 3  # in the prepared journal
SLOTS = {"type": "config@1", "key": "batch.slots", "old": 3, "new": 4, "batch": "b"}


def shipped() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(SHIPPED.read_text("utf-8"))
    return data


def test_the_shipped_schemas_are_the_published_models_in_canonical_form() -> None:
    entries = shipped()
    for name, entry in schemas.PUBLISHED.items():
        assert name in entries, (
            f"schema {name} not published in schemas.json: run just journal-schemas"
        )
        same = schemas.normalize(entries[name]) == schemas.normalize(
            entry.model.model_json_schema()
        )
        assert same, f"published schema {name} changed: publish {name}+1 instead"
    for name in entries:
        assert name in schemas.PUBLISHED, (
            f"published schema {name} changed: publish {name}+1 instead"
        )
    raw = SHIPPED.read_bytes()
    assert raw.decode("utf-8") == schemas.canonical(entries)
    assert not raw.startswith(b"\xef\xbb\xbf") and b"\r" not in raw and raw.endswith(b"}\n")


def _schema(**more: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "title": "T",
        "properties": {
            "a": {"title": "A", "type": "string"},
            "b": {"anyOf": [{"type": "string", "pattern": "^x$"}, {"type": "null"}]},
        },
        "required": ["a"],
    }
    return {**base, **more}


def _changed() -> list[dict[str, Any]]:
    props = _schema()["properties"]
    return [
        _schema(properties={**props, "a": {"type": "integer"}}),
        _schema(properties={**props, "c": {"type": "string"}}),
        _schema(properties={"a": props["a"]}),
        _schema(required=["a", "b"]),
        _schema(properties={**props, "b": {"anyOf": [{"type": "string", "pattern": "^y$"}]}}),
    ]


def test_the_normalized_form_ignores_the_generator_and_sees_every_published_change() -> None:
    # prepared schemas: what only a generator's rewording or a real change can produce
    props = _schema()["properties"]
    reworded = _schema(
        title="Other",
        description="d",
        properties={
            "b": {"description": "x", "anyOf": [{"type": "null"}, props["b"]["anyOf"][0]]},
            "a": {"type": "string", "title": "Z"},
        },
    )
    assert schemas.normalize(reworded) == schemas.normalize(_schema())
    for changed in _changed():
        assert schemas.normalize(changed) != schemas.normalize(_schema())


def test_the_recipe_adds_a_missing_entry_keeps_a_differing_one_and_changes_nothing_else() -> None:
    # a prepared file: one published entry missing, one existing entry that differs from its model
    entries = shipped()
    kept = {"properties": {}, "required": [], "note": "never rewritten"}
    prepared = {k: v for k, v in entries.items() if k != "board@1"}
    prepared["config@1"] = kept
    merged, said = schemas.merge(prepared)
    assert said == [
        "schemas.json: config@1 differs from its model: publish config@2 instead",
        "schemas.json: added board@1",
    ]
    assert merged["config@1"] is kept
    assert json.dumps(merged["merged@1"]) == json.dumps(entries["merged@1"])
    assert merged["board@1"] == schemas.PUBLISHED["board@1"].model.model_json_schema()
    assert schemas.canonical(merged).endswith("}\n")
    again, nothing = schemas.merge(entries)  # the shipped file: nothing added, nothing changed
    assert nothing == [] and again == entries


@pytest.mark.parametrize(
    ("type_", "payload", "ok"),
    [
        ("merged@1", MERGED, True),
        ("merged@1", {**MERGED, "cr": "x"}, False),
        ("merged@1", {**MERGED, "into_cr": "x"}, False),
        ("merged@1", {**MERGED, "merged_at": None}, True),
        ("merged@1", {**MERGED, "landed_with": "CR-2", "landed_at": None}, True),
        ("checks-red@1", RED, True),
        ("checks-red@1", {**RED, "cr": "x"}, False),
        ("checks-red@1", {**RED, "head": "f" * 64}, True),
        ("checks-red@1", {**RED, "head": "abc1234"}, False),
        ("board@1", {**schemas.PUBLISHED["board@1"].example, "action": "archive"}, True),
        ("config@1", {**SLOTS, "key": "x.y"}, True),
    ],
)
def test_a_model_fixes_the_json_types_and_the_formats_that_cannot_change(
    type_: str, payload: dict[str, Any], ok: bool
) -> None:
    payload = {k: v for k, v in payload.items() if k != "type"}
    if ok:
        schemas.validate(type_, payload)
    else:
        with pytest.raises(ValueError, match=f"journal payload {type_}"):
            schemas.validate(type_, payload)


@pytest.mark.parametrize("name", list(schemas.PUBLISHED))
def test_every_published_type_appends_in_order_refuses_a_bad_payload_and_keeps_its_duplicate_rule(
    repo: Path, name: str
) -> None:
    entry = schemas.PUBLISHED[name]
    found = Repo.find()
    path = changes(repo) / journal.FILE
    event = {"type": name, **entry.example}
    (one,) = journal.append(found, [event], "hub")
    assert list(one)[: len(HEAD)] == HEAD and (one["v"], one["type"]) == (2, name)
    before = path.read_bytes()
    extra = {**event, "unexpected": 1}
    missing = {k: v for k, v in event.items() if k != next(iter(entry.example))}
    for bad in (extra, missing):
        with pytest.raises(ValueError, match="journal payload"):
            journal.append(found, [bad], "hub")
    assert path.read_bytes() == before
    again = journal.append(found, [event], "hub")
    assert (len(again) == 1) is (entry.key is None)


def test_a_cli_event_that_is_refused_is_a_code_fault_and_writes_nothing(repo: Path) -> None:
    found = Repo.find()
    with pytest.raises(ValueError, match="journal payload checks-red@1"):
        journal.append(found, [{**RED, "type": "checks-red@1", "head": "abc1234"}], "cli")
    with pytest.raises(ValueError, match="journal type"):
        journal.append(found, [{"type": "nothing-known@1"}], "cli")
    assert not (changes(repo) / journal.FILE).exists()


def test_a_version_one_line_and_a_version_two_line_of_one_event_are_one_event(repo: Path) -> None:
    # a prepared journal: the version 1 lines an older hub or board wrote
    old_merged = {"v": 1, "seq": 1, "t": "t", "kind": "merged", "source": "hub"}
    old_red = {"v": 1, "seq": 2, "t": "t", "kind": "checks-red", "source": "hub"}
    folder = changes(repo)
    folder.mkdir(parents=True, exist_ok=True)
    lines = [
        {**old_merged, "audience": ["project"], **MERGED},
        {**old_red, "audience": ["project"], **RED},
    ]
    (folder / journal.FILE).write_text("".join(json.dumps(x) + "\n" for x in lines), "utf-8")
    found = Repo.find()
    assert journal.append(found, [{"type": "merged@1", **MERGED}], "board") == []
    assert journal.append(found, [{"type": "checks-red@1", **RED}], "board") == []
    landed = {**MERGED, "landed_with": "CR-2", "landed_at": "t"}
    assert len(journal.append(found, [{"type": "merged@1", **landed}], "board")) == 1


def _prepared(repo: Path) -> None:
    """A journal no writer produces: version 0, version 1 of each kind, an unknown version 2 type
    and a version 2 `merged@1` line whose payload its model refuses."""
    board = {"action": "move", "items": ["x"], "text": "x", "wakes": True}
    header = {"t": "t", "source": "hub", "audience": ["project"]}
    lines: list[dict[str, Any]] = [
        {"seq": 1, "t": "t", "by": "board", "kind": "board", **board},
        {"v": 1, "seq": 2, **header, "kind": "merged", **MERGED},
        {"v": 1, "seq": 3, **header, "kind": "checks-red", **RED},
        {
            "v": 1,
            "seq": 4,
            **header,
            "kind": "config",
            **{k: SLOTS[k] for k in SLOTS if k != "type"},
        },
        {"v": 1, "seq": 5, **header, "kind": "board", **board},
        {"v": 2, "seq": 6, **header, "type": "nothing-known@1", "x": 1},
        {"v": 2, "seq": 7, **header, "type": "merged@1", **{**MERGED, "cr": "x"}},
    ]
    folder = changes(repo)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / journal.FILE).write_text("".join(json.dumps(x) + "\n" for x in lines), "utf-8")


def test_read_gives_effective_types_and_sets_unknown_and_refused_lines_apart(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_batch(repo, chantier, monkeypatch, "Alpha")
    _prepared(repo)
    found = Repo.find()
    entries, bad, later, unknown = journal.read(found.store, found.changes)
    assert [e["type"] for e in entries[:5]] == [
        "board@1",
        "merged@1",
        "checks-red@1",
        "config@1",
        "board@1",
    ]
    assert (bad, later, unknown) == ([REFUSED], [], [(UNKNOWN, "nothing-known@1")])
    assert [e["audience"] for e in entries[5:]] == [[], []]
    assert journal.last_seq(entries) == REFUSED
    assert not any(journal.waking(e) for e in entries[5:])
    out = once(found, 0, [])
    assert sum(x.startswith("board wrote") for x in out) == BOARDS
    assert not any("nothing-known" in x for x in out)
    assert len([x for x in out if x.startswith(("forge saw", "config changed"))]) == TOLD
    status = chantier("status")[1]
    assert (
        f"{journal.FILE}: line 6 is of type nothing-known@1, unknown to this chantier: update it"
        in status
    )
    assert f"{journal.FILE}: line 7 unreadable" in status


def test_status_lines_skip_an_unknown_type_and_a_refused_payload_and_hide_nothing(
    repo: Path,
) -> None:
    # a prepared journal: the unknown and refused lines name an open CR; the newest slots line is
    # refused over an older valid one
    header = {"v": 2, "t": "t", "source": "hub", "audience": ["project"]}
    merged = {**MERGED, "batch": "b", "cr": "CR-5"}
    slots = {"key": "batch.slots", "old": 3, "new": 4, "batch": "b"}
    lines = [
        {**header, "seq": 1, "t": "2026-01-01T00:00:00Z", "type": "config@1", **slots},
        {**header, "seq": 2, "type": "nothing-known@1", **merged},
        {**header, "seq": 3, "type": "merged@1", **{**merged, "head": 1}},
        {**header, "seq": 4, "t": "2026-01-02T00:00:00Z", "type": "config@1", **slots, "new": []},
    ]
    folder = changes(repo)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / journal.FILE).write_text("".join(json.dumps(x) + "\n" for x in lines), "utf-8")
    entries = journal.read(Repo.find().store, Repo.find().changes)[0]
    out = journal.lines(entries, "b", {"CR-5"}, [])
    assert out == [schemas.config_text({**slots, "type": "config@1"})]

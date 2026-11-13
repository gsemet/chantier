"""The subset of YAML that `chantier.yaml` accepts.

`ruamel.yaml` reads the file (its pure-Python parser, loaded on first use: only the commands that
read `chantier.yaml` pay for the import). A short walk over its events builds the `Node` tree the
validators in `config.py` read, and refuses what the subset leaves out: anchors, aliases and tags,
block scalars, flow mappings, a list inside a list, a duplicate key, a tab in the indentation and
several documents. Scalars stay text: no value is ever converted to a number or a boolean."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

SCALAR, SEQUENCE, MAPPING, ALIAS = (
    "ScalarEvent",
    "SequenceStartEvent",
    "MappingStartEvent",
    "AliasEvent",
)
SKIPPED = {"StreamStartEvent", "StreamEndEvent", "DocumentStartEvent", "DocumentEndEvent"}
KEY = re.compile(r"[A-Za-z0-9_.-]+")
FOUND_WIDTH = 20


class YamlError(Exception):
    def __init__(self, line: int, message: str):
        super().__init__(message)
        self.line, self.message = line, message


@dataclass
class Node:
    kind: str  # "scalar", "list", "map" or "null"
    line: int
    value: Any = None  # scalar: str; list: [Node]; map: {key: (key line, Node)}


def _strip_comment(s: str) -> str:
    match = re.search(r"(?:^|\s)#", s)
    return s[: match.start()] if match else s


def _check_lines(text: str) -> None:
    """The refusals that are about a line, not about the parse: a tab, a document mark."""
    for number, raw in enumerate(text.splitlines(), 1):
        lead = raw[: len(raw) - len(raw.lstrip(" \t"))]
        body = _strip_comment(raw[len(lead) :]).rstrip()
        if not body:
            continue
        if "\t" in lead:
            raise YamlError(number, "a tab in the indentation: indent with spaces")
        if body in ("---", "...") or body.startswith(("--- ", "... ")):
            raise YamlError(number, "several documents (`---`) are not accepted: one document")


def _events(text: str) -> list[Any]:
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError

    try:
        return list(YAML(typ="safe", pure=True).parse(text))
    except YAMLError as e:
        mark = getattr(e, "problem_mark", None) or getattr(e, "context_mark", None)
        raise YamlError(mark.line + 1 if mark else 1, str(getattr(e, "problem", None) or e)) from e


def _line(event: Any) -> int:
    return int(event.start_mark.line) + 1


class _Walk:
    """The events of one document, taken in order."""

    def __init__(self, events: list[Any], lines: list[str]):
        self.events = [e for e in events if type(e).__name__ not in SKIPPED]
        self.lines = lines
        self.pos = 0

    def take(self) -> Any:
        event = self.events[self.pos]
        self.pos += 1
        return event

    def found(self, event: Any) -> str:
        row = self.lines[event.start_mark.line][event.start_mark.column :]
        return _strip_comment(row).strip()[:FOUND_WIDTH]

    def root(self) -> Node:
        if not self.events:
            return Node("map", 1, {})
        first = self.take()
        if type(first).__name__ == SCALAR and not first.value and first.style is None:
            return Node("map", 1, {})  # a file of comments
        if type(first).__name__ == SCALAR:
            row = self.lines[first.start_mark.line].strip()
            raise YamlError(_line(first), f"expected `key: value`, found: {row}")
        return self.node(first, _line(first))

    def refuse_markup(self, event: Any) -> None:
        if (
            type(event).__name__ == ALIAS
            or getattr(event, "anchor", None)
            or getattr(event, "tag", None)
        ):
            raise YamlError(
                _line(event),
                f"anchors, aliases and tags are not accepted: found `{self.found(event)}`",
            )

    def node(self, event: Any, line: int, in_list: bool = False) -> Node:
        self.refuse_markup(event)
        kind = type(event).__name__
        if kind == SCALAR:
            return self.scalar(event, line, in_list)
        if kind == SEQUENCE:
            return self.sequence(event, in_list)
        return self.mapping(event)

    def scalar(self, event: Any, line: int, in_list: bool) -> Node:
        if event.style in ("|", ">"):
            raise YamlError(
                _line(event),
                "block scalars (`|`, `>`) are not accepted: write the value on the line",
            )
        if not event.value and event.style is None:  # a plain, empty value
            if in_list:
                raise YamlError(_line(event), "a list item needs a value on its line")
            return Node("null", line)
        return Node("scalar", line, str(event.value))

    def sequence(self, event: Any, in_list: bool) -> Node:
        if in_list:
            raise YamlError(_line(event), "a list inside a list is not accepted")
        items = []
        while type(nxt := self.take()).__name__ != "SequenceEndEvent":
            items.append(self.node(nxt, _line(nxt), in_list=True))
        return Node("list", _line(event), items)

    def key(self, event: Any) -> str:
        self.refuse_markup(event)
        text = str(event.value) if type(event).__name__ == SCALAR else ""
        if not KEY.fullmatch(text):
            row = self.lines[event.start_mark.line].strip()
            raise YamlError(_line(event), f"expected `key: value`, found: {row}")
        return text

    def mapping(self, event: Any) -> Node:
        if event.flow_style:
            raise YamlError(
                _line(event), "flow mappings (`{}`) are not accepted: use a block mapping"
            )
        entries: dict[str, tuple[int, Node]] = {}
        while type(nxt := self.take()).__name__ != "MappingEndEvent":
            name, line = self.key(nxt), _line(nxt)
            if name in entries:
                raise YamlError(line, f"duplicate key `{name}` (first at line {entries[name][0]})")
            entries[name] = (line, self.node(self.take(), line))
        return Node("map", _line(event), entries)


def parse(text: str) -> Node:
    _check_lines(text)
    return _Walk(_events(text), text.splitlines()).root()

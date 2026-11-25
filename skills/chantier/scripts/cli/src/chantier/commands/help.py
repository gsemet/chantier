"""`help`: the plugin's help topics, read-only. A topic names the readings of `references/` a
rare case needs; the command prints one whole, or lists them. It reads no batch, no project, no
git and no network: only the plugin's own cards."""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path
from typing import Any, NamedTuple

from chantier import plugin_files
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError

HOSTS = ("claude", "copilot")
VERSION = re.compile(r"\d+\.\d+\.\d+")


class Topic(NamedTuple):
    name: str
    readings: list[Any]  # a str, or {"claude": str, "copilot": str}
    roles: list[str]
    trigger: str
    review_by: str | None


def _bad(name: str, problem: str) -> ChantierError:
    return ChantierError(f"topics.json: topic {name}: {problem}", EXIT_PRECONDITION)


def _lf(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def section(path: Path, heading: str) -> str:
    """The LF text from the line `## <heading>` to the next heading of level 1 or 2."""
    lines = _lf(path).splitlines(keepends=True)
    title = f"## {heading}"
    start = next((i for i, line in enumerate(lines) if line.rstrip("\n") == title), None)
    if start is None:
        raise ChantierError(f"{path.name}: no level-2 heading `{title}`", EXIT_PRECONDITION)
    end = next(
        (i for i in range(start + 1, len(lines)) if re.match(r"#{1,2} ", lines[i])), len(lines)
    )
    return "".join(lines[start:end])


def _forms(name: str, reading: Any) -> list[str]:
    if isinstance(reading, dict):
        if set(reading) != set(HOSTS) or not all(isinstance(v, str) for v in reading.values()):
            raise _bad(name, f"a host map reading needs exactly {HOSTS}")
        return list(reading.values())
    if not isinstance(reading, str) or not reading:
        raise _bad(name, f"a reading is a file, file#heading or a host map, not {reading!r}")
    return [reading]


def _check_reading(base: Path, name: str, form: str) -> None:
    if form.startswith("@"):
        raise _bad(name, f"reading {form}: the @action form is not allowed")
    file, _, heading = form.partition("#")
    path = base / file
    if not path.is_file():
        raise _bad(name, f"reading {form}: no file {file}")
    if heading:
        try:
            body = section(path, heading)
        except ChantierError as e:
            raise _bad(name, f"reading {form}: {e}") from None
        if not body.partition("\n")[2].strip():
            raise _bad(name, f"reading {form}: an empty section")


def load_topics(path: Path | None = None) -> dict[str, Topic]:
    """The topics of `references/topics.json` (or of `path`), checked; a problem raises
    `ChantierError` naming the topic."""
    path = path or plugin_files.skill_dir() / "references" / "topics.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ChantierError(f"topics.json: not readable: {e}", EXIT_PRECONDITION) from None
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ChantierError("topics.json: version 1 expected", EXIT_PRECONDITION)
    raw = data.get("topics")
    if not isinstance(raw, dict) or not raw:
        raise ChantierError("topics.json: no topics", EXIT_PRECONDITION)
    return {name: _topic(path.parent, name, t) for name, t in raw.items()}


def _topic(base: Path, name: str, t: Any) -> Topic:
    if not isinstance(t, dict):
        raise _bad(name, "not an object")
    readings, roles, trigger = t.get("readings"), t.get("roles"), t.get("trigger")
    if not isinstance(readings, list) or not readings:
        raise _bad(name, "readings: a non-empty list expected")
    if not isinstance(roles, list) or not roles or not all(isinstance(r, str) for r in roles):
        raise _bad(name, "roles: a non-empty list of names expected")
    if not isinstance(trigger, str) or not trigger.strip():
        raise _bad(name, "trigger: a non-empty text expected")
    review = t.get("review_by")
    if review is not None and not (isinstance(review, str) and VERSION.fullmatch(review)):
        raise _bad(name, f"review_by: X.Y.Z expected, not {review!r}")
    for reading in readings:
        for form in _forms(name, reading):
            _check_reading(base, name, form)
    return Topic(name, readings, roles, trigger, review)


def _known_roles() -> list[str]:
    manifest = plugin_files.skill_dir() / "references" / "startup-manifest.json"
    try:
        return list(json.loads(manifest.read_text(encoding="utf-8"))["roles"])
    except (OSError, ValueError, KeyError) as e:
        raise ChantierError(f"startup-manifest.json: no roles: {e}", EXIT_PRECONDITION) from None


def _print_topic(topic: Topic, host: str, base: Path) -> list[str]:
    out = [f"topic {topic.name}: {topic.trigger} ({', '.join(topic.roles)})"]
    for reading in topic.readings:
        form = reading[host] if isinstance(reading, dict) else reading
        file, _, heading = form.partition("#")
        out.append(f"--- references/{form} ---")
        text = section(base / file, heading) if heading else _lf(base / file)
        out += text.rstrip("\n").split("\n")
    return out


def show(args: argparse.Namespace) -> list[str]:
    topic, role = args.topic, args.role
    if topic and role:
        raise ChantierError("help takes a topic or --for, not both", EXIT_USAGE)
    topics = load_topics()
    if topic:
        if topic not in topics:
            close = difflib.get_close_matches(topic, list(topics))
            guess = (
                "; did you mean " + " or ".join(f"help {c}" for c in close) + "?" if close else ""
            )
            raise ChantierError(f"no topic {topic}{guess}; help lists them all", EXIT_USAGE)
        host = args.host or plugin_files.detect_host()
        return _print_topic(topics[topic], host, plugin_files.skill_dir() / "references")
    if role:
        known = _known_roles()
        if role not in known:
            raise ChantierError(f"no role {role}; roles: {', '.join(known)}", EXIT_USAGE)
        mine = [t for t in topics.values() if role in t.roles]
        if not mine:
            return [f"no topic for {role}; help lists them all"]
        return [f"{t.name}: {t.trigger}" for t in mine]
    return [
        f"topics: {len(topics)}; help <topic> prints one, help --for <role> lists a role's",
        *(f"{t.name}: {t.trigger} ({', '.join(t.roles)})" for t in topics.values()),
    ]

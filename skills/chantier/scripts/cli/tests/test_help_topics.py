"""`help`: the topic index (`references/topics.json`) resolves on both hosts, every piece has a
topic, every topic a CLI line names exists, and the command prints what it says. The shipped
files are read at the head under test; the prepared files cover only what none of them can hold."""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from conftest import SKILL

import chantier
from chantier.board.cli_run import judge
from chantier.cli import main
from chantier.commands.help import load_topics, section
from chantier.core import remote_wire
from chantier.core.errors import ChantierError

REFERENCES = SKILL / "references"
SRC = Path(chantier.__file__).resolve().parent
MIN_NAMED = 19  # 5 lease refusals, 2 push, 2 restack, 1 handed back, 9 watcher lines, as written
PIECE = re.compile(r"(driver|foreman|stack-driver|release-driver|chief-of-staff)-[a-z-]+\.md")
ROLES = list(json.loads((REFERENCES / "startup-manifest.json").read_text("utf-8"))["roles"])
LEASE_SECTION = section(REFERENCES / "driver-session.md", "Means: the lease")


def _run(
    capsys: pytest.CaptureFixture[str], *argv: str, cwd: Path | None = None
) -> tuple[int, list[str], str]:
    code = main(list(argv))
    out = capsys.readouterr()
    return code, out.out.splitlines(), out.err


@pytest.mark.parametrize("host", ["claude", "copilot"])
def test_every_topic_resolves_on_both_hosts(host: str) -> None:
    topics = load_topics()
    assert topics
    for t in topics.values():
        assert t.trigger.strip() and set(t.roles) <= set(ROLES), t.name
        for reading in t.readings:
            form = reading[host] if isinstance(reading, dict) else reading
            file, _, heading = form.partition("#")
            body = (
                section(REFERENCES / file, heading)
                if heading
                else (REFERENCES / file).read_text("utf-8")
            )
            assert body.strip(), (t.name, form)
        assert t.review_by is None or re.fullmatch(r"\d+\.\d+\.\d+", t.review_by), t.name


def test_every_piece_has_a_topic() -> None:
    read = {
        r.partition("#")[0]
        for t in load_topics().values()
        for reading in t.readings
        for r in ([*reading.values()] if isinstance(reading, dict) else [reading])
    }
    pieces = {p.name for p in REFERENCES.iterdir() if PIECE.fullmatch(p.name)} - {
        "chief-of-staff-any.md"
    }
    assert pieces and pieces <= read, sorted(pieces - read)


def test_every_topic_a_line_names_exists() -> None:
    names = [
        m
        for path in SRC.rglob("*.py")
        for m in re.findall(r"`help ([a-z][a-z0-9-]*)`", path.read_text(encoding="utf-8"))
    ]
    assert len(names) >= MIN_NAMED, len(names)
    assert set(names) <= set(load_topics()), sorted(set(names) - set(load_topics()))


@pytest.mark.parametrize("role", ["cr-driver", "stack-driver", "foreman", "chief-of-staff"])
def test_for_lists_only_that_roles_topics(capsys: pytest.CaptureFixture[str], role: str) -> None:
    code, out, _ = _run(capsys, "help", "--for", role)
    assert code == 0
    assert {ln.partition(":")[0] for ln in out} == {
        n for n, t in load_topics().items() if role in t.roles
    }


def test_for_a_worker_and_for_an_unknown_role(capsys: pytest.CaptureFixture[str]) -> None:
    assert _run(capsys, "help", "--for", "coder")[:2] == (
        0,
        ["no topic for coder; help lists them all"],
    )
    code, _, err = _run(capsys, "help", "--for", "nobody")
    assert code == 1 and "no role nobody; roles: cr-driver" in err


def test_help_lists_them_all(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = _run(capsys, "help")
    assert code == 0 and out[0].startswith(f"topics: {len(load_topics())};")
    assert len(out) == 1 + len(load_topics())


def test_help_lease_prints_the_section_whole_with_no_project(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    code, out, err = _run(capsys, "help", "lease")
    assert code == 0, err
    assert out[0].startswith("topic lease: ")
    text = "\n".join(out)
    assert LEASE_SECTION.rstrip("\n") in text
    assert "## Means: checkpoint commits" not in text


def test_help_refuses_a_near_name_and_a_topic_with_for(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = _run(capsys, "help", "leas")
    assert code == 1 and "no topic leas; did you mean help lease" in err
    assert "help lists them all" in err
    code, _, err = _run(capsys, "help", "lease", "--for", "cr-driver")
    assert code == 1 and "help takes a topic or --for, not both" in err


def test_help_stays_local() -> None:
    assert "help" in remote_wire.NEVER_REMOTE
    cmd, why = judge(SimpleNamespace(argv=["help", "lease"], env={}, project=None, stdin=None))
    assert cmd == "help" and why == "cli.run: help does not run through the server"


def _topics_file(tmp_path: Path, reading: Any, **more: Any) -> Path:
    (tmp_path / "a.md").write_text("# A\n\n## One\n\ntext\n\n## Two\n\nmore\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# B\n\nother\n", encoding="utf-8")
    topic = {"readings": [reading], "roles": ["foreman"], "trigger": "when", **more}
    path = tmp_path / "topics.json"
    path.write_text(json.dumps({"version": 1, "topics": {"t": topic}}), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("reading", "more", "problem"),
    [
        ("@driver:session", {}, "@action form is not allowed"),
        ("a.md#Three", {}, "no level-2 heading"),
        ("a.md#One", {"review_by": "next"}, "review_by"),
    ],
    ids=["prepared @action", "prepared missing heading", "prepared bad review_by"],
)
def test_prepared_topics_are_refused(
    tmp_path: Path, reading: Any, more: dict[str, Any], problem: str
) -> None:
    with pytest.raises(ChantierError, match=problem):
        load_topics(_topics_file(tmp_path, reading, **more))


def test_prepared_host_map_reading_is_resolved_per_host(tmp_path: Path) -> None:
    path = _topics_file(tmp_path, {"claude": "a.md#One", "copilot": "b.md"}, review_by="0.16.0")
    assert load_topics(path)["t"].review_by == "0.16.0"
    from chantier.commands import help as help_command  # noqa: PLC0415

    topic = load_topics(path)["t"]
    claude = help_command._print_topic(topic, "claude", tmp_path)
    copilot = help_command._print_topic(topic, "copilot", tmp_path)
    assert claude[1] == "--- references/a.md#One ---" and "text" in claude
    assert copilot[1] == "--- references/b.md ---" and "other" in copilot

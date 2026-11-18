import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import PLUGIN_ROOT, SKILL

STARTUP_LIMIT = 12_544
DRIVER_ROLES = ("cr-driver", "stack-driver", "qa-driver", "release-driver")
MANIFEST_VERSION = 2
WITH_SECTIONS = {*DRIVER_ROLES, "foreman", "chief-of-staff", "griller", "router", "status"}
FOREMAN_SECTIONS = [
    "concepts.md#Startup core",
    {"claude": "hosts/claude-code.md#Startup core", "copilot": "hosts/copilot.md#Startup core"},
]


def _manifest() -> tuple[dict[str, Any], Path]:
    path = SKILL / "references" / "startup-manifest.json"
    return json.loads(path.read_text(encoding="utf-8")), path


def _roles() -> dict[str, Path]:
    roles = {p.stem: p for p in (PLUGIN_ROOT / "agents").glob("*.md")}
    roles.update(
        {
            "router" if p.parent.name == "chantier" else p.parent.name: p
            for p in (PLUGIN_ROOT / "skills").glob("*/SKILL.md")
        }
    )
    roles["foreman"] = PLUGIN_ROOT / "skills" / "chantier" / "references" / "chief-of-staff.md"
    return roles


def _lf_bytes(path: Path) -> bytes:
    """The file's bytes in their LF form, so a CRLF checkout measures like a LF one."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def _section_span(path: Path, heading: str) -> tuple[int, int]:
    lines = _lf_bytes(path).splitlines(keepends=True)
    title = heading.encode("utf-8")
    try:
        start = next(i for i, line in enumerate(lines) if line.rstrip(b"\r\n") == title)
    except StopIteration:
        raise AssertionError(f"{path}: missing mandatory section {heading}") from None
    level = len(title) - len(title.lstrip(b"#"))
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if re.match(rb"#{1," + str(level).encode() + rb"} ", lines[i])
        ),
        len(lines),
    )
    return sum(map(len, lines[:start])), sum(map(len, lines[:end]))


def _section_bytes(path: Path, heading: str) -> int:
    start, end = _section_span(path, heading)
    return end - start


def _unique_startup_bytes(paths: list[Path], sections: list[dict[str, str]]) -> int:
    spans: dict[Path, list[tuple[int, int]]] = {}
    for path in paths:
        spans.setdefault(path.resolve(), []).append((0, len(_lf_bytes(path))))
    for section in sections:
        path = Path(section["file"]).resolve()
        spans.setdefault(path, []).append(_section_span(path, section["heading"]))
    total = 0
    for ranges in spans.values():
        covered = 0
        for start, end in sorted(ranges):
            total += max(0, end - max(start, covered))
            covered = max(covered, end)
    return total


def _resolve(reading: Any, host: str) -> dict[str, str]:
    """A reading as an absolute file and, for `file#heading`, its level-2 heading line."""
    if isinstance(reading, dict):
        assert set(reading) == {"claude", "copilot"}, reading
        reading = reading[host]
    file, _, heading = reading.partition("#")
    path = (_manifest()[1].parent / file).resolve()
    assert path.is_file(), reading
    return {"file": str(path), "heading": f"## {heading}" if heading else ""}


def _sections(readings: list[Any], host: str) -> tuple[list[Path], list[dict[str, str]]]:
    resolved = [_resolve(r, host) for r in readings]
    files = [Path(r["file"]) for r in resolved if not r["heading"]]
    return files, [r for r in resolved if r["heading"]]


def _check_actions(manifest: dict[str, Any]) -> set[Path]:
    assert isinstance(manifest["paths"], str)
    readings = {
        key: manifest[key]
        for key in ("manifest", "common", "role_core", "hosts", "entries", "roles")
    }
    readings |= {"startup_sections": manifest["startup_sections"], "actions": manifest["actions"]}
    assert "paths" not in readings
    assert manifest["paths"] not in json.dumps(readings)
    action_reads: set[Path] = set()
    for host in ("claude", "copilot"):
        for action in manifest["actions"].values():
            files, sections = _sections(action, host)
            action_reads |= set(files) | {Path(s["file"]) for s in sections}
            assert all(_section_bytes(Path(s["file"]), s["heading"]) > 0 for s in sections)
    assert manifest["actions"]["reload"][:3] == [
        manifest["common"],
        manifest["role_core"],
        manifest["manifest"],
    ]
    for role, heading in {
        "cr-driver": "CR driver",
        "stack-driver": "Stack driver",
        "qa-driver": "QA driver",
        "release-driver": "Release driver",
    }.items():
        card = manifest["roles"][role]
        assert manifest["actions"][role] == [f"{card}#Your means", f"{card}#{heading}"]
    return action_reads


def _wrapper_path(role: str, host: str, entry: dict[str, Any], wrapper: Path) -> Path | None:
    if entry.get("wrapper") is None and role == "foreman":
        return None
    if role in {"chief-of-staff", "griller", "router", "status"}:
        return wrapper
    folder = "agents" if host == "claude" else "com.github.copilot/agents"
    name = f"{role}.md" if host == "claude" else f"chantier-{role}.agent.md"
    return PLUGIN_ROOT / folder / name


def _reload_bytes(
    manifest: dict[str, Any], host: str, required: list[Path], sections: list[dict[str, str]]
) -> int:
    files, reload_sections = _sections(manifest["actions"]["reload"], host)
    return _unique_startup_bytes(required + files, sections + reload_sections)


@pytest.mark.parametrize("host", ["claude", "copilot"])
def test_startup_manifest_measures_every_real_role_and_host(host: str) -> None:
    manifest, manifest_path = _manifest()
    assert manifest["version"] == MANIFEST_VERSION
    assert manifest["limit"] == STARTUP_LIMIT
    folder = manifest_path.parent
    roles = _roles()
    assert manifest["actions"]
    action_reads = _check_actions(manifest)
    for role, card in manifest["roles"].items():
        assert role in roles
        assert (folder / card).is_file()
    assert set(manifest["startup_sections"]) == WITH_SECTIONS
    for role, wrapper in roles.items():
        entry = manifest.get("entries", {}).get(role, {})
        wrapper_path = _wrapper_path(role, host, entry, wrapper)
        required = [
            folder / manifest["common"],
            folder / manifest["hosts"][host]["core"],
            folder / manifest["role_core"],
            manifest_path,
        ]
        if wrapper_path is not None:
            required.append(wrapper_path)
        files, sections = _sections(manifest["startup_sections"].get(role, []), host)
        assert not files
        total = _unique_startup_bytes(required, sections)
        assert total <= STARTUP_LIMIT, (role, host, total)
        reload_total = _reload_bytes(manifest, host, required, sections)
        assert reload_total <= STARTUP_LIMIT, (role, host, "reload", reload_total)
        print(f"startup-bytes role={role} host={host} bytes={total} reload={reload_total}")
        if role == "foreman":
            assert manifest["startup_sections"]["foreman"] == FOREMAN_SECTIONS
            assert entry == {"wrapper": None, "prompt_builder": "chief-of-staff.md"}
            continue
        assert wrapper_path is not None
        declared = {Path(folder / manifest[k]).resolve() for k in ("common", "role_core")}
        declared |= {(folder / manifest["hosts"][host]["core"]).resolve()}
        declared |= {Path(s["file"]) for s in sections} | action_reads
        boot = "\n".join(wrapper_path.read_text(encoding="utf-8").splitlines()[:45])
        for reference in re.findall(r"references/([A-Za-z0-9._/-]+\.md)", boot):
            found = (SKILL / "references" / reference).resolve()
            assert found in declared, (role, host, reference)


def test_empty_action_readings_are_rejected() -> None:
    manifest, _ = _manifest()
    assert all(manifest["actions"].values())


def test_reading_union_counts_lf_bytes_and_nested_sections_once(tmp_path: Path) -> None:
    path = tmp_path / "card.md"
    data = b"# Card\r\n\r\n## Core\r\n\xc3\xa9\r\n### Nested\r\nrules\r\n## Later\r\nend\r\n"
    path.write_bytes(data)
    data = data.replace(b"\r\n", b"\n")
    core = {"file": str(path), "heading": "## Core"}
    nested = {"file": str(path), "heading": "### Nested"}
    assert _unique_startup_bytes([], [core, nested, core]) == len(
        data[data.index(b"## Core") : data.index(b"## Later")]
    )
    assert _unique_startup_bytes([path, path], [core, nested]) == len(data)


def test_reload_budget_includes_additional_whole_file_readings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, path = _manifest()
    manifest["actions"]["reload"].append("foreman.md")
    monkeypatch.setattr(sys.modules[__name__], "_manifest", lambda: (manifest, path))
    with pytest.raises(AssertionError, match="reload"):
        test_startup_manifest_measures_every_real_role_and_host("copilot")


REFS = SKILL / "references"
SKILLS = PLUGIN_ROOT / "skills"
WORKER_CARDS = ("coder", "inspector", "verifier", "demo-explorer")


def _text(path: Path, heading: str | None = None) -> str:
    data = _lf_bytes(path)
    if heading:
        start, end = _section_span(path, f"## {heading}")
        data = data[start:end]
    return " ".join(data.decode("utf-8").split())


def _agent_files() -> list[Path]:
    return [
        *(PLUGIN_ROOT / "agents").glob("*.md"),
        *(PLUGIN_ROOT / "com.github.copilot" / "agents").glob("*.agent.md"),
    ]


START, COS = REFS / "session-start.md", SKILLS / "chief-of-staff" / "SKILL.md"
GRILLER, CHIEF_CARD = SKILLS / "griller" / "SKILL.md", REFS / "chief-of-staff.md"
FIRST_TURN, CORE = "4. First turn: introduce chantier", "Startup core"
SESSION = "At the session's start, read `session-start.md`"
ABOUT_FOREMAN = (
    "named startup sections of <skill>/references/concepts.md and <skill>/references/hosts/"
)
MOVED_IN = [
    ("It repeats no grant and starts no service twice.", START, "5. Reload"),
    ("a CR's archive in its PR when the project asks", START, FIRST_TURN),
    ("A prompt names the card and section it expects", REFS / "concepts.md", None),
    ("a host path not exercised is labelled untested", REFS / "startup-core.md", None),
    ("At startup read the startup core and the startup sections", REFS / "foreman.md", None),
    (ABOUT_FOREMAN, CHIEF_CARD, None),
    ("A `Note: resume: closing` reads only", REFS / "driver.md", CORE),
    (SESSION, COS, CORE),
    (SESSION, GRILLER, CORE),
    ("with `$CHANTIER` as this file defines it, nothing else of this file but its", COS, CORE),
    *[("At startup read the startup core; defer", REFS / f"{c}.md", None) for c in WORKER_CARDS],
]

MOVED_OUT = [
    ("Read this short role contract at boot", [*SKILLS.rglob("*.md")]),
    ("defer all other card sections", _agent_files()),
    *[("short Startup core section", [REFS / f"{c}.md"]) for c in WORKER_CARDS],
    ("the short `Startup core` section", [REFS / "foreman.md"]),
    ("named startup sections only", [REFS / "foreman.md"]),
    ("startup sections of <skill>/references/foreman.md", [REFS / "chief-of-staff.md"]),
    ("Availability is not proof", [*REFS.glob("host-core-*.md")]),
]


@pytest.mark.parametrize(("phrase", "path", "heading"), MOVED_IN)
def test_moved_rule_is_where_it_now_lives(phrase: str, path: Path, heading: str | None) -> None:
    assert phrase in _text(path, heading)


@pytest.mark.parametrize(("phrase", "paths"), MOVED_OUT)
def test_moved_rule_is_gone_from_where_it_was(phrase: str, paths: list[Path]) -> None:
    assert paths
    assert [p for p in paths if phrase in _text(p)] == []


def test_the_rules_that_must_not_be_missed_come_first() -> None:
    paragraphs = _lf_bytes(REFS / "startup-core.md").decode("utf-8").split("\n\n")
    assert "report the exact error and stop" in " ".join(paragraphs[1].split())
    assert "never in a shell variable" in " ".join(paragraphs[1].split())
    assert paragraphs[2].startswith("No fallback")
    for skill, needle in {
        "chief-of-staff": "`watch: not running`",
        "chantier": "live Chief of Staff in the seat",
        "status": "You change nothing",
    }.items():
        first = _lf_bytes(SKILLS / skill / "SKILL.md").decode("utf-8").split("## Startup core\n")[1]
        assert needle in next(line for line in first.splitlines() if line.strip()), skill

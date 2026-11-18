import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import PLUGIN_ROOT, SKILL

STARTUP_LIMIT = 12_544


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
        path = (PLUGIN_ROOT / section["file"]).resolve()
        spans.setdefault(path, []).append(_section_span(path, section["heading"]))
    total = 0
    for ranges in spans.values():
        covered = 0
        for start, end in sorted(ranges):
            total += max(0, end - max(start, covered))
            covered = max(covered, end)
    return total


def _reading_file(reading: str | dict[str, str]) -> str:
    return reading if isinstance(reading, str) else reading["file"]


def _check_actions(manifest: dict[str, Any]) -> set[str]:
    action_reads = {_reading_file(r) for readings in manifest["actions"].values() for r in readings}
    assert all((PLUGIN_ROOT / r).is_file() for r in action_reads)
    for readings in manifest["actions"].values():
        for reading in readings:
            if isinstance(reading, dict):
                assert set(reading) <= {"host", "file", "heading"}
                assert _section_bytes(PLUGIN_ROOT / reading["file"], reading["heading"]) > 0
    assert manifest["actions"]["reload"][:3] == [
        manifest["common"],
        manifest["role_core"],
        manifest["manifest"],
    ]
    for role, heading in {
        "cr-driver": "## CR driver",
        "stack-driver": "## Stack driver",
        "qa-driver": "## QA driver",
        "release-driver": "## Release driver",
    }.items():
        expected = {"file": manifest["roles"][role], "heading": heading}
        assert {"file": manifest["roles"][role], "heading": "## Your means"} in manifest["actions"][
            role
        ]
        assert expected in manifest["actions"][role]
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
    readings = manifest["actions"]["reload"]
    reload_sections = [
        reading
        for reading in readings
        if isinstance(reading, dict) and reading.get("host", host) == host
    ]
    reload_files = [PLUGIN_ROOT / reading for reading in readings if isinstance(reading, str)]
    return _unique_startup_bytes(required + reload_files, sections + reload_sections)


@pytest.mark.parametrize("host", ["claude", "copilot"])
def test_startup_manifest_measures_every_real_role_and_host(host: str) -> None:
    manifest, manifest_path = _manifest()
    assert manifest["limit"] == STARTUP_LIMIT
    roles = _roles()
    assert manifest["actions"]
    action_reads = _check_actions(manifest)
    for role, card in manifest["roles"].items():
        assert role in roles
        assert (PLUGIN_ROOT / card).is_file()
    for role, wrapper in roles.items():
        entry = manifest.get("entries", {}).get(role, {})
        wrapper_path = _wrapper_path(role, host, entry, wrapper)
        required = [
            PLUGIN_ROOT / manifest["common"],
            PLUGIN_ROOT / manifest["hosts"][host]["core"],
            PLUGIN_ROOT / manifest["role_core"],
            manifest_path,
        ]
        if wrapper_path is not None:
            required.append(wrapper_path)
        sections = [
            section
            for section in manifest["mandatory_sections"].get(role, [])
            if section.get("host", host) == host
        ]
        assert sections
        total = _unique_startup_bytes(required, sections)
        assert total <= STARTUP_LIMIT, (role, host, total)
        reload_total = _reload_bytes(manifest, host, required, sections)
        assert reload_total <= STARTUP_LIMIT, (role, host, "reload", reload_total)
        print(f"startup-bytes role={role} host={host} bytes={total} reload={reload_total}")
        if role == "foreman":
            host_card = (
                f"skills/chantier/references/hosts/{'claude-code' if host == 'claude' else host}.md"
            )
            assert {"host": host, "file": host_card, "heading": "## Startup core"} in sections
            assert entry == {
                "wrapper": None,
                "prompt_builder": "skills/chantier/references/chief-of-staff.md",
            }
            continue
        assert wrapper_path is not None
        declared = {manifest["common"], manifest["role_core"], manifest["hosts"][host]["core"]}
        declared |= {s["file"] for s in sections} | action_reads
        boot = "\n".join(wrapper_path.read_text(encoding="utf-8").splitlines()[:45])
        for reference in re.findall(r"references/([A-Za-z0-9._/-]+\.md)", boot):
            assert f"skills/chantier/references/{reference}" in declared, (role, host, reference)


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
    manifest["actions"]["reload"].append("skills/chantier/references/foreman.md")
    monkeypatch.setattr(sys.modules[__name__], "_manifest", lambda: (manifest, path))
    with pytest.raises(AssertionError, match="reload"):
        test_startup_manifest_measures_every_real_role_and_host("copilot")

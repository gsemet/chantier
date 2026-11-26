"""The host rows (`references/hosts/*.json`) and `chantier host`: the data's shape, that no row
carries history, that each capability has its story in `docs/proofs/`, and the command's
answers on prepared states, in-process."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from batch_helpers import host, open_batch, record, write_record
from conftest import PLUGIN_ROOT, SKILL, Chantier

from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE
from chantier.host_rows import FILES, UNTESTED, load_rows, row_lines
from chantier.plugin_files import HOSTS, plugin_roles

CARDS = {"claude": "claude-code", "copilot": "copilot"}
EXTRA_ROLES = {"chief-of-staff", "foreman", "griller"}
HISTORY = re.compile(
    r"\d{4}-\d{2}-\d{2}|batch-\d+|CR-\d+|PR \d+|#\d+"
    r"|\b(proved|unproved|documented|untested|trial)\b",
    re.I,
)
KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MIN_MEANS, MAX_MEANS, MAX_LINE = 2, 4, 160
KNOWN = 50


def _raw(host_name: str) -> dict[str, object]:
    path = SKILL / "references" / "hosts" / FILES[host_name]
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return data


@pytest.mark.parametrize("name", HOSTS)
def test_every_row_has_means_and_a_one_word_mark(name: str) -> None:
    rows = load_rows(name)
    assert _raw(name)["host"] == name
    assert [r.capability for r in rows] == [r.capability for r in load_rows("claude")]
    assert len(rows) == KNOWN
    assert len({r.capability for r in rows}) == len(rows)
    valid = set(plugin_roles(name)) | EXTRA_ROLES
    for r in rows:
        assert KEBAB.match(r.capability), r.capability
        assert r.name, r.capability
        assert r.roles and set(r.roles) <= valid, (r.capability, r.roles)
        assert MIN_MEANS <= len(r.means) <= MAX_MEANS, r.capability
        assert all(m and len(m) <= MAX_LINE for m in r.means), r.capability
        assert r.mark in ("proved", "untested"), r.capability


def test_every_copilot_row_is_untested() -> None:
    assert {r.mark for r in load_rows("copilot")} == {"untested"}


@pytest.mark.parametrize("name", HOSTS)
def test_means_carry_no_history(name: str) -> None:
    found = [
        (r.capability, line, m.group(0))
        for r in load_rows(name)
        for line in r.means
        if (m := HISTORY.search(line))
    ]
    assert not found, found


@pytest.mark.parametrize("name", HOSTS)
def test_every_untested_row_prints_the_sentence(name: str) -> None:
    for r in load_rows(name):
        lines = row_lines(r)
        assert lines[0] == f"{r.capability}: {r.name} ({r.mark})"
        assert lines[1 : 1 + len(r.means)] == [f"  {m}" for m in r.means]
        if r.mark == "proved":
            assert len(lines) == 1 + len(r.means), r.capability
        else:
            assert lines[-1] == f"  {UNTESTED}", r.capability


@pytest.mark.parametrize("name", HOSTS)
def test_every_capability_is_a_heading_in_the_proof_file(name: str) -> None:
    text = (PLUGIN_ROOT / "docs" / "proofs" / f"{CARDS[name]}.md").read_text(encoding="utf-8")
    headings = [ln[3:].strip() for ln in text.splitlines() if ln.startswith("## ")]
    assert [r.capability for r in load_rows(name)] == [
        h for h in headings if not h.startswith("Other: ")
    ]


def test_an_unknown_capability_lists_the_known_ones(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    code, out, err = chantier("host", "nope")
    assert code == EXIT_PRECONDITION and not out
    ids = [r.capability for r in load_rows("claude")]
    assert err.strip() == f"error: unknown capability `nope` on claude: one of {', '.join(ids)}"
    assert "start-driver" in err


def test_the_batch_record_decides_the_host(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_batch(repo, chantier, monkeypatch, "Fix login")
    batch = record(repo)["id"]
    code, out, _ = chantier("host", "start-driver")
    assert (code, out[0]) == (0, f"host: claude ({batch})")
    assert out[1].endswith("(proved)") and UNTESTED not in out
    data = record(repo)
    data["host"] = "copilot"
    write_record(repo, data)
    code, out, _ = chantier("host", "start-driver")  # the session is still Claude's
    assert (code, out[0]) == (0, f"host: copilot ({batch})")
    assert out[1].endswith("(untested)") and out[-1] == f"  {UNTESTED}"
    code, every, _ = chantier("host")
    rows = load_rows("copilot")
    assert code == 0 and every.count("") == len(rows) - 1
    assert [ln.split(":")[0] for ln in every[1:] if ln and not ln.startswith(" ")] == [
        r.capability for r in rows
    ]


def test_no_host_and_no_batch_is_refused(repo: Path, chantier: Chantier) -> None:
    code, out, err = chantier("host")
    assert code == EXIT_USAGE and not out
    assert "cannot tell the host" in err
    code, out, _ = chantier("host", "start-driver", "--batch", "9")
    assert code != 0 and not out

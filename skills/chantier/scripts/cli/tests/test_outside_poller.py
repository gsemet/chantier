"""An outside poller: `chantier interests` lists what the CRs wait for, `chantier journal add`
appends an `issue@1` line for an issue a CR's `issue:` line names, and refuses everything else."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from conftest import Chantier
from forge_world import EXIT_PRECONDITION, EXIT_USAGE, crs_of, write_batch

from chantier.hub import issue_refs, journal

JIRA = "https://acme.atlassian.net/browse/PAY-12"
GITHUB = "https://github.com/acme/demo/issues/7"
ODD = "https://example.org/tickets/5"
GONE = "https://acme.atlassian.net/browse/PAY-99"
BY = ["1-inbox/export", "2-backlog/P2/export-again"]
PAYLOAD = {
    "tracker": "jira",
    "ref": JIRA,
    "event": "commented",
    "at": "2026-11-20T09:14:00Z",
    "text": "a comment asks to keep the old column order",
}
WRITTEN = f"journal: seq 1 issue@1 commented on {JIRA} ({', '.join(BY)})"


def plan(repo: Path) -> Path:
    """A planning folder: two CRs naming one Jira link, a GitHub one, one no tracker places, an
    archived and a trashed one naming another link, and one with no `issue:` line."""
    changes = repo / ".agents" / "changes"
    for folder, link in {
        "1-inbox/export": JIRA,
        "2-backlog/P2/export-again": JIRA,
        "3-ready/gh": GITHUB,
        "3-ready/odd": ODD,
        "5-archives/old": GONE,
        "6-trash/gone": GONE,
        "1-inbox/none": None,
    }.items():
        (changes / folder).mkdir(parents=True)
        text = "# t\n" + (f"\nissue: {link}\n" if link else "")
        (changes / folder / "01-intent.md").write_text(text, encoding="utf-8")
    return changes


def tree(base: Path) -> dict[str, bytes]:
    return {p.relative_to(base).as_posix(): p.read_bytes() for p in base.rglob("*") if p.is_file()}


def add(
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    payload: Any,
    type_: str = "issue@1",
) -> tuple[int, list[str], str]:
    """`journal add <type> --json -` with the payload on stdin (a string, bytes or a dict)."""
    if not isinstance(payload, (str, bytes)):
        payload = json.dumps(payload)
    raw = payload if isinstance(payload, bytes) else payload.encode("utf-8")
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8"))
    return chantier("journal", "add", type_, "--json", "-")


def lines(changes: Path) -> list[dict[str, Any]]:
    path = changes / journal.FILE
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def test_interests_lists_the_issues_the_crs_name_and_writes_nothing(
    repo: Path, chantier: Chantier
) -> None:
    changes = plan(repo)
    before = tree(changes)
    code, out, err = chantier("interests", "--kind", "issue", "--json")
    got = json.loads(out[0])
    assert (code, err, got["errors"], got["project"]) == (0, "", [], repo.name)
    assert [(i["ref"], i["tracker"], i["read_by"], i["by"]) for i in got["interests"]] == [
        (JIRA, "jira", "outside", BY[0]),
        (JIRA, "jira", "outside", BY[1]),
        (GITHUB, "github", "outside", "3-ready/gh"),
        (ODD, "other", "outside", "3-ready/odd"),
    ]
    assert got["interests"][0]["facts"] == ["events"]
    assert chantier("interests", "--kind", "issue")[1] == [
        f"interests of {repo.name}: 4",
        f"issue {JIRA} (jira): events for {BY[0]}",
        f"issue {JIRA} (jira): events for {BY[1]}",
        f"issue {GITHUB} (github): events for 3-ready/gh",
        f"issue {ODD} (other): events for 3-ready/odd",
    ]
    assert tree(changes) == before


def test_interests_with_no_kind_lists_the_running_batchs_prs_and_nothing_awaited_says_so(
    repo: Path, chantier: Chantier
) -> None:
    assert chantier("interests")[1] == [f"interests of {repo.name}: 0 (nothing awaited)"]
    crs = crs_of("alpha", count=2)
    crs[1]["pr"] = "https://git.example.org/acme/demo/pulls/3"
    write_batch(repo / ".agents", "running", crs)
    plan(repo)
    got = json.loads(chantier("interests", "--json")[1][0])["interests"]
    assert [(i["kind"], i["read_by"], i.get("connector")) for i in got[:2]] == [
        ("pr", "hub", "github"),
        ("pr", "hub", None),
    ]
    assert chantier("interests", "--kind", "pr")[1][1:] == [
        "pr https://github.com/acme/alpha/pull/10 (github): checks, state for batch-01 CR-1",
        "pr https://git.example.org/acme/demo/pulls/3 (no connector): checks, state for "
        "batch-01 CR-2",
    ]


def test_a_provider_that_fails_is_named_and_journal_add_then_writes_nothing(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    # a case the shipped files cannot produce: a file that cannot be read
    changes = plan(repo)
    said = "cannot read 01-intent.md"

    def unreadable(folder: Path) -> str:
        raise OSError(f"{said}\nmore")

    monkeypatch.setattr(issue_refs, "issue_url", unreadable)
    code, out, _ = chantier("interests", "--json")
    assert code == EXIT_PRECONDITION
    assert json.loads(out[0])["errors"] == [{"provider": "issues", "text": said}]
    assert chantier("interests")[:2] == (
        EXIT_PRECONDITION,
        [f"interests of {repo.name}: 0", f"interests: issues not read: {said}"],
    )
    code, _, err = add(chantier, monkeypatch, PAYLOAD)
    assert code == EXIT_PRECONDITION
    assert err == (
        f"error: journal add: the CRs' issue: lines could not be read ({said}): nothing written\n"
    )
    assert not (changes / journal.FILE).exists()


@pytest.mark.parametrize("bom", [False, True])
def test_journal_add_writes_the_event_once(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, bom: bool
) -> None:
    changes = plan(repo)
    data = json.dumps(PAYLOAD).encode("utf-8")
    assert add(chantier, monkeypatch, (b"\xef\xbb\xbf" if bom else b"") + data) == (
        0,
        [WRITTEN],
        "",
    )
    (line,) = lines(changes)
    assert list(line)[:6] == ["v", "seq", "t", "type", "source", "audience"]
    assert (line["v"], line["type"], line["source"], line["audience"]) == (
        2,
        "issue@1",
        "poller",
        ["project"],
    )
    assert (line["wakes"], line["folders"]) == (True, BY)
    assert {k: line[k] for k in PAYLOAD} == PAYLOAD
    again = add(chantier, monkeypatch, {**PAYLOAD, "text": "other words"})
    assert again == (0, ["journal: already there (seq 1)"], "")
    assert len(lines(changes)) == 1


# (what changes in the payload, None removes the key; the exit code; a part of the message)
REFUSED: list[Any] = [
    ({"type": "x"}, EXIT_USAGE, "payload refused: type: Extra inputs are not permitted"),
    ({"cr": "CR-1"}, EXIT_USAGE, "payload refused: cr: Extra inputs are not permitted"),
    ({"source": "hub"}, EXIT_USAGE, "payload refused: source: Extra inputs"),
    ({"audience": ["user"]}, EXIT_USAGE, "payload refused: audience: Extra inputs"),
    ({"folders": ["1-inbox/export"]}, EXIT_USAGE, "payload refused: folders: Extra inputs"),
    ({"ref": None}, EXIT_USAGE, "payload refused: ref: Field required"),
    ({"event": "deleted"}, EXIT_USAGE, "payload refused: event: Input should be"),
    ({"tracker": "bugzilla"}, EXIT_USAGE, "payload refused: tracker: Input should be"),
    ({"at": "yesterday"}, EXIT_USAGE, "payload refused: at: Value error"),
    ({"text": "two\nlines"}, EXIT_USAGE, "payload refused: text: Value error, text is one line"),
    ({"text": ""}, EXIT_USAGE, "payload refused: text: String should have at least 1"),
    ({"text": "x" * 301}, EXIT_USAGE, "payload refused: text: String should have at most 300"),
    ({"wakes": "yes"}, EXIT_USAGE, "payload refused: wakes: Input should be a valid boolean"),
    ({"ref": JIRA + "0"}, EXIT_PRECONDITION, f"{JIRA}0 is no CR's issue"),
    ({"ref": GONE}, EXIT_PRECONDITION, f"{GONE} is no CR's issue"),
]


@pytest.mark.parametrize("case", REFUSED)
def test_journal_add_refuses_what_it_must_and_writes_nothing(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, case: tuple[Any, ...]
) -> None:
    change, code, text = case
    changes = plan(repo)
    payload = {k: v for k, v in {**PAYLOAD, **change}.items() if v is not None}
    got = add(chantier, monkeypatch, payload)
    assert got[0] == code and text in got[2], got
    assert not (changes / journal.FILE).exists()


@pytest.mark.parametrize(
    "case",
    [
        (
            "merged@1",
            PAYLOAD,
            EXIT_PRECONDITION,
            "merged@1 is not written from outside; an outside poller writes",
        ),
        ("issue@1", "not json", EXIT_USAGE, "journal add: --json is not JSON: "),
        ("issue@1", b"\xff\xfe\x00", EXIT_USAGE, "journal add: --json is not JSON: "),
        (
            "issue@1",
            "[1]",
            EXIT_USAGE,
            "payload refused: payload: Input should be a valid dictionary",
        ),
    ],
)
def test_journal_add_refuses_a_wrong_type_and_a_wrong_input(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, case: tuple[Any, ...]
) -> None:
    type_, payload, code, text = case
    changes = plan(repo)
    got = add(chantier, monkeypatch, payload, type_)
    assert got[0] == code and text in got[2], got
    assert not (changes / journal.FILE).exists()

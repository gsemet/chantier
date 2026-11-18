"""`open` with no CR: the batch is born paused, shown as such, joined by `order add`, set running
by the first `take`, and closed with no CR, steered or never steered."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from batch_helpers import FROM_AGENTS_MD, changes, host, open_batch, prepared, record
from conftest import Chantier
from cost_world import msg, slug

from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE

NONE_STEERED = "none: no session steered it"
TWICE, THRICE = 2, 3


def empty(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, *args: object
) -> tuple[int, list[str], str]:
    host(monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "uuid-chief")
    return chantier("open", *FROM_AGENTS_MD, *args)


def events(repo: Path) -> list[dict[str, object]]:
    path = changes(repo) / "4-batch" / "events.jsonl"
    return [json.loads(x) for x in path.read_text("utf-8").splitlines()]


@pytest.mark.parametrize(
    "case",
    [
        (("--direct",), "series"),
        ((), "stack"),
        (("--budget", 9, "--slots", 2), "parallel"),
    ],
)
def test_open_with_no_cr_is_born_paused(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    case: tuple[tuple[object, ...], str],
) -> None:
    flags, mode = case
    code, out, err = empty(repo, chantier, monkeypatch, "--mode", mode, *flags)
    assert code == 0, err
    data = record(repo)
    assert data["status"] == "paused" and data["crs"] == [] and data["paused"]
    assert data["spent_usd"] is None and data["foreman_transcripts"] == []
    assert data["mode"] == mode and data["factory"] is True
    kinds = [(e["kind"], e.get("trigger")) for e in events(repo)]
    assert kinds[-2:] == [("open", None), ("pause", "open, no CR")]
    brief = (changes(repo) / "4-batch" / "brief.md").read_text("utf-8")
    assert "none yet" in brief and "Factory: on." in brief
    assert "no CR, paused" in out[0] and out[0].endswith(", factory")
    assert "`triage <folder> --ready` joins it on its own (factory)" in out[1]
    assert "start the Foreman (direct mode: steer it yourself)" in out[1]
    # a second open, with or without a CR, names the empty batch
    item = prepared(repo, chantier, "Second")
    for more in ((), (str(item),)):
        code, _, err = chantier("open", *more, *FROM_AGENTS_MD)
        assert code == EXIT_PRECONDITION
        assert data["id"] in err


@pytest.mark.parametrize(
    ("flags", "message"),
    [
        (("--release", 1), "order add --note <folder> --release"),
        (("--grant-fixes",), "need --release"),
        (("--autonomous-releases", 1, "--budget", 5), "need --release"),
    ],
)
def test_open_with_no_cr_refuses_what_needs_a_cr(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    flags: tuple[object, ...],
    message: str,
) -> None:
    code, _, err = empty(repo, chantier, monkeypatch, *flags)
    assert code == EXIT_USAGE and message in err
    assert not (changes(repo) / "4-batch" / "batch.json").exists()


def test_an_order_joins_the_empty_batch_and_the_first_take_sets_it_running(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert empty(repo, chantier, monkeypatch)[0] == 0
    batch = record(repo)["id"]
    monkeypatch.setenv("CHANTIER_BATCH", batch)
    status = chantier("status")[1]
    line = next(x for x in status if x.startswith(batch))
    assert "spent none yet" in line and line.endswith("no CR yet") and " factory: on " in line
    assert "no CR yet: `triage <folder> --ready` joins one on its own" in status
    assert "unknown" not in line and "$0.00" not in line
    md = (changes(repo) / "4-batch" / "STATUS.md").read_text("utf-8")
    assert "spent none yet" in md and "- No CR yet." in md
    index = changes(repo) / "STATUS.json"
    before = json.loads(index.read_text("utf-8"))
    assert before["batches"][0]["crs_total"] == 0
    item = prepared(repo, chantier, "First CR")
    code, _out, err = chantier("order", "add", "--note", str(item), "--batch", batch)
    assert code == 0, err
    assert record(repo)["status"] == "paused" and len(record(repo)["crs"]) == 1
    after = json.loads(index.read_text("utf-8"))
    assert after["batches"][0]["crs_total"] == 1 and after["schema"] == before["schema"]
    assert chantier("foreman", "set", "local_foreman_t", "--epoch", 1)[0] == 0
    cr = record(repo)["crs"][0]["id"]
    assert chantier("take", cr, "--epoch", 1)[0] == 0
    assert record(repo)["status"] == "running"


def steer(repo: Path, chantier: Chantier, tmp_path: Path) -> None:
    """Record a steering transcript with one priced call, as the claim does."""
    projects = tmp_path / "claude-projects"
    main = projects / slug(repo) / "uuid-foreman.jsonl"
    main.parent.mkdir(parents=True)
    last = {"role": "assistant", "stop_reason": "end_turn", "content": [{"type": "text"}]}
    ended = {"type": "assistant", "message": last}
    main.write_text(msg("f0", 300) + json.dumps(ended) + "\n")
    (projects / slug(repo) / "uuid-chief.jsonl").write_text(msg("c0", 300))
    assert chantier("foreman", "set", "local_foreman_t", "--epoch", 1)[0] == 0
    assert chantier("foreman", "transcript", "uuid-foreman", "--epoch", 1)[0] == 0


@pytest.mark.parametrize("case", [(True, False), (False, False), (True, True)])
def test_close_of_a_batch_that_never_held_a_cr(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    case: tuple[bool, bool],  # (steered, factory turned off first)
) -> None:
    steered, off = case
    monkeypatch.setenv("CHANTIER_CLAUDE_PROJECTS", str(tmp_path / "claude-projects"))
    assert empty(repo, chantier, monkeypatch)[0] == 0
    batch = record(repo)["id"]
    monkeypatch.setenv("CHANTIER_BATCH", batch)
    if steered:
        steer(repo, chantier, tmp_path)
    if off:  # the done `factory` order is no cause to refuse the close
        assert chantier("order", "factory", "off", "--note", "the user's word")[0] == 0
    code, preview, err = chantier("close")
    assert code == 0, err
    assert "0 CRs move from 3-done" in " ".join(preview)
    code, out, err = chantier("close", "--yes")
    assert code == 0, err
    assert f"closed {batch}" in out[0] and "0 CRs archived" in out[0]
    records = changes(repo) / "5-archives" / "batches"
    done = json.loads((records / f"{batch}.json").read_text("utf-8"))
    text = (records / f"{batch}.md").read_text("utf-8")
    assert done["crs"] == [] and text.count("no CR") >= TWICE  # the Completion and the Retro
    shown = "\n".join([*preview, *out, text])
    if steered:
        assert isinstance(done["cost_usd"], float) and "cost_cause" not in done
        assert NONE_STEERED not in shown
    else:
        assert done["cost_usd"] is None and done["cost_cause"] == NONE_STEERED
        assert done["cost_receipt"]["steering"]["none"] == NONE_STEERED
        assert shown.count(f"Total: {NONE_STEERED}") == THRICE  # preview, done lines, batch-NN.md
        assert "$0.00" not in shown.split("Chief of Staff")[0]


def test_close_still_refuses_a_batch_that_held_a_cr_with_no_steering_transcript(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_batch(repo, chantier, monkeypatch, "Held", seat=False)
    data = record(repo)
    entry = data["crs"][0]
    done = changes(repo) / "4-batch" / "3-done"
    done.mkdir(exist_ok=True)
    folder = changes(repo) / entry["path"]
    folder.rename(done / folder.name)
    entry.update(status="merged", path=f"4-batch/3-done/{folder.name}")
    (changes(repo) / "4-batch" / "batch.json").write_text(
        json.dumps({**data, "status": "paused"}), encoding="utf-8"
    )
    code, _, err = chantier("close")
    assert code != 0 and "no Foreman transcript recorded" in err


@pytest.mark.parametrize("language", ["en", "fr"])
def test_the_board_words_of_a_batch_with_no_cr_are_shipped(language: str) -> None:
    web = Path(__file__).resolve().parents[1] / "src" / "chantier" / "board" / "web" / "js"
    words = (web / "i18n" / f"{language}-batch.js").read_text("utf-8")
    assert "'batch.no_cr_yet'" in words and "'batch.spent_none_yet'" in words
    assert "'batch.no_cr_yet_factory'" in words and "'batch.factory_on'" in words
    for view in ("batch.js", "home-batch.js"):
        text = (web / "views" / view).read_text("utf-8")
        assert "noCrYet(" in text and "batch.no_cr_yet_factory" in text
        assert "steeringFactoryWord(" in text

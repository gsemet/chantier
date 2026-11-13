"""What the batch records say: the line `status` prints, and the Markdown `close` writes
(`batch-NN.md`: the Completion table, the cost and the retro). Where the records live and how
they are read and written is in `chantier.core.batch_records`.
"""

from __future__ import annotations

from chantier.core.batch_records import Rec, open_record
from chantier.core.repo import Repo
from chantier.rails import usd_text
from chantier.status.words import forge_word, shape_word, steering_word

NO_RETRO = "No retro was written."


def last_closed_text(record: Rec | None) -> str:
    """The line `status` prints under its head line."""
    if record is None:
        return "last closed: none"
    crs = record.get("crs") or []
    counts = (
        f"{sum(c['result'] == 'merged' for c in crs)} merged, "
        f"{sum(c['result'] == 'dropped' for c in crs)} dropped"
    )
    when = (
        f", closed {record['closed'][:10]}"
        if record.get("closed")
        else " (backfilled, no close date)"
    )
    cost = record.get("cost_usd")
    price = "" if cost is None else ", " + usd_text(cost, record.get("cost_unpriced"))
    return f"last closed: {record['batch']}{when}, {counts}{price}"


def archive_of(c: Rec) -> str | None:
    """A CR's folder after `close`, relative to the planning folder, in `/` form."""
    path = c.get("path")
    return str(path).replace("\\", "/").removeprefix(".agents/changes/") if path else None


def cr_entry(c: Rec, by_cr: Rec) -> Rec:
    cost = by_cr.get(c["id"])
    return {
        "cr": c["id"],
        "title": c.get("title"),
        "result": "merged" if c["status"] == "merged" else "dropped",
        "archive": archive_of(c),
        "pr": c.get("pr"),
        "rounds": c.get("round"),
        "cost_usd": round(cost[1], 4) if cost else None,
        "cost_unpriced": cost[2] if cost else {},
    }


def close_record(d: Rec, closed: str, total: float, unpriced: Rec, by_cr: Rec) -> Rec:
    """`d` is the batch as it is at `close`, its CRs' `path` already the archives'."""
    crs = sorted(d["crs"], key=lambda c: c.get("order", 0))
    return {
        **open_record(d),
        "state": "closed",
        "closed": closed,
        "cost_usd": round(total, 4),
        "cost_unpriced": unpriced,
        "crs": [cr_entry(c, by_cr) for c in crs],
        "report": f"{d['id']}.md",
    }


def link_to(archive: str | None) -> str:
    """A folder of the planning folder, as a link from `5-archives/batches/`."""
    if not archive:
        return ""
    if archive.startswith("5-archives/"):
        return f"../{archive.removeprefix('5-archives/')}/"
    return f"../../{archive}/"


def table_lines(crs: list[Rec]) -> list[str]:
    """The Completion report's table: CR, subject, result, PR, rounds, cost."""
    forge = forge_word([c.get("pr") for c in crs])
    lines = [
        f"| CR | Subject | Result | {forge} | Rounds | Cost |",
        "| --- | --- | --- | --- | ---: | ---: |",
    ]
    for c in crs:
        cr = f"[{c['cr']}]({link_to(c.get('archive'))})" if c.get("archive") else c["cr"]
        cost = c.get("cost_usd")
        price = "-" if cost is None else usd_text(cost, c.get("cost_unpriced"))
        rounds = "-" if c.get("rounds") is None else c["rounds"]
        title = str(c.get("title") or "-").replace("|", "/")
        lines.append(
            f"| {cr} | {title} | {c['result']} | {c.get('pr') or '-'} | {rounds} | {price} |"
        )
    return lines


def head_line(record: Rec) -> str:
    budget = record.get("budget_usd")
    cost = record.get("cost_usd")
    price = "no cost recorded" if cost is None else usd_text(cost, record.get("cost_unpriced"))
    return (
        f"Opened {record['opened']}, closed {record['closed']}, "
        f"{shape_word(record['mode'])}, steered by {steering_word(record['steering'])}, "
        f"{f'budget ${budget:g}' if budget else 'no budget'}, final cost {price}. "
        f"[{record['batch']}.json]({record['batch']}.json)"
    )


def release_retro_line(repo: Repo, d: Rec) -> str | None:
    """A release CR's own `work/retro.md`, linked where it is archived, never copied."""
    for c in d["crs"]:
        archive = archive_of(c)
        if (
            c.get("kind") == "release"
            and archive
            and (repo.changes / archive / "work" / "retro.md").is_file()
        ):
            return f"Release retro: {link_to(archive)}work/retro.md"
    return None


def close_markdown(record: Rec, summary: list[str], retro: str | None, release: str | None) -> str:
    """`batch-NN.md`: the title, the head line, the Completion table, the cost, the retro."""
    head = [
        f"# {record['batch']}",
        "",
        head_line(record),
        "",
        "## Completion",
        "",
        *table_lines(record["crs"]),
        "",
        "## Cost",
        "",
        *(f"- {s.strip()}" for s in summary),
        "",
        "## Retro",
        "",
    ]
    body = retro if retro else NO_RETRO  # the retro's own bytes, whole
    return (
        "\n".join(head)
        + "\n"
        + body
        + ("" if body.endswith("\n") else "\n")
        + (f"\n{release}\n" if release else "")
    )

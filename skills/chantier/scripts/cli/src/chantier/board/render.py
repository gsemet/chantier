"""What the board draws: the HTML page."""

from __future__ import annotations

import html
import posixpath
import re
from typing import Any
from urllib.parse import quote

from chantier.core.clock import age_minutes
from chantier.core.repo import Repo
from chantier.status.words import forge_word, shape_word, steering_word

REFRESH_S = 30


def esc(text) -> str:
    return html.escape(str(text), quote=True)


def file_link(path: str, label: str) -> str:
    return f'<a href="/file?p={quote(path, safe="/")}">{esc(label)}</a>'


def _url_link(url: str | None, label: str) -> str:
    """A link only for an http(s) URL; anything else is text."""
    if url and re.match(r"https?://", url):
        return f'<a href="{esc(url)}">{esc(label)}</a>'
    return esc(label)


def subject(title: str) -> str:
    return re.sub(r"^﻿?[#\s]*(?:Change Specification:\s*)?", "", title or "").strip()


def _money(usd) -> str:
    return "-" if usd is None else f"${usd:.2f}"


def _ago(ts: str | None) -> str:
    try:
        minutes = age_minutes(ts)
    except ValueError:
        return str(ts)
    if minutes is None:
        return "-"
    minutes = int(minutes)
    return f"{minutes} min ago" if minutes < MINUTES_AS_MINUTES else f"{minutes // 60} h ago"


MINUTES_AS_MINUTES = 120  # past two hours an age is said in hours


def _details(summary: str, body: str, open_: bool = False) -> str:
    opened = " open" if open_ else ""
    return f'<details class="sec"{opened}><summary>{summary}</summary>{body}</details>'


def _cr_row(c: dict[str, Any], batch_folder: str) -> str:
    spec = (
        posixpath.normpath(f"{batch_folder}/{c['specification']}")
        if c.get("specification")
        else None
    )
    title = file_link(spec, subject(c["title"])) if spec else esc(subject(c["title"]))
    word = forge_word([c.get("pr")])
    number = re.search(r"(\d+)/?$", c["pr"]) if c.get("pr") else None
    pr = _url_link(c.get("pr"), f"{word} #{number[1]}" if number else word) if c.get("pr") else "-"
    blocked = f'<div class="blk">{esc(c["blocked"])}</div>' if c.get("blocked") else ""
    waits = (
        f'<div class="muted">waits for {esc(", ".join(c["waits"]))}</div>' if c.get("waits") else ""
    )
    return (
        f'<div class="cr"><span class="dot {esc(c["severity"])}"></span><div class="crbody">'
        f"<div><b>{esc(c['cr'])}</b> {title}</div>"
        f'<div class="muted">{esc(c["label"])} · round {esc(c["round"])} · '
        f"{esc(_money(c['cost_usd']))}"
        f" · {pr}</div>{blocked}{waits}</div></div>"
    )


def _batch_section(
    batch: dict[str, Any], slots: dict[str, Any] | None, events: list[dict[str, Any]]
) -> str:
    priced = batch["priced"]
    spent, budget = batch["spent_usd"], batch["budget_usd"]
    figures = ("unknown" if not priced else f"${spent:.2f}") + (
        f" of ${budget:g}" if budget else ""
    )
    pct = min(100, int(100 * spent / budget)) if priced and budget else 0
    bar = f'<div class="bar"><div style="width:{pct}%"></div></div>' if priced and budget else ""
    asks = batch["asks_unread"]
    facts = [f"spent {figures}"]
    if slots:
        facts.append(f"slots {slots['taken']} taken, {slots['total'] - slots['taken']} free")
    facts.append(
        "heartbeat stopped"
        if batch.get("heartbeat_stopped")
        else f"heartbeat {_ago(batch['heartbeat'])}"
    )
    if batch["orders_pending"]:
        facts.append(f"{batch['orders_pending']} order(s) pending")
    ask = f" · <b>{asks} question(s) waiting</b>" if asks else ""
    rows = (
        "".join(_cr_row(c, batch["folder"]) for c in batch["crs"]) or '<p class="muted">No CR.</p>'
    )
    lines = "".join(
        f'<li><span class="muted">{esc(ev.get("t", "")[11:16])}</span> {esc(ev.get("actor", ""))} '
        f"<b>{esc(ev.get('kind', ''))}</b> {esc(ev.get('cr') or '')}</li>"
        for ev in reversed(events)
    )
    return (
        f'<section><h2>{esc(batch["batch"])} <span class="pill">{esc(batch["state"])}</span>'
        f'<span class="pill">{esc(steering_word(batch["steering"]))}</span>'
        f'<span class="pill">{esc(shape_word(batch["mode"]))}</span></h2>{bar}'
        f'<div class="muted">{esc(" · ".join(facts))}{ask}</div>{rows}'
        f"{_details('Recent events', f'<ul class=ev>{lines}</ul>') if lines else ''}</section>"
    )


def _item_rows(items: list[dict[str, Any]]) -> str:
    return (
        "<ul>"
        + "".join(
            f"<li>{file_link(i['path'], i['item'])}"
            f"{' <span class=pill>' + esc(i['spec']) + '</span>' if i.get('spec') else ''}"
            f'<div class="muted">{esc(i["title"])}</div></li>'
            for i in items
        )
        + "</ul>"
    )


def _past_rows(rows: list[dict[str, Any]]) -> str:
    out = []
    for r in rows:
        pr = f" · {_url_link(r['pr'], forge_word([r['pr']]))}" if r.get("pr") else ""
        out.append(
            f"<li>{file_link(r['path'], r['cr'] or 'CR')} {esc(subject(r['title']))}"
            f'<div class="muted">{esc(r["state"] or "-")} · '
            f"{esc(_money(r['cost_usd']))}{pr}</div></li>"
        )
    return "<ul>" + "".join(out) + "</ul>"


def render_body(data: dict[str, Any]) -> str:
    parts = []
    batch = data["batch"]
    if batch:
        slots = next((b["slots"] for b in data["batches"] if b["batch"] == batch["batch"]), None)
        parts.append(_batch_section(batch, slots, data["events"]))
    else:
        parts.append('<section><p class="muted">No batch.</p></section>')
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in data["backlog"]:
        groups.setdefault(item["priority"], []).append(item)
    for name in ("3-ready", "inbox"):
        if groups.get(name):
            parts.append(
                f"<section><h2>{esc(name)} ({len(groups[name])})</h2>"
                f"{_item_rows(groups[name])}</section>"
            )
    for name in sorted(k for k in groups if k not in ("3-ready", "inbox")):
        parts.append(
            _details(f"<b>Backlog {esc(name)}</b> ({len(groups[name])})", _item_rows(groups[name]))
        )
    for key, label in (("merged", "Merged"), ("trashed", "Trashed")):
        if data[key]:
            parts.append(
                _details(f"<b>{label}</b> ({data[key + '_total']})", _past_rows(data[key]))
            )
    return "".join(parts)


def project_name(repo: Repo) -> str:
    return (repo.project_dir or repo.root).name


def page(body: str, name: str, updated: str = "", title: str = "") -> str:
    foot = (
        (
            f'<p class="muted">Updated {esc(updated)}, refreshes every {REFRESH_S} s · '
            '<a href="/api/status">JSON</a></p>'
        )
        if updated
        else '<p class="muted"><a href="/">Board</a></p>'
    )
    refresh = f'<meta http-equiv="refresh" content="{REFRESH_S}">' if updated else ""
    return (
        f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">{refresh}'
        f"<title>{esc(title or name)}</title><style>{STYLE}</style></head><body>"
        f"<h1>{esc(name)}</h1>{body}{foot}</body></html>"
    )


STYLE = """
:root{color-scheme:light dark;--bg:#fafafa;--card:#fff;--fg:#222;--mut:#777;--line:#e4e4e4}
@media (prefers-color-scheme:dark){
:root{--bg:#151515;--card:#1f1f1f;--fg:#e8e8e8;--mut:#999;--line:#333}}
body{font:15px/1.4 system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:auto;
padding:12px;max-width:760px}
h1{font-size:18px;margin:4px 0 12px}h2{font-size:16px;margin:0 0 8px}
section,.sec{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;
margin-bottom:12px}
.pill{font-size:11px;font-weight:normal;border:1px solid var(--line);border-radius:9px;
padding:1px 7px;margin-left:6px}
.bar{height:6px;background:var(--line);border-radius:3px;margin:6px 0}
.bar div{height:100%;background:#4a7fd4;border-radius:3px}
.cr{display:flex;gap:10px;padding:8px 0;border-top:1px solid var(--line)}.crbody{flex:1;min-width:0}
.dot{width:10px;height:10px;border-radius:50%;margin-top:6px;flex:none;background:#888}
.green{background:#2e9d5b}.yellow{background:#d79b00}.red{background:#d1453b}.grey{background:#888}
.muted{color:var(--mut);font-size:13px}.blk{color:#d1453b;font-size:13px}
a{color:#4a7fd4;text-decoration:none}ul{padding-left:18px;margin:6px 0}li{margin:4px 0}
.ev{list-style:none;padding:0;font-size:13px}summary{cursor:pointer}pre{white-space:pre-wrap;word-wrap:break-word}
"""

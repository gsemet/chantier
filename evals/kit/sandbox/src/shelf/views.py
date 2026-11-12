"""Renders the hand-written templates. Every value is escaped here, once."""
from __future__ import annotations

from html import escape
from pathlib import Path
from string import Template

from shelf import __version__
from shelf.models import STATUSES

TEMPLATES = Path(__file__).parent / "templates"


def _template(name: str) -> Template:
    return Template((TEMPLATES / name).read_text(encoding="utf-8"))


def page(title: str, body: str) -> str:
    return _template("base.html").substitute(title=escape(title), body=body, version=escape(__version__))


def index(items: list[dict], error: str = "", values: dict | None = None) -> str:
    values = values or {}
    rows = "\n".join(
        f'<li><a href="/items/{i["id"]}">{escape(i["title"])}</a> '
        f'<span class="status">{escape(i["status"])}</span> '
        f'<span class="added">{escape(i["added"])}</span></li>'
        for i in items
    ) or '<li class="empty">Nothing on the shelf yet.</li>'
    message = f'<p class="error">{escape(error)}</p>' if error else ""
    body = _template("index.html").substitute(
        rows=rows,
        error=message,
        title_value=escape(values.get("title", ""), quote=True),
        url_value=escape(values.get("url", ""), quote=True),
    )
    return page("shelf", body)


def item(entry: dict) -> str:
    url = entry.get("url") or ""
    link = f'<p><a href="{escape(url, quote=True)}">{escape(url)}</a></p>' if url else ""
    options = "\n".join(
        f'<option value="{s}"{" selected" if s == entry["status"] else ""}>{s}</option>' for s in STATUSES
    )
    body = _template("item.html").substitute(
        id=entry["id"],
        title=escape(entry["title"]),
        link=link,
        status=escape(entry["status"]),
        added=escape(entry["added"]),
        options=options,
    )
    return page(entry["title"], body)


def error(status: int, message: str) -> str:
    body = _template("error.html").substitute(status=status, message=escape(message))
    return page(f"{status} {message}", body)

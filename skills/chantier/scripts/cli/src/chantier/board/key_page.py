"""The page a browser gets when it comes with no good key: a field to paste the key or the whole
link, sent to the board's own `?k=` exchange. The server's, not the web client's: it shows before
any page loads, with `--ui none` too. No script; its one inline style is allowed by its hash."""

from __future__ import annotations

import base64
import hashlib
from html import escape
from urllib.parse import quote

from chantier.board.context import Request
from chantier.board.reply import Reply

STYLE = (
    "body{font:16px/1.5 system-ui,sans-serif;margin:0 auto;max-width:36em;padding:1.5em}"
    "input[type=text]{display:block;width:100%;box-sizing:border-box;font:inherit;padding:.5em;"
    "margin:.5em 0}button{font:inherit;padding:.5em 1.5em}.wrong{color:#a00}.note{color:#555}"
)
STYLE_HASH = "sha256-" + base64.b64encode(hashlib.sha256(STYLE.encode("utf-8")).digest()).decode()
POLICY = (
    f"default-src 'none'; script-src 'none'; style-src '{STYLE_HASH}'; form-action 'self'; "
    "base-uri 'none'; frame-ancestors 'none'"
)
WORDS = {
    "en": {
        "needs": "This board needs the link with its key.",
        "label": "Paste the key or the whole link",
        "open": "Open",
        "note": (
            "The Chief of Staff gives the link (chantier webui prints it). "
            "Nothing is kept but the board's cookie."
        ),
        "wrong": (
            "That key is not this board's: a link of another board opens that board, not this one."
        ),
    },
    "fr": {
        "needs": "Ce board demande le lien avec sa clé.",
        "label": "Colle la clé ou le lien entier",
        "open": "Ouvrir",
        "note": (
            "Le Chief of Staff donne le lien (chantier webui l'affiche). "
            "Rien n'est gardé que le cookie du board."
        ),
        "wrong": (
            "Cette clé n'est pas celle de ce board : le lien d'un autre board ouvre cet "
            "autre board, pas celui-ci."
        ),
    },
}


def is_page_load(req: Request) -> bool:
    """A browser asking for a page: `GET` or `HEAD`, outside `/api/`, accepting `text/html`."""
    return (
        req.method in ("GET", "HEAD")
        and not req.path.startswith("/api/")
        and "text/html" in req.headers.get("accept", "").lower()
    )


def _language(req: Request) -> str:
    first = req.headers.get("accept-language", "").split(",")[0].strip().lower()
    return "fr" if first.split(";")[0].split("-")[0] == "fr" else "en"


def refusal(req: Request, wrong: bool = False) -> Reply:
    """The `401` page with its form; `wrong` adds the line for a `k` that is not this board's."""
    words = WORDS[_language(req)]
    last = req.path.rsplit("/", 1)[-1]  # relative, so a path prefix behind a proxy is kept
    action = "./" + quote(last, safe="")
    hidden = "".join(
        f'<input type="hidden" name="{escape(name)}" value="{escape(value)}">'
        for name, value in req.query.items()
        if name != "k"
    )
    line = f'<p class="wrong">{escape(words["wrong"])}</p>' if wrong else ""
    body = (
        f'<!doctype html><html lang="{_language(req)}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>chantier board</title><style>{STYLE}</style></head><body>"
        f"<h1>chantier board</h1><p>{escape(words['needs'])}</p>{line}"
        f'<form method="get" action="{escape(action)}">'
        f'<label for="k">{escape(words["label"])}</label>'
        '<input type="text" id="k" name="k" autocomplete="off" autocapitalize="off" '
        'spellcheck="false" autofocus>'
        f'{hidden}<button type="submit">{escape(words["open"])}</button></form>'
        f'<p class="note">{escape(words["note"])}</p></body></html>\n'
    )
    return Reply(
        401, body.encode("utf-8"), "text/html; charset=utf-8", {"Content-Security-Policy": POLICY}
    )

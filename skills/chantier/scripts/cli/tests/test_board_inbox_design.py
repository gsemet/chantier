"""The Inbox page's design rules (`clients/web/DESIGN.md`): it reads only and keeps its hides in
the browser."""

from __future__ import annotations

import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "src" / "chantier" / "clients" / "web"
MODEL_AND_VIEW = ("views/inbox.js", "model/inbox.js")


def _web(*parts: str) -> str:
    return WEB.joinpath(*parts).read_text(encoding="utf-8")


def _inbox_scripts() -> dict[str, str]:
    js = WEB / "js"
    files = [
        js / "views" / "inbox.js",
        js / "model" / "inbox.js",
        *sorted((js / "inbox").glob("*.js")),
    ]
    return {f.relative_to(js).as_posix(): f.read_text(encoding="utf-8") for f in files}


def test_the_inbox_is_the_second_view_and_reads_only() -> None:
    registry = _web("js", "views", "registry.js")
    ids = re.findall(r"\bid: '(\w+)'", registry)
    assert ids[1] == "inbox"
    entry = registry.split("id: 'inbox'", 1)[1].split("},", 1)[0]
    assert all(key in entry for key in ("overview:", "count:", "countAll:"))
    scripts = _inbox_scripts()
    assert len(scripts) > len(MODEL_AND_VIEW)
    for name, text in scripts.items():
        assert not re.search(r"core/(transport|api)\.js|from '\.\./api/", text), name
        assert "localStorage" not in text, name  # `core/store.js` is the only writer of it
    pure = scripts["model/inbox.js"]  # pure: no page, no store, no words
    assert not [w for w in ("document", "window", "localStorage", "Notification") if w in pure]
    assert re.findall(r"from '([^']+)'", pure) in ([], ["../core/format.js"])
    cards = scripts["inbox/entry.js"]
    assert "from '../ui/card.js'" in cards and 'class="card' not in cards
    assert re.findall(r"attrs: (\S+)", cards) == ['html`data-key="inbox-${e.id}"`,']
    chip = _web("css", "components", "chip.css")
    states = [m.start() for m in re.finditer(r"\.tag\.st\.(?!off)\w+", chip)]
    assert 0 <= max(states) < chip.index(".tag.st.off")

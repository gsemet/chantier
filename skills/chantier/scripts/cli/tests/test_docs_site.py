"""The documentation site: every image of docs/ is shown by a page."""

import re

from conftest import PLUGIN_ROOT
from docs_site import site_pages


def test_every_docs_image_is_shown_by_a_site_page() -> None:
    docs = PLUGIN_ROOT / "docs"
    images = {*docs.glob("*.svg"), *docs.glob("*.png"), *(docs / "web-board").glob("*.png")}
    conf = (docs / "conf.py").read_text(encoding="utf-8")
    if re.search(r'^html_logo = "logo\.svg"$', conf, re.M):
        images.discard(docs / "logo.svg")
    named = set()
    for page in site_pages():
        text = page.read_text(encoding="utf-8")
        refs = re.findall(r"!\[[^\]]*\]\(([^)\s]+)", text)
        refs += re.findall(r"^(?::{3,}|`{3,})\{(?:image|figure)\}\s+(\S+)", text, re.M)
        named |= {(page.parent / ref).resolve() for ref in refs if not ref.startswith("http")}
    unnamed = sorted(p.relative_to(docs).as_posix() for p in images if p.resolve() not in named)
    assert unnamed == [], f"images no site page shows: {unnamed}"

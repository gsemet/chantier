"""The documentation site: every image of docs/ is shown by a page."""

import re

from conftest import PLUGIN_ROOT, SKILL
from docs_site import repo_file_of, site_pages

from chantier.commands.rules import linked


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


def test_skill_and_references_links_resolve() -> None:
    for page in [
        *(PLUGIN_ROOT / "skills").glob("*/SKILL.md"),
        *(SKILL / "references").glob("*.md"),
        PLUGIN_ROOT / "README.md",
        *site_pages(),
    ]:
        for link in re.findall(r"\]\(([^)#\s]+)", page.read_text(encoding="utf-8")):
            if not link.startswith("http"):
                assert (page.parent / link).exists(), f"{page.name}: {link}"
            elif (target := repo_file_of(link)) is not None:
                assert target.exists(), f"{page.name}: {link}"


def test_the_docs_style_guide_is_wired_in_and_stays_out_of_the_rules() -> None:
    assert (PLUGIN_ROOT / "docs" / "STYLE.md").is_file()
    for name in ("AGENTS.md", "CONTRIBUTING.md"):
        text = (PLUGIN_ROOT / name).read_text(encoding="utf-8")
        assert "`docs/STYLE.md`" in text, f"{name} does not name `docs/STYLE.md`"
    seen = [(PLUGIN_ROOT / "AGENTS.md").resolve()]
    linked(seen[0], PLUGIN_ROOT.resolve(), seen, 2)
    assert not [p for p in seen if p.as_posix().endswith("docs/STYLE.md")]

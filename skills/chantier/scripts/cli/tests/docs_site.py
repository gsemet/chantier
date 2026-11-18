"""The documentation site's pages and links, as the shipped files hold them."""

from pathlib import Path

from conftest import PLUGIN_ROOT

SITE_BASE = "https://chantier.readthedocs.io/en/latest/"
REPO_BLOB = "https://github.com/gsemet/chantier/blob/main/"
REPO_TREE = "https://github.com/gsemet/chantier/tree/main/"


def site_pages() -> list[Path]:
    """The pages of the documentation site: docs/**/*.md minus what the build leaves out."""
    docs = PLUGIN_ROOT / "docs"
    skipped = {"demo", "release-notes", "_build"}
    return [
        page
        for page in docs.rglob("*.md")
        if not skipped & set(page.relative_to(docs).parts) and not page.name.endswith("-texts.md")
    ]


def repo_file_of(link: str) -> Path | None:
    """The repository file a site or GitHub link names, None for any other link."""
    if link.startswith(SITE_BASE) or link == SITE_BASE.rstrip("/"):
        rest = link.removeprefix(SITE_BASE).split("?")[0]
        if rest in ("", "index.html"):
            return PLUGIN_ROOT / "docs" / "index.md"
        if rest.endswith("/"):
            return PLUGIN_ROOT / "docs" / rest / "index.md"
        return PLUGIN_ROOT / "docs" / f"{rest.removesuffix('.html')}.md"
    for base in (REPO_BLOB, REPO_TREE):
        if link.startswith(base):
            return PLUGIN_ROOT / link.removeprefix(base)
    return None

"""The item, its statuses, and the validation of a new item."""
from __future__ import annotations

STATUSES = ("to-read", "reading", "done")
DEFAULT_STATUS = "to-read"
MAX_TITLE = 200


def validate_new(title: str, url: str) -> tuple[dict, str | None]:
    """Return the cleaned values of a new item and an error message (None when valid)."""
    title = (title or "").strip()
    url = (url or "").strip()
    clean = {"title": title, "url": url}
    if not title:
        return clean, "The title is required."
    if len(title) > MAX_TITLE:
        return clean, f"The title is at most {MAX_TITLE} characters."
    if url and not url.startswith(("http://", "https://")):
        return clean, "The link must start with http:// or https://."
    return clean, None

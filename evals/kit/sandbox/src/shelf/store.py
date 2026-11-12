"""The items, kept in a JSON file: the path in SHELF_DATA, else shelf.json here."""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

from shelf.models import DEFAULT_STATUS


def data_path() -> Path:
    return Path(os.environ.get("SHELF_DATA") or "shelf.json")


def load() -> list[dict]:
    path = data_path()
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save(items: list[dict]) -> None:
    path = data_path()
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(items, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def add(title: str, url: str = "") -> dict:
    items = load()
    item = {
        "id": max((i["id"] for i in items), default=0) + 1,
        "title": title,
        "url": url,
        "status": DEFAULT_STATUS,
        "added": datetime.date.today().isoformat(),
    }
    save([*items, item])
    return item


def get(item_id: int) -> dict | None:
    return next((i for i in load() if i["id"] == item_id), None)


def set_status(item_id: int, status: str) -> dict | None:
    items = load()
    item = next((i for i in items if i["id"] == item_id), None)
    if item is None:
        return None
    item["status"] = status
    save(items)
    return item

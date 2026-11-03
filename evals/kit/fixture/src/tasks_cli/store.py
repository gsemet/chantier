"""Tasks are kept in one JSON file: $TASKS_FILE, else tasks.json in the current folder."""
from __future__ import annotations

import json
import os
from pathlib import Path


def path() -> Path:
    return Path(os.environ.get("TASKS_FILE", "tasks.json"))


def load() -> list[dict]:
    p = path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def save(tasks: list[dict]) -> None:
    path().write_text(json.dumps(tasks, indent=2) + "\n", encoding="utf-8")


def next_id(tasks: list[dict]) -> int:
    return max((t["id"] for t in tasks), default=0) + 1

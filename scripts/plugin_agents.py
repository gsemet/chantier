#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Write the agent files the Claude Code plugin ships (`agents/`), from the skill's templates.

    uv run --script scripts/plugin_agents.py           # write agents/*.md
    uv run --script scripts/plugin_agents.py --check   # exit 1 if agents/ is out of date

They carry the skill's base model list only: a user or project override makes `chantier setup`
install that role's agent in the project instead.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "chantier"
sys.path.insert(0, str(SKILL / "scripts" / "cli" / "src"))
os.environ["CHANTIER_SKILL_DIR"] = str(SKILL)

from chantier.commands import render_plugin_agents  # noqa: E402

AGENTS = ROOT / "agents"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only report files out of date")
    args = parser.parse_args()
    wanted = render_plugin_agents()
    stale = [name for name, text in wanted.items()
             if not (AGENTS / f"{name}.md").exists()
             or (AGENTS / f"{name}.md").read_text(encoding="utf-8") != text]
    extra = sorted(p.name for p in AGENTS.glob("*.md") if p.stem not in wanted) \
        if AGENTS.exists() else []
    if args.check:
        for name in stale:
            print(f"out of date: agents/{name}.md")
        for name in extra:
            print(f"not a chantier role: agents/{name}")
        return 1 if stale or extra else 0
    AGENTS.mkdir(exist_ok=True)
    for name in stale:
        (AGENTS / f"{name}.md").write_text(wanted[name], encoding="utf-8", newline="\n")
        print(f"wrote agents/{name}.md")
    for name in extra:
        (AGENTS / name).unlink()
        print(f"removed agents/{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

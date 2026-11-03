#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Write the agent files the plugin ships, from the skill's templates and base model lists.

    uv run --script scripts/plugin_agents.py           # write them
    uv run --script scripts/plugin_agents.py --check   # exit 1 if one is out of date

Claude Code reads `agents/<role>.md`; GitHub Copilot reads
`com.github.copilot/agents/<role>.agent.md`. Each host gets its own tools and model fields.
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

from chantier.commands import COPILOT_PLUGIN_AGENTS, render_plugin_agents  # noqa: E402

# host: (folder, file suffix)
HOSTS = {"claude": ("agents", ".md"), "copilot": (COPILOT_PLUGIN_AGENTS, ".agent.md")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only report files out of date")
    args = parser.parse_args()
    bad = 0
    for host, (folder, suffix) in HOSTS.items():
        wanted = {f"{name}{suffix}": text for name, text in render_plugin_agents(host).items()}
        out = ROOT / folder
        stale = [f for f, text in wanted.items()
                 if not (out / f).exists() or (out / f).read_text(encoding="utf-8") != text]
        extra = sorted(p.name for p in out.glob("*.md") if p.name not in wanted) \
            if out.exists() else []
        if args.check:
            for f in stale:
                print(f"out of date: {folder}/{f}")
            for f in extra:
                print(f"not a chantier role: {folder}/{f}")
            bad += len(stale) + len(extra)
            continue
        out.mkdir(parents=True, exist_ok=True)
        for f in stale:
            (out / f).write_text(wanted[f], encoding="utf-8", newline="\n")
            print(f"wrote {folder}/{f}")
        for f in extra:
            (out / f).unlink()
            print(f"removed {folder}/{f}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

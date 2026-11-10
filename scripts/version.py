#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Set chantier's version in every file that carries it, in one go.

    uv run --script scripts/version.py show
    uv run --script scripts/version.py set 1.2.3
    uv run --script scripts/version.py bump [patch|minor|major]

The current version is read from the CLI (`__version__`); every other file must agree with it,
or nothing is written.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "chantier"
CLI = SKILL / "scripts" / "cli"
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
V = r"(\d+\.\d+\.\d+)"

# (file, pattern with one group holding the version, expected number of matches)
TARGETS: list[tuple[Path, str, int]] = [
    (CLI / "src" / "chantier" / "__init__.py", rf'^__version__ = "{V}"$', 1),
    (CLI / "pyproject.toml", rf'^version = "{V}"$', 1),
    (CLI / "uv.lock", rf'^name = "chantier"\nversion = "{V}"$', 1),
    (SKILL / "SKILL.md", rf"^chantier-version: {V}$", 1),
    (ROOT / "skills" / "chief-of-staff" / "SKILL.md", rf"^chantier-version: {V}$", 1),
    (ROOT / "skills" / "griller" / "SKILL.md", rf"^chantier-version: {V}$", 1),
    (ROOT / ".github" / "plugin" / "plugin.json", rf'^  "version": "{V}",$', 1),
    (ROOT / ".claude-plugin" / "plugin.json", rf'^  "version": "{V}",$', 1),
    (ROOT / ".claude-plugin" / "marketplace.json", rf'^      "version": "{V}"$', 1),
    (ROOT / ".github" / "plugin" / "marketplace.json", rf'^ +"version": "{V}",?$', 2),
]
TARGETS += [(p, rf"^# chantier-agent: {V}$", 1) for p in sorted((ROOT / "agents").glob("*.md"))]
TARGETS += [(p, rf"^# chantier-agent: {V}$", 1)
            for p in sorted((ROOT / "com.github.copilot" / "agents").glob("*.agent.md"))]


def current() -> str:
    text = TARGETS[0][0].read_text(encoding="utf-8")
    return re.search(TARGETS[0][1], text, re.M).group(1)


def bump(version: str, part: str) -> str:
    major, minor, patch = map(int, version.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def apply(old: str, new: str) -> list[str]:
    """Check every target first, then write them all; returns the errors, if any."""
    errors, edits = [], []
    for path, pattern, count in TARGETS:
        rel = path.relative_to(ROOT).as_posix()
        if not path.exists():
            errors.append(f"missing {rel}")
            continue
        text = path.read_bytes().decode("utf-8")
        eol = "\r\n" if "\r\n" in text else "\n"
        text = text.replace("\r\n", "\n")
        found = list(re.finditer(pattern, text, re.M))
        if len(found) != count:
            errors.append(f"{rel}: expected {count} version line(s), found {len(found)}")
            continue
        wrong = [m.group(1) for m in found if m.group(1) != old]
        if wrong:
            errors.append(f"{rel}: has {', '.join(wrong)}, not {old}")
            continue
        for m in reversed(found):
            s, e = m.span(1)
            text = text[:s] + new + text[e:]
        edits.append((path, text.replace("\n", eol)))
    if errors:
        return errors
    for path, text in edits:
        path.write_bytes(text.encode("utf-8"))
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show", help="print the current version")
    s = sub.add_parser("set", help="set an exact version")
    s.add_argument("version")
    b = sub.add_parser("bump", help="bump one part of the version")
    b.add_argument("part", nargs="?", default="patch", choices=["patch", "minor", "major"])
    args = parser.parse_args()

    old = current()
    if args.cmd == "show":
        print(old)
        return 0
    new = args.version if args.cmd == "set" else bump(old, args.part)
    if not SEMVER.match(new):
        print(f"error: `{new}` is not MAJOR.MINOR.PATCH", file=sys.stderr)
        return 1
    if new == old:
        print(f"already {old}")
        return 0
    errors = apply(old, new)
    if errors:
        print("error: nothing written", file=sys.stderr)
        for line in errors:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(f"{old} -> {new} in {len(TARGETS)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())

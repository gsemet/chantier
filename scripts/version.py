#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Set chantier's version in every file that carries it, in one go.

    uv run --script scripts/version.py show
    uv run --script scripts/version.py set 1.2.3
    uv run --script scripts/version.py bump [patch|minor|major]
    uv run --script scripts/version.py ff-main

The current version is read from the CLI (`__version__`); every other file must agree with it,
or nothing is written.
"""

from __future__ import annotations

import argparse
import re
import subprocess
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
    (ROOT / "pyproject.toml", rf'^version = "{V}"$', 1),
    (ROOT / "uv.lock", rf'^name = "chantier"\nversion = "{V}"$', 1),
    (SKILL / "SKILL.md", rf"^chantier-version: {V}$", 1),
    (ROOT / "skills" / "chief-of-staff" / "SKILL.md", rf"^chantier-version: {V}$", 1),
    (ROOT / "skills" / "griller" / "SKILL.md", rf"^chantier-version: {V}$", 1),
    (ROOT / "skills" / "status" / "SKILL.md", rf"^chantier-version: {V}$", 1),
    (ROOT / ".github" / "plugin" / "plugin.json", rf'^  "version": "{V}",$', 1),
    (ROOT / ".claude-plugin" / "plugin.json", rf'^  "version": "{V}",$', 1),
    (ROOT / ".claude-plugin" / "marketplace.json", rf'^      "version": "{V}"$', 1),
    (ROOT / ".github" / "plugin" / "marketplace.json", rf'^ +"version": "{V}",?$', 2),
]
TARGETS += [(p, rf"^# chantier-agent: {V}$", 1) for p in sorted((ROOT / "agents").glob("*.md"))]
TARGETS += [
    (p, rf"^# chantier-agent: {V}$", 1)
    for p in sorted((ROOT / "com.github.copilot" / "agents").glob("*.agent.md"))
]


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


def check_tag(version: str) -> int:
    subject = subprocess.run(
        ["git", "log", "-1", "--format=%s", "origin/main"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    ).stdout.strip()
    expected = f"release: v{version}"
    if subject != expected:
        print(f'just tag: origin/main is "{subject}", expected "{expected}"', file=sys.stderr)
        return 1
    return 0


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _first(text: str) -> str:
    lines = text.strip().splitlines()
    return lines[0] if lines else "no message"


def ff_main(root: Path = ROOT) -> int:
    branch = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    if branch.returncode != 0:
        print(
            "just tag: detached HEAD, not main: run just tag from the main checkout, on main",
            file=sys.stderr,
        )
        return 1
    if branch.stdout.strip() != "main":
        print(
            f"just tag: the checkout is on {branch.stdout.strip()}, not main: "
            "run just tag from the main checkout, on main",
            file=sys.stderr,
        )
        return 1
    status = _git(root, "status", "--porcelain", "--untracked-files=no")
    if status.stdout.strip():
        paths = [line[3:] for line in status.stdout.splitlines()[:3]]
        print(
            f"just tag: the main checkout has tracked changes ({', '.join(paths)}): "
            "commit or set them aside yourself, then run just tag again",
            file=sys.stderr,
        )
        return 1
    fetch = _git(root, "fetch", "origin", "main")
    if fetch.returncode != 0:
        print(f"just tag: fetch failed: {_first(fetch.stderr)}", file=sys.stderr)
        return 1
    before = _git(root, "rev-parse", "HEAD").stdout.strip()
    merge = _git(root, "merge", "--ff-only", "--no-overwrite-ignore", "origin/main")
    if merge.returncode != 0:
        reason = _first(merge.stderr or merge.stdout)
        print(
            f"just tag: main cannot fast-forward to origin/main ({reason}): nothing was "
            "changed; settle main by hand, then run just tag again",
            file=sys.stderr,
        )
        return 1
    after = _git(root, "rev-parse", "HEAD").stdout.strip()
    short = after[:7]
    line = (
        f"main checkout: already at {short}"
        if before == after
        else f"main checkout: fast-forwarded to {short}"
    )
    if _git(root, "diff", "--quiet", before, "HEAD", "--", "uv.lock").returncode == 1:
        line += "; uv.lock changed: sync pending"
    print(line)
    return 0


def write(old: str, new: str) -> int:
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show", help="print the current version")
    sub.add_parser("check-tag", help="succeed only if origin/main's head is `release: v<version>`")
    sub.add_parser(
        "ff-main",
        help="fast-forward the main checkout to origin/main; refuse when not on main, "
        "with tracked changes, or when it is not a fast-forward",
    )
    s = sub.add_parser("set", help="set an exact version")
    s.add_argument("version")
    b = sub.add_parser("bump", help="bump one part of the version")
    b.add_argument("part", nargs="?", default="patch", choices=["patch", "minor", "major"])
    args = parser.parse_args()

    if args.cmd == "ff-main":
        return ff_main()
    old = current()
    if args.cmd == "show":
        print(old)
        return 0
    if args.cmd == "check-tag":
        return check_tag(old)
    new = args.version if args.cmd == "set" else bump(old, args.part)
    return write(old, new)


if __name__ == "__main__":
    sys.exit(main())

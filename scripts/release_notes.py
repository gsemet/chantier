#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Check the reviewed release notes and prepare them for the GitHub release.

    uv run --script scripts/release_notes.py --check
    uv run --script scripts/release_notes.py --prepare vX.Y.Z [--output FILE] [--assets DIR]
    uv run --script scripts/release_notes.py --scan FILE...

The notes, the announcement thread and their images live in
`docs/release-notes/YYYY-MM-DD-vX.Y.Z/`. See docs/release-process.md.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTES_ROOT = ROOT / "docs" / "release-notes"
NOTES_FILE = "release-notes.md"
TWEET_FILE = "tweet.md"
VERSION_FILE = ROOT / "skills" / "chantier" / "scripts" / "cli" / "src" / "chantier" / "__init__.py"
FIRST_NOTES_VERSION = (0, 8, 0)
REPO = "https://github.com/gsemet/chantier"
RELEASE_ASSETS = f"{REPO}/releases/download"
INSTALL_LINK = f"{REPO}#install"
TAG = re.compile(r"v((0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*))")
IMAGE = re.compile(r'!\[[^\]]*\]\(([^)\s]+)[^)]*\)|<img\b[^>]*\bsrc="([^"]+)"')
POST = re.compile(r"^## (\S+)\s*$", re.MULTILINE)
IMAGE_LINE = re.compile(r"^Image:\s*(.+?)\s*$", re.MULTILINE)

# Fixed patterns: the same on every machine.
FIXED = [
    ("home path", re.compile(r"[A-Za-z]:[\\/]+Users[\\/]|/Users/[^/\s]|/home/[^/\s]")),
    ("email", re.compile(r"[\w.+-]+@(?!example\.(?:com|org)\b)[\w-]+(?:\.[\w-]+)+")),
    ("uuid", re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}(?![0-9a-fA-F])")),
]


def current_version() -> str:
    """The CLI's version, the line scripts/version.py reads."""
    text = VERSION_FILE.read_text(encoding="utf-8")
    match = re.search(r'^__version__ = "(\d+\.\d+\.\d+)"$', text, re.MULTILINE)
    if not match:
        raise ValueError(f"No __version__ in {VERSION_FILE}")
    return match.group(1)


def notes_file(version: str) -> Path:
    """Find the one notes file of a version, in its dated folder."""
    found = sorted(NOTES_ROOT.glob(f"[0-9]*-[0-9]*-[0-9]*-v{version}/{NOTES_FILE}"))
    if len(found) != 1:
        raise ValueError(
            f"Expected one docs/release-notes/YYYY-MM-DD-v{version}/{NOTES_FILE}, "
            f"found {len(found)}"
        )
    return found[0]


def images(text: str) -> list[str]:
    """The source of every image of a text, in order."""
    return [match.group(1) or match.group(2) for match in IMAGE.finditer(text)]


def local_image(source: str, folder: Path) -> None:
    """Reject an image that is not a bare file name present in the folder."""
    if "/" in source or "\\" in source or not (folder / source).is_file():
        raise ValueError(f"Image next to the notes expected, found: {source}")


def validate_notes(notes: str, folder: Path, version: str) -> None:
    """Reject notes of another version and images that the release cannot attach."""
    title = notes.strip().splitlines()[0] if notes.strip() else ""
    minor = ".".join(version.split(".")[:2])
    if not title.startswith(("# ", "<h1")) or minor not in title:
        raise ValueError(f"The notes must start with a title naming version {minor}")
    for source in images(notes):
        local_image(source, folder)


def tweet_image(tweet: str, folder: Path) -> str:
    """The one image of the thread; checks the posts on the way."""
    version_posts = POST.findall(tweet)
    if version_posts != ["1/", "2/", "3/"]:
        raise ValueError(f"{TWEET_FILE} must hold ## 1/, ## 2/ and ## 3/ in order, found {version_posts}")
    parts = POST.split(tweet)
    # parts: [head, name1, body1, name2, body2, name3, body3]
    bodies = {parts[i]: parts[i + 1] for i in range(1, len(parts), 2)}
    lines = IMAGE_LINE.findall(tweet)
    if len(lines) != 1 or not IMAGE_LINE.search(bodies["1/"]):
        raise ValueError(f"{TWEET_FILE} must hold exactly one Image: line, in post 1")
    local_image(lines[0], folder)
    return lines[0]


def validate_tweet(tweet: str, folder: Path, version: str) -> str:
    """Check the thread's shape and links; return its image."""
    image = tweet_image(tweet, folder)
    bodies = dict(zip(*[iter(POST.split(tweet)[1:])] * 2))
    if f"{REPO}/releases/tag/v{version}" not in bodies["2/"]:
        raise ValueError(f"Post 2 of {TWEET_FILE} must link {REPO}/releases/tag/v{version}")
    if INSTALL_LINK not in bodies["3/"]:
        raise ValueError(f"Post 3 of {TWEET_FILE} must link {INSTALL_LINK}")
    return image


def git_value(key: str) -> str:
    """A git config value, or an empty string."""
    try:
        done = subprocess.run(
            ["git", "config", key], capture_output=True, text=True, encoding="utf-8", check=False
        )
    except OSError:
        return ""
    return done.stdout.strip()


def local_patterns() -> list[tuple[str, re.Pattern[str]]]:
    """Values proper to this machine: the home folder's name, the git identity."""
    values = [("home folder name", Path.home().name)]
    values += [("git user name", git_value("user.name")), ("git user email", git_value("user.email"))]
    return [
        (kind, re.compile(rf"(?<!\w){re.escape(value)}(?!\w)", re.IGNORECASE))
        for kind, value in values
        if len(value) >= 3
    ]


def scan_text(text: str, name: str, patterns: list[tuple[str, re.Pattern[str]]]) -> list[str]:
    """One `name:line: kind` per match."""
    hits = []
    for number, line in enumerate(text.splitlines(), 1):
        for kind, pattern in patterns:
            if pattern.search(line):
                hits.append(f"{name}:{number}: {kind}")
    return hits


def check() -> None:
    """Fail when the current version has no valid notes."""
    version = current_version()
    if tuple(int(part) for part in version.split(".")) < FIRST_NOTES_VERSION:
        print("release-notes: none needed before 0.8.0")
        return
    path = notes_file(version)
    folder = path.parent
    notes = path.read_text(encoding="utf-8")
    validate_notes(notes, folder, version)
    tweet_path = folder / TWEET_FILE
    if not tweet_path.is_file():
        raise ValueError(f"Missing {tweet_path.relative_to(ROOT).as_posix()}")
    tweet = tweet_path.read_text(encoding="utf-8")
    validate_tweet(tweet, folder, version)
    hits = scan_text(notes, NOTES_FILE, FIXED) + scan_text(tweet, TWEET_FILE, FIXED)
    if hits:
        raise ValueError("Private data in the release text: " + ", ".join(hits))
    print(f"release-notes: {path.relative_to(ROOT).as_posix()} ok")


def public_notes(notes: str, tag: str) -> str:
    """Point the images of the notes to the assets of the release."""

    def attached(match: re.Match[str]) -> str:
        source = match.group(1) or match.group(2)
        return match.group(0).replace(source, f"{RELEASE_ASSETS}/{tag}/{source}")

    return IMAGE.sub(attached, notes)


def prepare(tag: str, output: Path, assets: Path) -> None:
    """Write the notes of a tag for the release, copy the images to attach and list them."""
    version = TAG.fullmatch(tag)
    if not version:
        raise ValueError("Expected a stable vX.Y.Z tag")
    number = version.group(1)
    path = notes_file(number)
    folder = path.parent
    notes = path.read_text(encoding="utf-8")
    validate_notes(notes, folder, number)
    tweet_path = folder / TWEET_FILE
    if not tweet_path.is_file():
        raise ValueError(f"Missing {tweet_path.relative_to(ROOT).as_posix()}")
    thread_image = validate_tweet(tweet_path.read_text(encoding="utf-8"), folder, number)
    assets.mkdir(parents=True, exist_ok=True)
    sources = list(dict.fromkeys(images(notes) + [thread_image]))
    for source in sources:
        shutil.copy(folder / source, assets / source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(public_notes(notes, tag), encoding="utf-8", newline="\n")
    for source in sources:
        print(assets / source)


def scan(files: list[Path]) -> int:
    """List private data in files; 1 when there is any."""
    patterns = FIXED + local_patterns()
    hits: list[str] = []
    for file in files:
        hits += scan_text(file.read_text(encoding="utf-8", errors="replace"), str(file), patterns)
    for hit in hits:
        print(hit)
    return 1 if hits else 0


def main() -> int:
    """Run exactly one mode."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--prepare", metavar="TAG")
    parser.add_argument("--scan", nargs="+", type=Path, metavar="FILE")
    parser.add_argument("--output", type=Path, default=Path("release-notes.md"))
    parser.add_argument("--assets", type=Path, default=Path("release-assets"))
    arguments = parser.parse_args()
    if [bool(arguments.check), bool(arguments.prepare), bool(arguments.scan)].count(True) != 1:
        parser.error("Use exactly one of --check, --prepare, --scan")
    try:
        if arguments.scan:
            return scan(arguments.scan)
        if arguments.check:
            check()
        else:
            prepare(arguments.prepare, arguments.output, arguments.assets)
    except (ValueError, OSError) as error:
        print(f"release-notes: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

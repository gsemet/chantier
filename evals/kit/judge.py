"""The judge: hidden tests on a sandbox PR's head, and a release judged by what the sandbox shows.

    uv run --no-project python evals/kit/judge.py <repository> <ref> <slug> [<slug> ...]
    uv run --no-project python evals/kit/judge.py --release <version> <repository> [<slug> ...]

`<repository>` is a git URL or a local path; `<ref>` a SHA-1 or a ref name.

A feature judge clones the repository into a temporary folder, copies the hidden tests of each slug
(`kit/sandbox-judge/<slug>/test_*.py`, never pushed to the sandbox) into the clone's `tests/`, and
runs them, then the project's whole suite, on `<ref>`. A release judge checks the tag
`v<version>`: it is on `main`, the version is in the three places, the heavy check passes, the
hidden tests of the slugs pass at the tag, and, on the sandbox, the GitHub release holds the notes.

Exit codes: 0 pass, 1 fail, 2 usage, 4 not run (the clone, the fetch, the ref or `uv` failed; the
tool's text is printed). Standard library only; POSIX and Windows.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sandbox  # noqa: E402  (the sandbox's constants and its folder removal)

HIDDEN = HERE / "sandbox-judge"
TIMEOUT = 600  # seconds, for each pytest run and for the heavy check
PASS, FAIL, USAGE, NOT_RUN = 0, 1, 2, 4
SUMMARY = re.compile(r"\b\d+ (?:passed|failed|errors?|skipped|deselected|xfailed|xpassed)\b|no tests ran")


class NotRun(Exception):
    """The judge could not run: the reason is the tool's own text."""


def git_env() -> dict:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def project_env() -> dict:
    """The environment of the project's runs: no virtual environment of the caller's, no data file."""
    env = dict(os.environ)
    for name in ("VIRTUAL_ENV", "SHELF_DATA"):
        env.pop(name, None)
    return env


def run(cmd, cwd=None, env=None, timeout=300) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except FileNotFoundError:
        raise NotRun(f"`{cmd[0]}` is not installed or not on the PATH") from None
    except subprocess.TimeoutExpired:
        raise NotRun(f"`{' '.join(cmd)}` did not end within {timeout // 60} minutes") from None


def must(cmd, cwd=None, timeout=300) -> str:
    done = run(cmd, cwd=cwd, env=git_env(), timeout=timeout)
    if done.returncode != 0:
        text = (done.stderr or done.stdout).strip()
        raise NotRun(f"`{' '.join(cmd)}` failed ({done.returncode}): {text}")
    return done.stdout


def tail(text: str) -> str:
    lines = [x.strip() for x in text.strip().splitlines() if x.strip()]
    return lines[-1] if lines else ""


def hidden_files(slugs: list[str]) -> list[Path]:
    """The hidden test files of the slugs; a slug with no folder is not run."""
    files = []
    for slug in slugs:
        found = sorted((HIDDEN / slug).glob("test_*.py")) if re.fullmatch(r"[a-z0-9-]+", slug) else []
        if not found:
            raise NotRun(f"no hidden test for {slug}")
        files += found
    return files


def clone(repository: str, holder: Path) -> Path:
    """A clone with no checkout, with the PR heads of a forge fetched too: a PR's head stays
    reachable after its branch is deleted (on a repository with no such refs it fetches nothing)."""
    repo = holder / "repo"
    must(["git", "-c", "core.autocrlf=false", "clone", "--quiet", "--no-checkout", repository,
          str(repo)], timeout=600)
    must(["git", "config", "core.autocrlf", "false"], cwd=repo)
    must(["git", "fetch", "--quiet", "origin", "+refs/pull/*/head:refs/remotes/origin/pull/*"],
         cwd=repo, timeout=600)
    return repo


def checkout(repo: Path, ref: str) -> str:
    """Detach at the ref (a branch of the origin, a tag or a SHA-1); return its full SHA-1."""
    for name in (f"origin/{ref}", ref):
        done = run(["git", "rev-parse", "--verify", "--quiet", f"{name}^{{commit}}"], cwd=repo,
                   env=git_env())
        if done.returncode == 0:
            sha = done.stdout.strip()
            must(["git", "checkout", "--quiet", "--detach", sha], cwd=repo)
            return sha
    raise NotRun(f"head {ref} not found on the origin")


def pytest(repo: Path, *targets: str) -> tuple[bool, str]:
    """`uv run --locked pytest -q`: whether it passed, and pytest's summary line. A run that
    printed no summary (uv failed, the lock is stale) did not run the tests: not run."""
    done = run(["uv", "run", "--locked", "pytest", "-q", "-p", "no:cacheprovider", *targets],
               cwd=repo, env=project_env(), timeout=TIMEOUT)
    line = tail(done.stdout)
    if done.returncode == 0:
        return True, line
    if not SUMMARY.search(line):
        raise NotRun(f"`uv run --locked pytest` failed ({done.returncode}): "
                     f"{(done.stderr or done.stdout).strip()[-400:]}")
    return False, line


def run_hidden(repo: Path, files: list[Path]) -> tuple[bool, str, bool, str]:
    tests = repo / "tests"
    tests.mkdir(exist_ok=True)
    names = []
    for f in files:
        shutil.copyfile(f, tests / f.name)
        names.append(f"tests/{f.name}")
    ok_hidden, hidden = pytest(repo, *names)
    ok_suite, suite = pytest(repo)
    return ok_hidden, hidden, ok_suite, suite


def feature(repository: str, ref: str, slugs: list[str]) -> dict:
    """Judge `ref` with the hidden tests of the slugs. Returns `ok`, `sha`, `hidden`, `suite`;
    raises NotRun."""
    files = hidden_files(slugs)
    holder = Path(tempfile.mkdtemp(prefix="chantier-judge-"))
    try:
        repo = clone(repository, holder)
        sha = checkout(repo, ref)
        ok_hidden, hidden, ok_suite, suite = run_hidden(repo, files)
        return {"ok": ok_hidden and ok_suite, "sha": sha, "hidden": hidden, "suite": suite}
    finally:
        sandbox.remove(holder)


def changelog_section(text: str, version: str) -> list[str]:
    """The bullets of one version's `## <version>` section."""
    lines, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip() == version
        elif inside and line.lstrip().startswith("- "):
            lines.append(line.strip())
    return lines


def is_sandbox(repository: str) -> bool:
    plain = repository.strip().rstrip("/").removesuffix(".git").lower()
    return plain in (f"https://github.com/{sandbox.REPO}", f"git@github.com:{sandbox.REPO}")


def release(version: str, repository: str, slugs: list[str]) -> tuple[bool, list[str]]:
    """Judge the release `version`. Returns whether it passed and one line per item; raises NotRun."""
    tag = f"v{version}"
    files = hidden_files(slugs) if slugs else []
    lines, ok = [], True

    def item(passed: bool, text: str) -> None:
        nonlocal ok
        ok = ok and passed
        lines.append(f"{'ok' if passed else 'FAIL'}: {text}")

    listed = must(["git", "ls-remote", "--tags", repository], timeout=120)
    tags = {row.partition("\t")[2].removeprefix("refs/tags/").removesuffix("^{}") for row in listed.splitlines()}
    if tag not in tags:
        item(False, f"the tag {tag} is not on the origin")
        return False, lines
    item(True, f"the tag {tag} is on the origin")

    holder = Path(tempfile.mkdtemp(prefix="chantier-judge-"))
    try:
        repo = clone(repository, holder)
        must(["git", "fetch", "--quiet", "--tags", "origin"], cwd=repo, timeout=600)
        merged = run(["git", "merge-base", "--is-ancestor", f"{tag}^{{commit}}", "origin/main"],
                     cwd=repo, env=git_env())
        item(merged.returncode == 0, f"the commit of {tag} is on main")
        sha = checkout(repo, f"refs/tags/{tag}")
        pyproject = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))
        init = (repo / "src" / "shelf" / "__init__.py").read_text(encoding="utf-8")
        found = re.search(r"^__version__\s*=\s*[\"']([^\"']+)[\"']", init, re.M)
        heading = re.search(r"^## (.+?)\s*$", (repo / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
        for where, value in (("pyproject.toml", pyproject["project"]["version"]),
                             ("shelf.__version__", found and found[1]),
                             ("the first heading of CHANGELOG.md", heading and heading[1])):
            item(value == version, f"{where} is {value} at {tag} (want {version})")
        done = run(["uv", "run", "python", "scripts/release_check.py"], cwd=repo,
                   env=project_env(), timeout=TIMEOUT)
        last = tail(done.stdout)
        item(done.returncode == 0 and last == "release check passed",
             f"release_check.py ends with `{last or tail(done.stderr)}`")
        if files:
            ok_hidden, hidden, ok_suite, suite = run_hidden(repo, files)
            lines.append(f"hidden: {hidden}")
            lines.append(f"suite: {suite}")
            item(ok_hidden and ok_suite, f"the hidden tests of {', '.join(slugs)} pass at {tag} "
                                         f"({sha[:7]})")
        notes = changelog_section((repo / "CHANGELOG.md").read_text(encoding="utf-8"), version)
    finally:
        sandbox.remove(holder)

    if not is_sandbox(repository):
        lines.append("GitHub release: not run: not the sandbox")
        return ok, lines
    done = run(["gh", "release", "view", tag, "--repo", sandbox.REPO, "--json", "tagName,name,body"],
               env=git_env(), timeout=120)
    if done.returncode != 0:
        text = (done.stderr or done.stdout).strip()
        if "not found" in text.lower():
            item(False, f"no GitHub release {tag} on {sandbox.REPO}: {text}")
            return False, lines
        raise NotRun(f"`gh release view {tag}` failed ({done.returncode}): {text}")
    shown = json.loads(done.stdout)
    body = shown.get("body") or ""
    missing = [n for n in notes if n not in body]
    item(shown.get("tagName") == tag and shown.get("name") == tag and not missing,
         f"GitHub release {tag}: name {shown.get('name')!r}"
         + (f", notes missing {len(missing)} of {len(notes)} bullets: {missing[:2]}" if missing
            else f", all {len(notes)} bullets of the changelog in its notes"))
    return ok, lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="judge.py", description=__doc__.splitlines()[0])
    parser.add_argument("--release", metavar="VERSION", help="judge the release v<version>")
    parser.add_argument("arguments", nargs="+", help="<repository> <ref> <slug>..., or with "
                        "--release: <repository> [<slug>...]")
    args = parser.parse_args(argv)
    try:
        if args.release:
            repository, slugs = args.arguments[0], args.arguments[1:]
            passed, lines = release(args.release, repository, slugs)
            print("\n".join(lines))
            print(f"judge release v{args.release}: {'pass' if passed else 'fail'}")
            return PASS if passed else FAIL
        if len(args.arguments) < 3:
            parser.error("a repository, a ref and at least one slug")
        repository, ref, *slugs = args.arguments
        result = feature(repository, ref, slugs)
        print(f"hidden: {result['hidden']}")
        print(f"suite: {result['suite']}")
        print(f"judge {', '.join(slugs)} at {result['sha'][:7]}: {'pass' if result['ok'] else 'fail'}")
        return PASS if result["ok"] else FAIL
    except NotRun as why:
        print(f"judge: not run: {why}")
        return NOT_RUN


if __name__ == "__main__":
    sys.exit(main())

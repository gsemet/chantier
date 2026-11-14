"""Stage a workspace for one eval campaign.

    uv run --no-project python evals/kit/setup.py <campaign> <workspace>

`claude-planted`: the tasks-cli project, a bare origin, the local forge. Creates `<workspace>` (a
git repository on `main`, pushed to `<workspace>.origin.git`) and the forge state next to it in
`<workspace>.forge/`. The campaign sets which prepared CRs go to `.agents/changes/2-backlog/P1/`,
which review steps the project's `AGENTS.md` declares, and which CI contracts the forge adds. On
Claude, `.claude/settings.local.json` puts the forge's folder first on `PATH` for every session in
the workspace (the Foreman, its Drivers and workers): their `gh` is the local forge.

`full`, `real-foreman`, `real-direct`, `copilot`, `ticket-summary`: the sandbox (shelf, on GitHub). Setup checks that
the sandbox is at its base (it never resets and never pushes), takes the run's number, clones the
sandbox into `<workspace>`, runs `chantier init` and `uv sync --locked` there, places the frozen
CRs (`kit/sandbox-crs/`) in `.agents/changes/3-ready/` with the run's PR-title convention, writes
`<workspace>.run.json` and prints the `open` line of each batch. The agents use the real `gh`. On
Claude, it also writes the workspace's `.claude/settings.local.json` (ignored by the sandbox's git)
with the rules the user's settings may lack: the operator's merge (`sandbox.py merge`) and, for a
release, its tag push and its GitHub release; nothing else.

`ticket-summary` places no CR and opens no batch: instead of the `open` lines, setup prints the
`gh issue create` line of the campaign's frozen issue (`kit/ticket-summary/`) and the path of the
ticket-less chat request, and allows the two posting commands (`gh issue comment`, `gh issue
artifact create`) in place of the merge. It creates nothing on the forge: the operator runs the line.

Exit codes: 0 ok, 1 usage, 2 precondition, 4 external (git, gh or uv failed). Standard library only.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sandbox  # noqa: E402  (the sandbox's constants, its survey helpers, its folder removal)

ROOT = HERE.parents[1]
CLI = ROOT / "skills" / "chantier" / "scripts" / "cli"  # the package's folder: its source is `src/`
IGNORE = shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache", "tasks.json")
REVIEWS = {
    "docs-review": ("chantier-eval-docs-reviewer", "every new or changed CLI command or option "
                    "is documented in README.md, with an example"),
    "style-review": ("chantier-eval-strict-reviewer", "the house style of the command line"),
}
QUICK = ["delete-item", "edit-item", "status-filter", "json-api", "stats-page"]
CAMPAIGNS = {
    "claude-planted": {"host": "claude",
                       "crs": ["add-priority", "done-unknown-id", "list-json", "delete-command",
                               "export-csv", "stats-command", "release-v0-2-0", "version-option"],
                       "reviews": ["docs-review", "style-review"], "contracts": True,
                       "release": "RELEASING.md"},
    # the sandbox campaigns: each batch lists its CRs in `open` order, the release's item number,
    # the CRs added during the batch, the slots and the budget
    "full": {"host": "claude", "mode": "parallel", "batches": [
        {"crs": [*QUICK, "csv-export", "item-notes", "title-search", "release-v0-2-0"],
         "release": 9, "added": ["item-rating"], "slots": 4, "budget": 40},
        {"crs": ["sort-list", "duplicate-url", "release-v0-3-0"], "release": 3, "added": [],
         "slots": 4, "budget": 15}]},
    "real-foreman": {"host": "claude", "mode": "choose", "batches": [
        {"crs": QUICK, "added": [], "slots": 3, "budget": 20}]},
    "real-direct": {"host": "claude", "mode": "choose", "batches": [
        {"crs": QUICK, "added": [], "slots": 3, "budget": 20, "direct": True}]},
    "copilot": {"host": "copilot", "batches": [
        {"crs": ["delete-item"], "added": [], "slots": 1, "budget": 3}]},
    # no batch and no frozen CR: one issue the operator creates, one request typed in the chat
    "ticket-summary": {"host": "claude", "batches": [],
                       "issue": {"title": "Dark theme for the reading list",
                                 "body": "ticket-summary/issue.md",
                                 "chat": "ticket-summary/chat-request.md"}},
}
OK, USAGE, PRECONDITION, EXTERNAL = sandbox.OK, sandbox.USAGE, sandbox.PRECONDITION, sandbox.EXTERNAL


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def sandbox_crs(spec: dict) -> list[str]:
    """Every CR of a sandbox campaign: its batches' CRs and the ones added during them."""
    return [slug for batch in spec["batches"] for slug in [*batch["crs"], *batch["added"]]]


def inside(path: Path, folder: Path) -> bool:
    return path == folder or folder in path.parents


# the staged campaign ------------------------------------------------------------------------------


def main(campaign: str, dest: Path) -> None:
    spec = CAMPAIGNS[campaign]
    if dest.exists():
        raise SystemExit(f"{dest} already exists")
    origin = dest.with_name(dest.name + ".origin.git")
    forge = dest.with_name(dest.name + ".forge")
    shutil.copytree(HERE / "fixture", dest, ignore=IGNORE)
    if spec["reviews"]:
        with (dest / "AGENTS.md").open("a", encoding="utf-8") as f:
            f.write("\n## chantier\n\n" + "".join(
                f"- {name}: `{REVIEWS[name][0]}`, after the Inspector: {REVIEWS[name][1]}\n"
                for name in spec["reviews"]))
            if spec.get("release"):
                f.write(f"- release: {spec['release']}\n")
    git("init", "--quiet", "-b", "main", str(dest), cwd=dest.parent)
    git("config", "user.name", "eval user", cwd=dest)
    git("config", "user.email", "eval@example.com", cwd=dest)
    git("add", ".", cwd=dest)
    git("commit", "--quiet", "-m", "chore: tasks-cli", cwd=dest)
    git("init", "--quiet", "--bare", "-b", "main", str(origin), cwd=dest.parent)
    git("remote", "add", "origin", str(origin), cwd=dest)
    git("push", "--quiet", "-u", "origin", "main", cwd=dest)
    git("remote", "set-head", "origin", "main", cwd=dest)

    forge.mkdir()
    state = forge / "state.json"
    state.write_text(json.dumps({"next_pr": 1, "next_run": 1, "prs": {}, "ci": {}}))
    if sys.platform == "win32":
        gh = forge / "gh.cmd"
        gh.write_text(f'@"{sys.executable}" "{HERE / "forge.py"}" %*\r\n')
    else:
        gh = forge / "gh"
        gh.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{HERE / "forge.py"}" "$@"\n')
        gh.chmod(0o755)
    # the Drivers and the Foreman call `gh` themselves: the forge's folder comes first on PATH
    env = {"FAKE_GH_STATE": str(state), "LIVE_ORIGIN": str(origin),
           "LIVE_CI_DELAY": "120", "PATH": str(forge) + os.pathsep + os.environ.get("PATH", "")}
    if spec.get("contracts"):
        env["LIVE_CI_CONTRACTS"] = str(HERE / "contracts")
    if spec["host"] == "claude":
        settings = dest / ".claude" / "settings.local.json"
        settings.write_text(json.dumps({"env": env}, indent=2) + "\n")

    backlog = dest / ".agents" / "changes" / "2-backlog" / "P1"
    for slug in spec["crs"]:
        shutil.copytree(HERE / "crs" / slug, backlog / slug)
    subprocess.run(["uv", "sync", "--quiet"], cwd=dest, check=True)
    print(f"campaign  {campaign}\nworkspace {dest}\norigin    {origin}\nforge     {state}")
    if spec["host"] != "claude":
        print("environment for every session of the batch:")
        print("".join(f"  {k}={v}\n" for k, v in env.items()), end="")


# a sandbox campaign -------------------------------------------------------------------------------


def survey() -> list[str]:
    """What keeps the sandbox from being at its base, by the survey `sandbox.py reset` makes: `main`
    at the recorded base, no other branch, no tag, no open PR, no release. Empty: it is at its base."""
    problems = sandbox.ref_problems(sandbox.remote_refs(), sandbox.recorded_base())
    prs = sandbox.open_prs()
    published = sandbox.releases()
    for what, found in (("open PRs", [f"#{p['number']}" for p in prs]), ("releases", published)):
        if found:
            problems.append(f"{what}: {', '.join(found)}")
    return problems


def run_number() -> int:
    """1 plus the highest `<n>` among the sandbox's PR titles that start with `[eval <n> `."""
    listed = json.loads(sandbox.gh("pr", "list", "--repo", sandbox.REPO, "--state", "all",
                                   "--limit", "1000", "--json", "title"))
    used = [int(m[1]) for p in listed if (m := re.match(r"\[eval (\d+) ", p["title"]))]
    return max(used, default=0) + 1


def chantier_state() -> dict:
    """This checkout's chantier: the CLI's version, its commit, whether the tree is clean."""
    init = (CLI / "src" / "chantier" / "__init__.py").read_text(encoding="utf-8")
    version = re.search(r"^__version__\s*=\s*[\"']([^\"']+)[\"']", init, re.M)[1]
    commit = sandbox.run(["git", "rev-parse", "HEAD"], cwd=ROOT).strip()
    dirty = bool(sandbox.run(["git", "status", "--porcelain"], cwd=ROOT).strip())
    return {"version": version, "commit": commit, "dirty": dirty}


def eval_section(campaign: str, run: int, date: str, prefix: str, release: bool) -> str:
    text = (f"\n## Eval run\n\n"
            f"This CR runs in chantier's eval campaign `{campaign}`, run {run}, set up on {date}.\n\n"
            f"- Every pull request this CR opens has a title that starts with `{prefix} `, followed "
            f"by the title it would have anyway, for example `{prefix} feat: delete an item`.\n")
    if release:
        text += ("- A fix this release needs carries this section into its fix-<n>.md, so its pull "
                 "request's title starts the same way.\n")
    return text


def place_crs(spec: dict, ws: Path, campaign: str, run: int, date: str, prefix: str) -> None:
    ready = ws / ".agents" / "changes" / "3-ready"
    for slug in sandbox_crs(spec):
        shutil.copytree(HERE / "sandbox-crs" / slug, ready / slug)
        path = ready / slug / "03-change-spec.md"
        body = path.read_bytes().decode("utf-8").replace("\r\n", "\n").rstrip("\n") + "\n"
        extra = eval_section(campaign, run, date, prefix, slug.startswith("release-"))
        path.write_bytes((body + extra).encode("utf-8"))


def merge_command() -> str:
    """The operator's merge, as a command line without its PR: the quoted script only if needed."""
    script = (HERE / "sandbox.py").as_posix()
    if " " in script:
        script = f'"{script}"'
    return f"uv run --no-project python {script} merge"


def allow_rules(spec: dict) -> list[str]:
    """The permission rules a sandbox run needs and the user's settings may lack: the merge, and
    for each release CR the tag push and the GitHub release of RELEASING.md (steps 6 and 7)."""
    both = lambda rule: [f"Bash({rule})", f"PowerShell({rule})"]  # noqa: E731
    if spec.get("issue"):  # merges nothing; posts the ticket summary on GitHub
        return both("gh issue comment *") + both("gh issue artifact create *")
    rules = both(f"{merge_command()} *")
    for slug in sandbox_crs(spec):
        m = re.fullmatch(r"release-v(\d+)-(\d+)-(\d+)", slug)
        if m:
            tag = "v" + ".".join(m.groups())
            rules += both(f"git push origin {tag}") + both(f"git -C * push origin {tag}")
            rules += both(f"gh release create {tag} *")
    return rules


def write_settings(ws: Path, spec: dict) -> int:
    """The workspace's ignored `.claude/settings.local.json`: the allow rules, nothing else."""
    path = ws / ".claude" / "settings.local.json"
    if path.exists():
        raise sandbox.Stop(PRECONDITION, f"{path} already exists")
    rules = allow_rules(spec)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps({"permissions": {"allow": rules}}, indent=2) + "\n").encode("utf-8"))
    return len(rules)


def open_lines(spec: dict, campaign: str) -> list[str]:
    lines = []
    for batch in spec["batches"]:
        mode = spec.get("mode")
        parts = ["$CHANTIER open", *(f".agents/changes/3-ready/{slug}" for slug in batch["crs"])]
        if batch.get("release"):
            parts.append(f"--release {batch['release']}")
        if mode:
            parts.append(f"--mode {'<stack|parallel|series>' if mode == 'choose' else mode}")
        parts += [f"--slots {batch['slots']}", f"--budget {batch['budget']}", "--default-branch main"]
        if batch.get("direct"):
            parts.append("--direct")
        lines.append(" ".join(parts))
    return lines


def sandbox_main(campaign: str, dest: Path) -> int:
    spec = CAMPAIGNS[campaign]
    # 1. preconditions: nothing is created before they pass
    if dest.exists():
        raise sandbox.Stop(PRECONDITION, f"{dest} already exists")
    if inside(dest, ROOT):
        raise sandbox.Stop(PRECONDITION, f"{dest} is inside this repository ({ROOT}): an eval's "
                                         "workspace is outside it")
    try:
        shown = subprocess.run(sandbox.resolve(["gh", "auth", "status"]), capture_output=True)
    except FileNotFoundError:
        raise sandbox.Stop(PRECONDITION, "`gh` is not installed or not on the PATH") from None
    if shown.returncode != 0:
        raise sandbox.Stop(PRECONDITION, "`gh auth status` failed: "
                           + (shown.stdout + shown.stderr).decode("utf-8", "replace").strip())
    problems = survey()
    if problems:
        raise sandbox.Stop(PRECONDITION, "the sandbox is not at its base: run sandbox.py reset, "
                                         "then reset --yes (" + "; ".join(problems) + ")")
    base = sandbox.recorded_base()
    # 2. the run's number, the date, the prefix
    run = run_number()
    date = datetime.date.today().isoformat()
    prefix = f"[eval {run} {date} {campaign}]"
    chantier = chantier_state()
    # 3. the clone, `init`, `uv sync --locked`
    try:
        sandbox.run(["git", "clone", "--quiet", sandbox.URL, str(dest)], env=sandbox.remote_env())
        head = sandbox.run(["git", "rev-parse", "HEAD"], cwd=dest).strip()
        if head != base:
            raise sandbox.Stop(PRECONDITION, f"the clone's HEAD is {head}, not the base {base}")
        sandbox.run(["uv", "run", "--locked", "--project", str(ROOT), "chantier", "init"], cwd=dest)
        sandbox.run(["uv", "sync", "--locked"], cwd=dest)
        allowed = write_settings(dest, spec) if spec["host"] == "claude" else 0
        # 4. the frozen CRs with the run's PR-title convention
        place_crs(spec, dest, campaign, run, date, prefix)
    except BaseException:
        if dest.exists():
            sandbox.remove(dest)
        raise
    # 5. the run record, next to the workspace
    record = {"campaign": campaign, "run": run, "date": date, "prefix": prefix,
              "repository": sandbox.REPO, "base": base, "chantier": chantier,
              "host": spec["host"], "crs": sandbox_crs(spec)}
    if spec.get("issue"):
        record["issue"] = {"title": f"{prefix} {spec['issue']['title']}",
                           "body": str(HERE / spec["issue"]["body"])}
    dest.with_name(dest.name + ".run.json").write_bytes(
        (json.dumps(record, indent=2) + "\n").encode("utf-8"))
    # 6. the summary
    print(f"campaign  {campaign}\nrun       {run}\nprefix    {prefix}\nworkspace {dest}\n"
          f"base      {base}\nchantier  {chantier['version']} {chantier['commit']}"
          f"{' (dirty tree)' if chantier['dirty'] else ''}")
    if record["crs"]:
        print(f"CRs placed in .agents/changes/3-ready/ ({len(record['crs'])}):")
        print("".join(f"  {slug}\n" for slug in record["crs"]), end="")
    print(f"\nCHANTIER = uv run --locked --project \"{ROOT}\" chantier   (run from the workspace)")
    if spec.get("issue"):
        print(issue_lines(record["issue"], spec["issue"]))
    else:
        print(f"merge     {merge_command()} <pr>   (run from the workspace)")
    if allowed:
        print(f"allowed   {allowed} rules in .claude/settings.local.json")
    for number, line in enumerate(open_lines(spec, campaign), 1):
        added = spec["batches"][number - 1]["added"]
        print(f"batch {number}: {line}" + (f"   (added during it: {', '.join(added)})" if added else ""))
    return OK


def issue_lines(issue: dict, frozen: dict) -> str:
    """The `ticket-summary` campaign's next steps: the issue's creation line and the chat request."""
    body = (HERE / frozen["body"]).as_posix()
    if " " in body:
        body = f'"{body}"'
    create = (f'gh issue create --repo {sandbox.REPO} --title "{issue["title"]}" '
              f"--body-file {body}")
    return (f"issue     {create}   (run it, then note its number)\n"
            f"chat      {(HERE / frozen['chat']).as_posix()}   "
            "(the ticket-less request, typed in the chat)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    if sys.argv[1] not in CAMPAIGNS:
        raise SystemExit(f"campaign: one of {', '.join(CAMPAIGNS)}")
    try:
        if "batches" in CAMPAIGNS[sys.argv[1]]:
            sys.exit(sandbox_main(sys.argv[1], Path(sys.argv[2]).resolve()))
        main(sys.argv[1], Path(sys.argv[2]).resolve())
    except sandbox.Stop as stop:
        print(f"setup.py: {stop}", file=sys.stderr)
        sys.exit(stop.code)

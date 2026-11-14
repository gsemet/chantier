"""The allow rules the commands need and the check of a user's settings."""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, NamedTuple

from chantier.core.files import read_text
from chantier.core.git import git
from chantier.core.repo import Repo
from chantier.plugin_files import is_dev_checkout

# The commands the cards make the agents write, filled with realistic values, each tied to the
# recommended allow rule that covers it and to a group. P10 asks whether some allow rule of the
# user's settings lets each one through (as Claude Code matches rules), whatever the rule's form.
GH_LIST_TIMEOUT = 10
_SHA = "0123456789abcdef0123456789abcdef01234567"


SHORT_CHARS = 60
_BRANCH = "chantier/batch-01/cr-101-example"


_TREE = "/work/project.worktrees/batch-01-CR-101"


# (capability, forge, command, recommended rule); ` origin ` stands for the project's remote name.
# The capability is one of CAPABILITIES; the forge is any, github, gitlab, gh-stack, dev or plugin.
# The order is the order of the table "Capabilities and their commands" in hosts/claude-code.md;
# SendMessage, a bare tool, belongs to the capability batch and comes last.
# P10 counts these commands, not rules.
SAMPLES = (
    ("batch", "any", f"git push -u origin {_BRANCH}", "git push -u origin chantier/*"),
    (
        "batch",
        "any",
        f"git -C {_TREE} push -u origin {_BRANCH}",
        "git -C * push -u origin chantier/*",
    ),
    (
        "batch",
        "any",
        f"git push --force-with-lease -u origin {_BRANCH}",
        "git push --force-with-lease -u origin chantier/*",
    ),
    (
        "batch",
        "any",
        f"git -C {_TREE} push --force-with-lease -u origin {_BRANCH}",
        "git -C * push --force-with-lease -u origin chantier/*",
    ),
    (
        "batch",
        "any",
        f"git push --force-with-lease={_BRANCH}:{_SHA} origin {_SHA}:refs/heads/{_BRANCH}",
        "git push --force-with-lease=chantier/* origin *chantier/*",
    ),
    (
        "batch",
        "dev",
        "uv run --locked --project /checkout chantier status",
        "uv run --locked --project * chantier *",
    ),
    (
        "batch",
        "plugin",
        "uvx --from /plugin chantier --skill /plugin/skills/chantier status",
        "uvx --from * chantier *",
    ),
    ("batch", "github", "gh pr create --draft --body-file /tmp/body.md", "gh pr create*"),
    ("batch", "github", "gh pr edit 12 --body-file /tmp/body.md", "gh pr edit*"),
    ("batch", "github", "gh pr edit 12 --base chantier/batch-01/cr-100-base", "gh pr edit*"),
    ("batch", "github", "gh pr ready 12", "gh pr ready*"),
    ("batch", "github", "gh pr ready 12 --undo", "gh pr ready*"),
    ("batch", "github", "gh pr checks 12", "gh pr checks*"),
    ("batch", "github", "gh pr view 12", "gh pr view*"),
    ("stack", "gh-stack", "gh stack view", "gh stack*"),
    (
        "batch",
        "gitlab",
        "glab mr create --draft --description-file /tmp/body.md",
        "glab mr create*",
    ),
    ("batch", "gitlab", "glab mr update 12 --target-branch main", "glab mr update*"),
    ("batch", "gitlab", "glab mr view 12", "glab mr view*"),
    ("batch", "gitlab", "glab ci status", "glab ci status*"),
    ("release", "github", "gh pr merge 12 --rebase", "gh pr merge*"),
    ("release", "gitlab", "glab mr merge 12 --rebase", "glab mr merge*"),
    ("release", "any", "git push origin v1.2.3", "git push origin v*"),
    (
        "release",
        "github",
        "gh release create v1.2.3 --verify-tag --notes-file /tmp/notes.md",
        "gh release create*",
    ),
    (
        "release",
        "gitlab",
        "glab release create v1.2.3 --notes-file /tmp/notes.md",
        "glab release create*",
    ),
    ("fixes", "github", "gh pr merge 12 --rebase", "gh pr merge*"),
    ("fixes", "gitlab", "glab mr merge 12 --rebase", "glab mr merge*"),
)


# The capabilities, in the table's order, and how P10 names each.
CAPABILITIES = {
    "batch": "every batch",
    "stack": "a stack",
    "release": "a release on its own",
    "fixes": "fixes on a grant",
}


def _allow_for(capabilities: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        f"{tool}({rule})"
        for rule in dict.fromkeys(s[3] for s in SAMPLES if s[0] in capabilities)
        for tool in ("Bash", "PowerShell")
    )


# The allow rules hosts/claude-code.md recommends, in its table's order (a test compares them):
# the capabilities every batch and a stack; the pasteable block holds exactly these.
RECOMMENDED_ALLOW = (*_allow_for(("batch", "stack")), "SendMessage")


# The rules offered only under a grant (a release on its own, fixes on a grant): not in the block.
GRANT_ALLOW = _allow_for(("release", "fixes"))

SETTINGS_SHOWN = "~/.claude/settings.json, .claude/settings.json, .claude/settings.local.json"


# Rules auto mode drops on entry (hosts/claude-code.md, "What not to add"): they do not count.
_DROPPED = re.compile(
    r"\*?|(python3?|node|ruby|perl|bash|sh|zsh|pwsh|powershell|cmd|php|deno|bun|env|sudo|xargs"
    r"|npx|bunx)( ?\*)?|(uv|npm|pnpm|yarn|pip|pipx|poetry|bun)( run)?( ?\*)?",
    re.I,
)


_RULE = re.compile(r"([^()]+?)\s*(?:\((.*)\))?", re.S)


def _glob(pattern: str, text: str, fold: bool) -> bool:
    regex = ".*".join(re.escape(part) for part in pattern.split("*"))
    return re.fullmatch(regex, text, re.S | (re.I if fold else 0)) is not None


def rule_matches(rule: str, tool: str, command: str = "") -> bool:
    """Whether a permission rule `Tool(pattern)` (or a bare tool name) covers this tool use, as
    Claude Code documents: `*` matches any text, `cmd *` also matches the bare `cmd`, the legacy
    `:*` suffix reads as ` *`, PowerShell matches without case, a bare tool name matches all."""
    m = _RULE.fullmatch(rule.strip())
    if not m or m[1] != tool:
        return False
    if m[2] is None:
        return True
    pattern = m[2].strip()
    if pattern.endswith(":*"):
        pattern = pattern[:-2] + " *"
    fold = tool == "PowerShell"
    if pattern.endswith(" *") and _glob(pattern[:-2], command, fold):
        return True
    return _glob(pattern, command, fold)


def _counts_as_allow(rule: str) -> bool:
    """False for an allow rule auto mode drops on entry: it protects nothing unattended."""
    m = _RULE.fullmatch(rule.strip())
    if not m:
        return False
    if m[1] in ("Bash", "PowerShell"):
        return m[2] is not None and not _DROPPED.fullmatch(m[2].strip())
    return not m[1].startswith(("Agent", "Monitor"))


def _settings_rules(repo: Repo | None) -> tuple[dict[str, list[str]], list[str]]:
    """The `permissions` allow, deny and ask strings of the user's three settings files, and the
    files that could not be read. A file that is absent holds nothing."""
    files = [Path.home() / ".claude" / "settings.json"]
    if repo:
        files += [
            repo.session_root / ".claude" / "settings.json",
            repo.session_root / ".claude" / "settings.local.json",
        ]
    rules: dict[str, list[str]] = {"allow": [], "deny": [], "ask": []}
    unreadable: list[str] = []
    for path in files:
        if not path.is_file():
            continue
        try:
            permissions = json.loads(read_text(path)).get("permissions", {})
            for kind in rules:
                rules[kind] += [r for r in permissions.get(kind, []) if isinstance(r, str)]
        except (OSError, ValueError, AttributeError):
            unreadable.append(str(path))
    return rules, unreadable


def _forges(remote: str) -> set[str]:
    """The forges that apply: the remote's forge, the `gh stack` extension when
    `gh extension list` names it."""
    url = git("remote", "get-url", remote, check=False).lower()
    host = re.sub(r"^.*?(?:://|@)", "", url).split("/")[0].split(":")[0]
    forges = {"any", "dev" if is_dev_checkout() else "plugin"}
    if "gitlab" in host:
        forges.add("gitlab")
    elif "github" in host:
        forges.add("github")
    else:
        forges |= {"github", "gitlab"}
    if "github" in forges and _gh_names_stack():
        forges.add("gh-stack")
    return forges


def _gh_names_stack() -> bool:
    """Whether `gh extension list` names the `gh stack` extension. No `gh`, a failure or a
    timeout reads as no: P9 reports a missing or broken `gh`."""
    exe = shutil.which("gh")
    if not exe:
        return False
    try:
        p = subprocess.run(
            [exe, "extension", "list"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=GH_LIST_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if p.returncode != 0:
        return False
    for line in p.stdout.splitlines():
        cols = [c.strip() for c in line.split("\t")]
        if cols[0].startswith("gh stack") or (len(cols) > 1 and cols[1].endswith("/gh-stack")):
            return True
    return False


def _caught(rules: dict[str, Any], tool: str, command: str) -> tuple[str, str] | None:
    """The deny or ask rule that catches the command, as (kind, rule)."""
    return next(
        (
            (kind, r)
            for kind in ("deny", "ask")
            for r in rules[kind]
            if rule_matches(r, tool, command)
        ),
        None,
    )


class Gap(NamedTuple):
    """What the settings lack for one capability."""

    missing: int
    total: int
    named: list[str]
    blocked: list[str]


def _gap(
    rows: list[tuple[str, str, str, str]], remote: str, rules: dict[str, Any], send: bool
) -> Gap:
    allow = [r for r in rules["allow"] if _counts_as_allow(r)]
    tools = ("Bash", "PowerShell") if os.name == "nt" else ("Bash",)
    adds: dict[str, list[str]] = {}
    blocked: list[str] = []
    missing = 0
    for _, _, raw_command, raw_rule in rows:
        command = raw_command.replace(" origin ", f" {remote} ")
        rule = raw_rule.replace(" origin ", f" {remote} ")
        short = command if len(command) < SHORT_CHARS else command[: SHORT_CHARS - 3] + "..."
        lacking, held = [], []
        for tool in tools:
            hit = _caught(rules, tool, command)
            if hit:
                held.append(f"{short} by {hit[1]}" + (" (asks)" if hit[0] == "ask" else ""))
            elif not any(rule_matches(r, tool, command) for r in allow):
                lacking.append(f"{tool}({rule})")
        blocked += [n for n in dict.fromkeys(held) if n not in blocked]
        if lacking:
            adds.setdefault(", ".join(lacking), []).append(short)
        missing += bool(lacking) or bool(held)
    if send and not any(rule_matches(r, "SendMessage") for r in rules["allow"]):
        adds["SendMessage"] = ["SendMessage"]
        missing += 1
    named = [f"{' / '.join(samples)} (add {add})" for add, samples in adds.items()]
    return Gap(missing, len(rows) + send, named, blocked)


def commands_not_allowed(
    repo: Repo | None, capabilities: set[str] | None = None
) -> tuple[dict[str, Gap], list[str]]:
    """For each asked capability (the base by default), in the table's order: the applicable
    sample commands that the settings do not let through (how many of how many, what to add,
    what a deny or ask rule catches); and the unreadable settings files."""
    remote = "origin"
    if repo:
        with contextlib.suppress(Exception):
            remote = repo.config.get("remote") or remote
    remotes = git("remote", check=False).split()
    if remote not in remotes and remotes:
        remote = "origin" if "origin" in remotes else remotes[0]
    rules, unreadable = _settings_rules(repo)
    forges = _forges(remote)
    gaps = {
        cap: _gap(
            [s for s in SAMPLES if s[0] == cap and s[1] in forges], remote, rules, cap == "batch"
        )
        for cap in CAPABILITIES
        if cap in (capabilities or {"batch"}) | {"batch"}
    }
    return gaps, unreadable

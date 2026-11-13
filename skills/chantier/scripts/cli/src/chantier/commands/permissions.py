"""The allow rules the commands need and the check of a user's settings."""

from __future__ import annotations

import contextlib
import json
import os
import re
from pathlib import Path

from chantier.commands.rules import linked
from chantier.core.files import read_text
from chantier.core.git import git
from chantier.core.repo import Repo
from chantier.plugin_files import project_instructions, surface_instructions

# The commands the cards make the agents write, filled with realistic values, each tied to the
# recommended allow rule that covers it and to a group. P10 asks whether some allow rule of the
# user's settings lets each one through (as Claude Code matches rules), whatever the rule's form.
_SHA = "0123456789abcdef0123456789abcdef01234567"


SHORT_CHARS = 60
_BRANCH = "chantier/batch-01/cr-101-example"


_TREE = "/work/project.worktrees/batch-01-CR-101"


# (group, command, recommended rule); ` origin ` stands for the project's remote name. The order
# is the order of the table in hosts/claude-code.md; SendMessage, a bare tool, comes last.
SAMPLES = (
    ("always", f"git push -u origin {_BRANCH}", "git push -u origin chantier/*"),
    ("always", f"git -C {_TREE} push -u origin {_BRANCH}", "git -C * push -u origin chantier/*"),
    (
        "always",
        f"git push --force-with-lease -u origin {_BRANCH}",
        "git push --force-with-lease -u origin chantier/*",
    ),
    (
        "always",
        f"git -C {_TREE} push --force-with-lease -u origin {_BRANCH}",
        "git -C * push --force-with-lease -u origin chantier/*",
    ),
    (
        "always",
        f"git push --force-with-lease={_BRANCH}:{_SHA} origin {_SHA}:refs/heads/{_BRANCH}",
        "git push --force-with-lease=chantier/* origin *chantier/*",
    ),
    (
        "always",
        "uv run --script /plugin/skills/chantier/scripts/cli/chantier.py status",
        "uv run --script *chantier.py *",
    ),
    ("github", "gh pr create --draft --body-file /tmp/body.md", "gh pr create*"),
    ("github", "gh pr edit 12 --body-file /tmp/body.md", "gh pr edit*"),
    ("github", "gh pr edit 12 --base chantier/batch-01/cr-100-base", "gh pr edit*"),
    ("github", "gh pr ready 12", "gh pr ready*"),
    ("github", "gh pr ready 12 --undo", "gh pr ready*"),
    ("github", "gh pr checks 12", "gh pr checks*"),
    ("github", "gh pr view 12", "gh pr view*"),
    ("gh-stack", "gh stack view", "gh stack*"),
    (
        "gh-release",
        "gh release create v1.2.3 --title v1.2.3 --verify-tag --notes-file /tmp/n.md",
        "gh release create*",
    ),
    ("gitlab", "glab mr create --draft --description-file /tmp/body.md", "glab mr create*"),
    ("gitlab", "glab mr update 12 --target-branch main", "glab mr update*"),
    ("gitlab", "glab mr view 12", "glab mr view*"),
    ("gitlab", "glab ci status", "glab ci status*"),
    ("glab-release", "glab release create v1.2.3 --notes-file /tmp/n.md", "glab release create*"),
)


# The allow rules hosts/claude-code.md recommends, in its table's order (a test compares them).
RECOMMENDED_ALLOW = (
    *tuple(
        f"{tool}({rule})"
        for rule in dict.fromkeys(s[2] for s in SAMPLES)
        for tool in ("Bash", "PowerShell")
    ),
    "SendMessage",
)


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


def _sample_groups(repo: Repo | None, remote: str) -> set[str]:
    """The sample groups that apply: the remote's forge, the `gh stack` extension when installed,
    the publication when the project's rules name it."""
    url = git("remote", "get-url", remote, check=False).lower()
    host = re.sub(r"^.*?(?:://|@)", "", url).split("/")[0].split(":")[0]
    groups = {"always"}
    if "gitlab" in host:
        groups.add("gitlab")
    elif "github" in host:
        groups.add("github")
    else:
        groups |= {"github", "gitlab"}
    text = ""
    if repo:
        seen: list[Path] = []
        for first, root in (
            (project_instructions(repo), repo.root),
            (surface_instructions(repo), repo.surface),
        ):
            if first:
                seen.append(first.resolve())
                linked(first.resolve(), root.resolve(), seen, 2)
        text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in seen)
    if "github" in groups and "gh release create" in text:
        groups.add("gh-release")
    if "gitlab" in groups and "glab release create" in text:
        groups.add("glab-release")
    data = [os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")]
    if os.environ.get("LOCALAPPDATA"):
        data.append(os.environ["LOCALAPPDATA"])
    if "github" in groups and any(
        (Path(d) / sub / "extensions" / "gh-stack").exists()
        for d in data
        for sub in ("gh", "GitHub CLI")
    ):
        groups.add("gh-stack")
    return groups


def commands_not_allowed(repo: Repo | None) -> tuple[int, int, list[str], list[str], list[str]]:
    """The applicable sample commands that the settings do not let through: how many of how many;
    what to add; what a deny or ask rule catches; the unreadable files."""
    remote = "origin"
    if repo:
        with contextlib.suppress(Exception):
            remote = repo.config.get("remote") or remote
    remotes = git("remote", check=False).split()
    if remote not in remotes and remotes:
        remote = "origin" if "origin" in remotes else remotes[0]
    rules, unreadable = _settings_rules(repo)
    allow = [r for r in rules["allow"] if _counts_as_allow(r)]
    tools = ("Bash", "PowerShell") if os.name == "nt" else ("Bash",)
    groups = _sample_groups(repo, remote)
    wanted = [s for s in SAMPLES if s[0] in groups]
    adds: dict[str, list[str]] = {}
    blocked: list[str] = []
    missing = 0
    for _, raw_command, raw_rule in wanted:
        command = raw_command.replace(" origin ", f" {remote} ")
        rule = raw_rule.replace(" origin ", f" {remote} ")
        short = command if len(command) < SHORT_CHARS else command[: SHORT_CHARS - 3] + "..."
        lacking, held_back = [], False
        for tool in tools:
            hit = next(
                (
                    (kind, r)
                    for kind in ("deny", "ask")
                    for r in rules[kind]
                    if rule_matches(r, tool, command)
                ),
                None,
            )
            if hit:
                held_back = True
                note = f"{short} by {hit[1]}" + (" (asks)" if hit[0] == "ask" else "")
                if note not in blocked:
                    blocked.append(note)
            elif not any(rule_matches(r, tool, command) for r in allow):
                lacking.append(f"{tool}({rule})")
        if lacking:
            adds.setdefault(", ".join(lacking), []).append(short)
        missing += bool(lacking) or held_back
    if not any(rule_matches(r, "SendMessage") for r in rules["allow"]):
        adds["SendMessage"] = ["SendMessage"]
        missing += 1
    named = [f"{' / '.join(samples)} (add {add})" for add, samples in adds.items()]
    return missing, len(wanted) + 1, named, blocked, unreadable

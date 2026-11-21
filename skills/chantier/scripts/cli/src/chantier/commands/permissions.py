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

from chantier.commands.allow_samples import CAPABILITIES, SAMPLES, fill_sample
from chantier.core.files import read_text
from chantier.core.git import git
from chantier.core.repo import Repo
from chantier.plugin_files import is_dev_mode, skill_dir

# P10 asks whether some allow rule of the user's settings lets each sample command of
# `allow_samples` through (as Claude Code matches rules), whatever the rule's form.
GH_LIST_TIMEOUT = 10
SHORT_CHARS = 60

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


def _settings_rules(
    repo: Repo | None,
) -> tuple[dict[str, list[str]], list[str], dict[str, str]]:
    """The `permissions` allow, deny and ask strings of the user's three settings files, the
    files that could not be read, and the first file each allow rule came from. A file that is
    absent holds nothing."""
    files = [Path.home() / ".claude" / "settings.json"]
    if repo:
        files += [
            repo.session_root / ".claude" / "settings.json",
            repo.session_root / ".claude" / "settings.local.json",
        ]
    rules: dict[str, list[str]] = {"allow": [], "deny": [], "ask": []}
    unreadable: list[str] = []
    origins: dict[str, str] = {}
    for path in files:
        if not path.is_file():
            continue
        try:
            permissions = json.loads(read_text(path)).get("permissions", {})
            for kind in rules:
                rules[kind] += [r for r in permissions.get(kind, []) if isinstance(r, str)]
            origins |= {
                r: str(path)
                for r in permissions.get("allow", [])
                if isinstance(r, str) and r not in origins
            }
        except (OSError, ValueError, AttributeError):
            unreadable.append(str(path))
    return rules, unreadable, origins


def _dev_mode(repo: Repo | None) -> bool:
    """The install's mode for this project: dev only in chantier's own checkout when the
    session's project is chantier; every mode test of this file asks it."""
    return is_dev_mode(repo)


def _forges(remote: str, repo: Repo | None) -> set[str]:
    """The forges that apply: the remote's forge, the `gh stack` extension when
    `gh extension list` names it; and the mode's rows, `dev` or `plugin`."""
    url = git("remote", "get-url", remote, check=False).lower()
    host = re.sub(r"^.*?(?:://|@)", "", url).split("/")[0].split(":")[0]
    forges = {"any", "dev" if _dev_mode(repo) else "plugin"}
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
    advice: str = ""  # the broad and stale chantier rules found, as the P10 line ends with them


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


# What a broad chantier rule lets through: a rule that matches one of these commands names no real
# path; the last two are older forms still found in users' settings.
PROBES = (
    'uvx --from "/elsewhere" chantier status',
    'uv run --no-sync --project "/elsewhere" chantier status',
    "uv run --no-sync --project . python -c x chantier y",
    'uv sync --locked --project "/elsewhere"',
    "uv run --script /elsewhere/chantier.py status",
    'uv run --locked --project "/elsewhere" chantier status',
)

_PLUGIN_FORM = re.compile(r'(?:Bash|PowerShell)\(uvx --from "(.*)" chantier \*\)')
_DEV_FORM = re.compile(
    r'(?:Bash|PowerShell)\((?:uv run --no-sync --project "(.*)" chantier \*|'
    r'uv sync --locked --project "(.*)")\)'
)


def _tools() -> tuple[str, ...]:
    return ("Bash", "PowerShell") if os.name == "nt" else ("Bash",)


def _broad(allow: list[str]) -> list[str]:
    """The allow rules that let a probe command through, in order."""
    return [
        r
        for r in dict.fromkeys(allow)
        if any(rule_matches(r, tool, probe) for tool in _tools() for probe in PROBES)
    ]


def _replacing(rule: str, allow: list[str], samples: list[tuple[str, str, str, str]]) -> str:
    """The filled real-path rules of this install that replace a broad rule: those whose sample
    (of this install's mode) the rule lets through, in the broad rule's tool, each marked
    `present` when the settings hold it; "no chantier command needs it" with none."""
    tool = rule.split("(", 1)[0]
    found = [f"{tool}({sample[3]})" for sample in samples if rule_matches(rule, tool, sample[2])]
    if not found:
        return "no chantier command needs it"
    return "replaced by " + " and ".join(f"{r}{' present' if r in allow else ''}" for r in found)


def _stale(allow: list[str], broad: list[str], dev: bool) -> list[str]:
    """The allow rules in the form of a chantier rule that name another path than this
    install's and let no probe through: in the plugin mode a plugin-form rule of any other path;
    in either mode a dev-form rule (dev or sync) whose folder no longer exists."""
    here = os.path.normcase(skill_dir().parents[1].as_posix())
    stale = []
    for r in dict.fromkeys(allow):
        if r in broad:
            continue
        m = _PLUGIN_FORM.fullmatch(r)
        if m and not dev and os.path.normcase(m[1]) != here:
            stale.append(r)
            continue
        m = _DEV_FORM.fullmatch(r)
        path = m and (m[1] or m[2])
        if path and os.path.normcase(path) != here and not Path(path).is_dir():
            stale.append(r)
    return stale


def _advice(rules: dict[str, Any], origins: dict[str, str], mode: str) -> str:
    """The end of the P10 line for the broad and stale chantier rules; empty with none."""
    allow = [r for r in rules["allow"] if _counts_as_allow(r)]
    samples = [fill_sample(s) for s in SAMPLES if s[1] == mode and s[0] == "batch"]
    broad = _broad(allow)
    stale = _stale(allow, broad, mode == "dev")
    text = ""
    if broad:
        named = "; ".join(
            f"{r} ({origins.get(r, '?')}), {_replacing(r, rules['allow'], samples)}" for r in broad
        )
        text += f"; broad rules let any command through, remove them by hand: {named}"
    if stale:
        named = "; ".join(f"{r} ({origins.get(r, '?')})" for r in stale)
        text += f"; stale chantier rules, remove them by hand: {named}"
    return text


def commands_not_allowed(
    repo: Repo | None, capabilities: set[str] | None = None
) -> tuple[dict[str, Gap], list[str]]:
    """For each asked capability (the base by default), in the table's order: the applicable
    sample commands that the settings do not let through (how many of how many, what to add,
    what a deny or ask rule catches); and the unreadable settings files. The chantier rows are
    filled with this install's real paths; the base capability's gap also carries the broad and
    stale chantier rules the settings hold."""
    remote = "origin"
    if repo:
        with contextlib.suppress(Exception):
            remote = repo.config.get("remote") or remote
    remotes = git("remote", check=False).split()
    if remote not in remotes and remotes:
        remote = "origin" if "origin" in remotes else remotes[0]
    rules, unreadable, origins = _settings_rules(repo)
    forges = _forges(remote, repo)
    gaps = {
        cap: _gap(
            [fill_sample(s) for s in SAMPLES if s[0] == cap and s[1] in forges],
            remote,
            rules,
            cap == "batch",
        )
        for cap in CAPABILITIES
        if cap in (capabilities or {"batch"}) | {"batch"}
    }
    gaps["batch"] = gaps["batch"]._replace(
        advice=_advice(rules, origins, "dev" if _dev_mode(repo) else "plugin")
    )
    return gaps, unreadable

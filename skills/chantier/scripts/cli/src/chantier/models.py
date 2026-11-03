"""Model selection per host: base lists in the skill, user and project overrides, exact ids only.

An agent never interprets a model name: this module resolves a role (and a CR) to one exact id
from a host catalog, and refuses anything else. There is no fuzzy matching anywhere, by design:
"GPT 5.6 Luna" must never become `gpt-6-luna` because the names look alike.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .state import EXIT_PRECONDITION, EXIT_USAGE, ChantierError

HOSTS = ("claude", "copilot")
ROLES = ("foreman", "cr-driver", "stack-driver", "qa-driver", "investigator", "coder",
         "inspector", "debugger", "verifier", "conflict-resolver")
INHERIT = "inherit"
SECTIONS = ("catalog", "roles", "aliases", "effort", "tools")
# Reasoning levels both hosts accept (Claude Code `effort`, Copilot `reasoning-effort`);
# which levels a given model honors is checked by the host at dispatch, not here.
EFFORTS = ("low", "medium", "high", "xhigh", "max")
# Sections only the skill's base list may set: tools are part of a role's contract.
SKILL_ONLY = ("tools",)
# The Foreman's heartbeat interval, `<n>s` or `<n>m`: just under the prompt-cache TTL of its
# model on this host, so a wake never pays a cold read of the whole context.
HEARTBEAT = re.compile(r"^(?P<n>[1-9]\d*)(?P<unit>[sm])$")
HEARTBEAT_RANGE = (60, 3600)
BRIEF_ENTRY = re.compile(r"^(?P<role>[a-z-]+)(?:@(?P<cr>CR-\d+))?=(?P<model>\S+)$")
CR_IN_NAME = re.compile(r"\bCR-\d+\b")


# ---- a strict YAML subset -------------------------------------------------------------------

def parse_yaml(text: str, where: str) -> dict:
    """Nested mappings of plain or quoted scalars, `{}`, and `#` comments. Anything else fails.

    The CLI stays free of dependencies (it runs with `uv run --script`, offline), and a small
    strict parser cannot guess what a malformed line meant.
    """
    root: dict = {}
    # (indent of the key that owns the mapping, the mapping, indent of its own keys)
    stack: list[list] = [[-1, root, None]]
    pending: tuple[int, dict, str] | None = None
    for n, raw in enumerate(text.splitlines(), 1):
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        if "\t" in line[: len(line) - len(line.lstrip())]:
            raise ChantierError(f"{where}:{n}: tabs are not allowed for indentation", EXIT_PRECONDITION)
        indent = len(line) - len(line.lstrip())
        body = line.strip()
        m = re.fullmatch(r"(?P<key>[^:\s][^:]*?):(?:\s+(?P<value>.+))?", body)
        if not m:
            raise ChantierError(f"{where}:{n}: expected `key: value`, got `{body}`", EXIT_PRECONDITION)
        if pending:
            p_indent, p_parent, p_key = pending
            p_parent[p_key] = {}
            if indent > p_indent:
                stack.append([p_indent, p_parent[p_key], None])
            pending = None
        while indent <= stack[-1][0]:
            stack.pop()
        level = stack[-1]
        if level[2] is None:
            level[2] = indent
        elif level[2] != indent:
            raise ChantierError(f"{where}:{n}: inconsistent indentation", EXIT_PRECONDITION)
        parent = level[1]
        key = _unquote(m.group("key").strip())
        if key in parent:
            raise ChantierError(f"{where}:{n}: duplicate key `{key}`", EXIT_PRECONDITION)
        value = m.group("value")
        if value is None:
            parent[key] = None
            pending = (indent, parent, key)
        elif value.strip() == "{}":
            parent[key] = {}
        elif value.strip()[:1] in "[{&*!|>":
            raise ChantierError(f"{where}:{n}: only plain scalars are supported, got `{value}`",
                           EXIT_PRECONDITION)
        else:
            parent[key] = _unquote(value.strip())
    if pending:
        pending[1][pending[2]] = {}
    return root


def _strip_comment(line: str) -> str:
    quote = None
    for i, ch in enumerate(line):
        if ch in "\"'" and quote in (None, ch):
            quote = None if quote else ch
        elif ch == "#" and not quote and (i == 0 or line[i - 1].isspace()):
            return line[:i]
    return line


def _unquote(s: str) -> str:
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


# ---- host detection -------------------------------------------------------------------------

def detect_host(explicit: str | None = None) -> tuple[str, str]:
    """The host and why: `--host`, `CHANTIER_HOST`, then the host's own environment variables."""
    if explicit:
        return _check_host(explicit), "--host"
    if os.environ.get("CHANTIER_HOST"):
        return _check_host(os.environ["CHANTIER_HOST"]), "CHANTIER_HOST"
    if os.environ.get("CLAUDE_CODE_ENTRYPOINT"):
        return "claude", "CLAUDE_CODE_ENTRYPOINT"
    if (os.environ.get("COPILOT_CLI") or os.environ.get("COPILOT_AGENT_SESSION_ID")
            or os.environ.get("AI_AGENT", "").startswith("github_copilot")):
        return "copilot", "COPILOT_* environment"
    raise ChantierError("cannot tell the host (Claude or Copilot): set CHANTIER_HOST or pass --host",
                   EXIT_USAGE)


def _check_host(host: str) -> str:
    if host not in HOSTS:
        raise ChantierError(f"unknown host `{host}`: one of {', '.join(HOSTS)}", EXIT_USAGE)
    return host


# ---- loading and validation -----------------------------------------------------------------

def base_path(skill: Path, host: str) -> Path:
    return skill / "references" / "models" / f"{host}.yml"


def user_path() -> Path:
    env = os.environ.get("CHANTIER_MODELS_USER")
    if env:
        return Path(env).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(xdg) / "chantier" / "models.yml"


def project_path(root: Path) -> Path:
    return root / ".agents" / "chantier.models.yml"


class Models:
    """The merged model configuration of one host, with the source of every role."""

    def __init__(self, host: str, skill: Path, root: Path | None, legacy: dict | None = None,
                 base_only: bool = False):
        self.host = host
        self.catalog: dict[str, str] = {}
        self.aliases: dict[str, str] = {}
        self.roles: dict[str, str] = {}
        self.source: dict[str, str] = {}
        self.effort: dict[str, str] = {}
        self.effort_source: dict[str, str] = {}
        self.tools: dict[str, str] = {}
        self.heartbeat: str | None = None
        self.heartbeat_source = "default"
        self.errors: list[str] = []
        if legacy:
            self.errors.append("`models` in .agents/chantier.json is no longer read: move it to "
                               ".agents/chantier.models.yml under the host's `roles`")
        base = base_path(skill, host)
        if not base.exists():
            raise ChantierError(f"missing base model list {base}", EXIT_PRECONDITION)
        self._merge(self._base(base), "skill", str(base))
        layers = [] if base_only else [(user_path(), "user")]
        if root and not base_only:
            layers.append((project_path(root), "project"))
        for path, label in layers:
            if path.exists():
                data = parse_yaml(path.read_text(), str(path))
                unknown = set(data) - set(HOSTS)
                if unknown:
                    self.errors.append(f"{path}: unknown host key(s) {', '.join(sorted(unknown))}"
                                       f" (expected {', '.join(HOSTS)})")
                self._merge(data.get(host) or {}, label, str(path))
        self._validate()

    def _base(self, path: Path) -> dict:
        data = parse_yaml(path.read_text(), str(path))
        if data.get("host") != self.host:
            self.errors.append(f"{path}: `host` must be `{self.host}`")
        return {k: v for k, v in data.items() if k != "host"}

    def _merge(self, data: dict, label: str, where: str) -> None:
        if not isinstance(data, dict):
            self.errors.append(f"{where}: `{self.host}` must be a mapping")
            return
        for section, values in data.items():
            if section == "heartbeat":
                if not isinstance(values, str) or not HEARTBEAT.match(values):
                    self.errors.append(f"{where}: heartbeat must be `<n>s` or `<n>m`, "
                                       f"not `{values}`")
                else:
                    self.heartbeat, self.heartbeat_source = values, label
                continue
            if section not in SECTIONS:
                self.errors.append(f"{where}: unknown section `{section}` "
                                   f"(expected heartbeat, {', '.join(SECTIONS)})")
                continue
            if not isinstance(values, dict):
                self.errors.append(f"{where}: `{section}` must be a mapping")
                continue
            if section in SKILL_ONLY and label != "skill":
                self.errors.append(f"{where}: `{section}` is set by the skill only "
                                   "(a role's tools are part of its contract)")
                continue
            for key, value in values.items():
                if not isinstance(value, str) or not value:
                    self.errors.append(f"{where}: {section}.{key} must be a non-empty string")
                    continue
                if section in ("roles", "effort", "tools"):
                    if key not in ROLES:
                        self.errors.append(f"{where}: {section}: unknown role `{key}` "
                                           f"(roles: {', '.join(ROLES)})")
                        continue
                    if section == "roles":
                        self.roles[key], self.source[key] = value, label
                    elif section == "effort":
                        self.effort[key], self.effort_source[key] = value, label
                    else:
                        self.tools[key] = value
                else:
                    getattr(self, section)[key] = value

    def _validate(self) -> None:
        if self.heartbeat is None:
            self.errors.append(f"heartbeat: missing from the {self.host} base list")
        elif not HEARTBEAT_RANGE[0] <= self.heartbeat_seconds() <= HEARTBEAT_RANGE[1]:
            self.errors.append(f"heartbeat `{self.heartbeat}` is outside "
                               f"{HEARTBEAT_RANGE[0]}-{HEARTBEAT_RANGE[1]} s")
        for alias, target in self.aliases.items():
            if alias in self.catalog or alias == INHERIT:
                self.errors.append(f"alias `{alias}` is also a model id: remove one")
            elif target not in self.catalog:
                self.errors.append(f"alias `{alias}` points to `{target}`, "
                                   f"not in the {self.host} catalog")
        for role in ROLES:
            value = self.roles.get(role)
            if value is None:
                self.roles[role], self.source[role] = INHERIT, "default"
            elif not self.known(value):
                self.errors.append(f"role `{role}`: `{value}` is not in the {self.host} catalog "
                                   f"(exact ids only; run `chantier models` and ask the user)")
            level = self.effort.get(role)
            if level is not None and level != INHERIT and level not in EFFORTS:
                self.errors.append(f"effort `{role}`: `{level}` is not one of "
                                   f"{', '.join(EFFORTS)} or {INHERIT}")
            if not self.tools.get(role):
                self.errors.append(f"tools `{role}`: missing from the {self.host} base list")

    def heartbeat_seconds(self) -> int:
        m = HEARTBEAT.match(self.heartbeat or "")
        if not m:
            raise ChantierError("no valid heartbeat: run `chantier models check`", EXIT_PRECONDITION)
        return int(m["n"]) * (60 if m["unit"] == "m" else 1)

    def known(self, value: str) -> bool:
        return value == INHERIT or value in self.catalog or value in self.aliases

    def exact(self, value: str) -> str:
        """An exact catalog id, or `inherit`. Never a near match."""
        if value == INHERIT or value in self.catalog:
            return value
        if value in self.aliases:
            return self.aliases[value]
        raise ChantierError(f"`{value}` is not a {self.host} model id or declared alias "
                       f"(exact match only; ask the user, never pick a similar id)",
                       EXIT_PRECONDITION)

    def role(self, role: str) -> str:
        if role not in ROLES:
            raise ChantierError(f"unknown role `{role}` (roles: {', '.join(ROLES)})", EXIT_USAGE)
        return self.exact(self.roles[role])

    def effort_of(self, role: str) -> str | None:
        """The configured reasoning level, or None: the user's own setting applies."""
        level = self.effort.get(role)
        return None if level in (None, INHERIT) else level

    def tool_list(self, role: str) -> list[str]:
        return [t.strip() for t in self.tools.get(role, "").split(",") if t.strip()]

    def display(self, model_id: str) -> str | None:
        return self.catalog.get(model_id)

    def frontmatter_model(self, role: str) -> str | None:
        """The agent file's `model:` value for this host, or None to omit the line."""
        model_id = self.role(role)
        if self.host == "claude":
            return model_id
        if model_id == INHERIT:
            return None
        return f"[{self.display(model_id)}, {model_id}]"


# ---- the brief's Models line ----------------------------------------------------------------

def brief_overrides(brief: Path, models: Models) -> dict[tuple[str, str | None], str]:
    """`role=id` or `role@CR-n=id`, comma or space separated, after the `- Models` label."""
    if not brief.exists():
        return {}
    line = next((ln for ln in brief.read_text().splitlines()
                 if ln.lstrip().startswith("- Models")), None)
    if line is None:
        return {}
    rest = line.split("):", 1)[1] if "):" in line else line.split(":", 1)[-1]
    out: dict[tuple[str, str | None], str] = {}
    for entry in re.split(r"[,\s]+", rest.strip()):
        if not entry:
            continue
        m = BRIEF_ENTRY.match(entry)
        if not m:
            raise ChantierError(f"brief Models: `{entry}` is not `role=id` or `role@CR-n=id`",
                           EXIT_PRECONDITION)
        if m["role"] not in ROLES:
            raise ChantierError(f"brief Models: unknown role `{m['role']}`", EXIT_PRECONDITION)
        out[(m["role"], m["cr"])] = models.exact(m["model"])
    return out


def expected(models: Models, overrides: dict, role: str, cr: str | None) -> tuple[str, str]:
    """The exact model for one spawn, and where it comes from."""
    if cr and (role, cr) in overrides:
        return overrides[(role, cr)], f"brief {role}@{cr}"
    if (role, None) in overrides:
        return overrides[(role, None)], f"brief {role}"
    return models.role(role), f"{models.source[role]} {role}"


# ---- audit of the models a host actually ran ------------------------------------------------

def copilot_events(session: str) -> Path:
    home = Path(os.environ.get("COPILOT_HOME") or Path.home() / ".copilot").expanduser()
    return home / "session-state" / session / "events.jsonl"


def copilot_spawns(path: Path) -> list[dict]:
    """Every `subagent.started` of a chantier role: role, CR (from the name), model, source, and
    the effort its `subagent.configured` event (same agent id) reports."""
    if not path.exists():
        raise ChantierError(f"no Copilot event log at {path}", EXIT_PRECONDITION)
    spawns = []
    efforts: dict[str, str | None] = {}
    for line in path.open():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "subagent.configured":
            efforts[e.get("agentId")] = (e.get("data") or {}).get("reasoningEffort")
            continue
        if e.get("type") != "subagent.started":
            continue
        d = e.get("data") or {}
        role = d.get("agentType") or d.get("agentName")
        if role not in ROLES:
            continue
        name = f"{d.get('agentDisplayName', '')} {d.get('agentDescription', '')}"
        cr = CR_IN_NAME.search(name)
        spawns.append({"role": role, "cr": cr.group(0) if cr else None,
                       "model": d.get("model"), "selection": d.get("modelSelectionSource"),
                       "agent": e.get("agentId"), "name": d.get("agentDisplayName", "")})
    for s in spawns:
        s["effort"] = efforts.get(s["agent"])
    return spawns


def copilot_session(path: Path) -> dict:
    """The session's own model calls (not its subagents'), counted per (model, effort), and the
    prompts it has scheduled with `/every`: the Foreman's runtime facts."""
    if not path.exists():
        raise ChantierError(f"no Copilot event log at {path}", EXIT_PRECONDITION)
    calls: dict[tuple[str | None, str | None], int] = {}
    schedules: list[dict] = []
    for line in path.open():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        d = e.get("data") or {}
        if e.get("type") == "session.usage_record" and not e.get("agentId"):
            u = d.get("usage") or {}
            key = (u.get("model"), u.get("reasoningEffort"))
            calls[key] = calls.get(key, 0) + 1
        elif e.get("type") == "session.schedule_created":
            schedules.append({"id": d.get("id"), "prompt": d.get("prompt", ""),
                              "interval_ms": d.get("intervalMs"),
                              "recurring": d.get("recurring")})
        elif e.get("type") == "session.schedule_cancelled":
            schedules = [s for s in schedules if s["id"] != d.get("id")]
    return {"calls": calls, "schedules": schedules}

"""The optional `chantier.yaml` of a project: read, validated and resolved here, never by an agent.

The CLI has no dependency, so the file is read as a strict subset of YAML (block mappings,
scalars, lists of scalars, comments); anything outside it is refused with its line. A role's
model is turned into an exact identifier by the table below, and an unknown or ambiguous name
is refused: the parent that starts an agent passes the value as printed, never one it read or
completed itself. The CLI knows no role: the roles are the plugin's agent files, which the
caller lists.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

FILE = "chantier.yaml"
ROLE_KEYS = ("agent", "model", "skills", "tools")
PRICE_NAMES = ("input", "cache_write_5m", "cache_write_1h", "cache_read", "output")
HOST_NAMES = {"claude": "Claude Code", "copilot": "Copilot"}
HOST_FILES = {"claude": "claude-code", "copilot": "copilot"}


# ---- the model table: the only source of a model's identifier ---------------------------------

@dataclass(frozen=True)
class Model:
    id: str     # the exact identifier the host's agent files name
    name: str   # the display name
    start: str  # the value a start of an agent takes on this host


# Seeded from the plugin's agent files (a test checks they cannot drift). A new role model reaches
# the table by a release; a new model's price does not need one: a project sets it under `prices:`
# in `chantier.yaml`, above the built-in `costs.PRICE`.
MODELS = {
    "claude": (
        Model("claude-opus-5-5", "Claude Opus 5.5", "opus"),
        Model("claude-sonnet-5-5", "Claude Sonnet 5.5", "sonnet"),
        Model("claude-haiku-5-5", "Claude Haiku 5.5", "haiku"),
    ),
    "copilot": (
        Model("claude-opus-5.5", "Claude Opus 5.5", ""),
        Model("claude-sonnet-5.5", "Claude Sonnet 5.5", ""),
        Model("gpt-5.6-luna", "GPT-5.6 Luna", ""),
        Model("gpt-6.1-sol", "GPT-6.1 Sol", ""),
    ),
}
# Whether a start of an agent takes a model on this host: only what the host's reference marks
# proved (hosts/claude-code.md, hosts/copilot.md, row "Models").
SETS_MODEL_AT_START = {"claude": True, "copilot": False}
# The model an escalated task starts on (concepts.md, "Escalation"): one per host, the same for
# every role, kept next to MODELS so a release changes both. None where a start sets no model.
ESCALATION = {"claude": "claude-opus-5-5", "copilot": None}


def normalise(name: str) -> str:
    """Lower case; every run of characters other than letters and digits becomes one `-`."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _shown(models) -> str:
    return ", ".join(f"{m.id} ({m.name})" for m in models)


def resolve(host: str, name: str) -> tuple[Model | None, str | None]:
    """One model of the host's table, or the reason there is none."""
    wanted = normalise(name)
    models = MODELS[host]
    if not re.search("[a-z]", wanted):
        return None, f'model "{name}": name the model, not only its version'
    found = [m for m in models if wanted in (normalise(m.id), normalise(m.name))]
    if not found:
        parts = wanted.split("-")
        found = [m for m in models if _contains(normalise(m.id).split("-"), parts)]
    if len(found) == 1:
        return found[0], None
    if not found:
        return None, f'model "{name}" is unknown on {HOST_NAMES[host]}; known: {_shown(models)}'
    return None, f'model "{name}" is ambiguous on {HOST_NAMES[host]}: it matches {_shown(found)}'


def _contains(parts: list[str], run: list[str]) -> bool:
    """`run` is a contiguous run of whole parts of `parts`."""
    return any(parts[i:i + len(run)] == run for i in range(len(parts) - len(run) + 1))


# ---- the YAML subset ---------------------------------------------------------------------------

class YamlError(Exception):
    def __init__(self, line: int, message: str):
        super().__init__(message)
        self.line, self.message = line, message


@dataclass
class Node:
    kind: str    # "scalar", "list", "map" or "null"
    line: int
    value: object = None  # scalar: str; list: [Node]; map: {key: (key line, Node)}


@dataclass
class _Token:
    indent: int
    text: str
    line: int


_KEY = re.compile(r"^([A-Za-z0-9_.-]+):(?:[ ]+(.*))?$")


def _strip_comment(s: str) -> str:
    quote = None
    i = 0
    while i < len(s):
        ch = s[i]
        if quote:
            if quote == '"' and ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "'\"" and (i == 0 or s[i - 1] in " [,"):
            quote = ch
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            return s[:i]
        i += 1
    return s


def _tokens(text: str) -> list[_Token]:
    out = []
    for number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        lead = raw[:len(raw) - len(raw.lstrip(" \t"))]
        body = _strip_comment(raw[len(lead):]).rstrip()
        if not body:
            continue
        if "\t" in lead:
            raise YamlError(number, "a tab in the indentation: indent with spaces")
        if body in ("---", "...") or body.startswith(("--- ", "... ")):
            raise YamlError(number, "several documents (`---`) are not accepted: one document")
        out.append(_Token(len(lead), body, number))
    return out


def _is_item(text: str) -> bool:
    return text == "-" or text.startswith("- ")


def _scalar(text: str, line: int) -> Node:
    text = text.strip()
    if not text:
        raise YamlError(line, "an empty value")
    head = text[0]
    if head in "&*!":
        raise YamlError(line, f"anchors, aliases and tags are not accepted: found `{text[:20]}`")
    if head in "|>":
        raise YamlError(line, "block scalars (`|`, `>`) are not accepted: write the value on the line")
    if head in "{}":
        raise YamlError(line, "flow mappings (`{}`) are not accepted: use a block mapping")
    if head == "[":
        raise YamlError(line, "a list inside a list is not accepted")
    if head == '"':
        return Node("scalar", line, _double(text, line))
    if head == "'":
        if len(text) < 2 or text[-1] != "'" or re.search(r"(?<!')'(?!')", text[1:-1]):
            raise YamlError(line, f"a single-quoted value is not closed or has text after it: {text}")
        return Node("scalar", line, text[1:-1].replace("''", "'"))
    if ": " in text or text.endswith(":"):
        raise YamlError(line, f"a plain value cannot hold `: `; quote it: {text}")
    return Node("scalar", line, text)


def _double(text: str, line: int) -> str:
    out, i = [], 1
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            if text[i + 1:i + 2] not in ('"', "\\"):
                raise YamlError(line, 'in double quotes only \\" and \\\\ are accepted')
            out.append(text[i + 1])
            i += 2
            continue
        if ch == '"':
            if text[i + 1:].strip():
                raise YamlError(line, f"text after the closing quote: {text[i + 1:].strip()}")
            return "".join(out)
        out.append(ch)
        i += 1
    raise YamlError(line, f"a double-quoted value is not closed: {text}")


def _flow_list(text: str, line: int) -> Node:
    if not text.endswith("]"):
        raise YamlError(line, "a flow list ends with `]` on its line")
    inner = text[1:-1]
    if not inner.strip():
        return Node("list", line, [])
    items, quote, start, i = [], None, 0, 0
    while i <= len(inner):
        ch = inner[i] if i < len(inner) else ","
        if quote:
            if quote == '"' and ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "'\"" and (i == 0 or inner[i - 1] in " ["):
            quote = ch
        elif ch == ",":
            piece = inner[start:i].strip()
            if not piece:
                raise YamlError(line, "an empty item in a flow list")
            items.append(_scalar(piece, line))
            start = i + 1
        i += 1
    return Node("list", line, items)


def _inline(text: str, line: int) -> Node:
    text = text.strip()
    return _flow_list(text, line) if text.startswith("[") else _scalar(text, line)


def _block(toks: list[_Token], i: int, indent: int) -> tuple[Node, int]:
    return (_list if _is_item(toks[i].text) else _map)(toks, i, indent)


def _list(toks: list[_Token], i: int, indent: int) -> tuple[Node, int]:
    first, items = toks[i].line, []
    while i < len(toks) and toks[i].indent == indent and _is_item(toks[i].text):
        rest = toks[i].text[1:].strip()
        if not rest:
            raise YamlError(toks[i].line, "a list item needs a value on its line")
        items.append(_scalar(rest, toks[i].line))
        i += 1
    if i < len(toks) and toks[i].indent > indent:
        raise YamlError(toks[i].line, "unexpected indentation")
    return Node("list", first, items), i


def _map(toks: list[_Token], i: int, indent: int) -> tuple[Node, int]:
    first, entries = toks[i].line, {}
    while i < len(toks) and toks[i].indent == indent:
        t = toks[i]
        if _is_item(t.text):
            raise YamlError(t.line, "a list item where a `key: value` is expected")
        m = _KEY.match(t.text)
        if not m:
            raise YamlError(t.line, f"expected `key: value`, found: {t.text}")
        key = m[1]
        if key in entries:
            raise YamlError(t.line, f"duplicate key `{key}` (first at line {entries[key][0]})")
        rest = (m[2] or "").strip()
        i += 1
        if rest:
            node = _inline(rest, t.line)
        elif i < len(toks) and toks[i].indent > indent:
            node, i = _block(toks, i, toks[i].indent)
        elif i < len(toks) and toks[i].indent == indent and _is_item(toks[i].text):
            node, i = _list(toks, i, indent)
        else:
            node = Node("null", t.line)
        entries[key] = (t.line, node)
    if i < len(toks) and toks[i].indent > indent:
        raise YamlError(toks[i].line, "unexpected indentation")
    return Node("map", first, entries), i


def parse(text: str) -> Node:
    toks = _tokens(text)
    if not toks:
        return Node("map", 1, {})
    node, i = _block(toks, 0, toks[0].indent)
    if i < len(toks):
        raise YamlError(toks[i].line, "unexpected indentation")
    return node


# ---- validation and resolution -----------------------------------------------------------------

def default_agent(host: str, role: str) -> str:
    return f"chantier:{role}" if host == "claude" else f"chantier-{role}"


def load(path: Path, host: str, roles: list[str]) -> tuple[dict | None, list[str]]:
    """`(None, [])` when the file is absent; else the resolved playbook and the problems found
    (each `chantier.yaml:<line>: ...`, in line order). `roles` are the plugin's, for this host."""
    if not path.is_file():
        return None, []
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        return None, [f"{FILE}:1: cannot read the file as UTF-8: {e}"]
    try:
        tree = parse(text)
    except YamlError as e:
        return None, [f"{FILE}:{e.line}: {e.message}"]
    if tree.kind != "map":
        return None, [f"{FILE}:{tree.line}: the file is a mapping: `roles:` then one entry per role"]
    problems: list[tuple[int, str]] = []

    def bad(line: int, message: str):
        problems.append((line, message))

    resolved: dict[str, dict] = {}
    prices: dict[str, dict] = {}
    for key, (kline, node) in tree.value.items():
        if key == "prices":
            prices = _prices(node, kline, bad)
            continue
        if key != "roles":
            bad(kline, f'unknown key "{key}": the top-level keys are "roles" and "prices"')
            continue
        if node.kind != "map" or not node.value:
            bad(kline, '"roles" holds one entry per role: `<role>:` then its keys')
            continue
        if not roles:
            bad(kline, f"no plugin agent found for {HOST_NAMES[host]}: the roles cannot be checked")
            continue
        for role, (rline, rnode) in node.value.items():
            if role not in roles:
                bad(rline, f'role "{role}" is not one of the plugin\'s agents: {", ".join(roles)}')
                continue
            if rnode.kind != "map" or not rnode.value:
                bad(rline, f'role "{role}" is empty: set one of {", ".join(ROLE_KEYS)}')
                continue
            resolved[role] = _role(host, role, rnode, bad)
    problems.sort(key=lambda p: p[0])
    lines = [f"{FILE}:{n}: {m}" for n, m in problems]
    return ({"file": FILE, "host": host, "roles": resolved, "prices": prices}
            if not lines else None), lines


def _number(node: Node) -> float | None:
    """A non-negative finite number from a scalar, else None."""
    if node.kind != "scalar":
        return None
    try:
        value = float(node.value)
    except ValueError:
        return None
    return value if math.isfinite(value) and value >= 0 else None


def _five(node: Node, line: int, where: str, bad, tier: bool) -> dict | None:
    """The five prices of an entry (or of its `long_context`, which also has `above`), or None
    when a value is wrong or one is missing: none is derived from another."""
    need = PRICE_NAMES + (("above",) if tier else ())
    keys = need if tier else need + ("long_context",)
    rec: dict = {}
    ok = True
    for key, (kline, value) in node.value.items():
        if key not in keys:
            bad(kline, f'{where}: unknown key "{key}": one of {", ".join(keys)}')
            ok = False
        elif key == "long_context":
            found = _five(value, kline, f"{where}: long_context", bad, True) \
                if value.kind == "map" and value.value else None
            if found:
                rec[key] = found
            else:
                if value.kind != "map" or not value.value:
                    bad(kline, f"{where}: long_context holds `above` and the five prices")
                ok = False
        elif (number := _number(value)) is None:
            bad(kline, f'{where}: "{key}" is a number, not negative')
            ok = False
        else:
            rec[key] = number
    absent = [k for k in need if k not in node.value]
    if absent:
        bad(line, f"{where}: missing {', '.join(absent)} (all five prices are required, "
            "none is derived from another)")
    return rec if ok and not absent else None


def _prices(node: Node, kline: int, bad) -> dict[str, dict]:
    """`prices:` one entry per exact model id, in $/MTok."""
    if node.kind != "map" or not node.value:
        bad(kline, '"prices" holds one entry per model id: `<id>:` then its five prices')
        return {}
    out: dict[str, dict] = {}
    for model, (mline, mnode) in node.value.items():
        if mnode.kind != "map" or not mnode.value:
            bad(mline, f'prices: "{model}" is empty: set {", ".join(PRICE_NAMES)}')
            continue
        found = _five(mnode, mline, f'prices: "{model}"', bad, False)
        if found:
            out[model] = found
    return out


def _role(host: str, role: str, node: Node, bad) -> dict:
    rec: dict = {}
    for key, (kline, value) in node.value.items():
        if key not in ROLE_KEYS:
            bad(kline, f'role "{role}": unknown key "{key}": one of {", ".join(ROLE_KEYS)}')
        elif key in ("agent", "model"):
            if value.kind != "scalar" or not value.value.strip():
                bad(kline, f'role "{role}": "{key}" is one string')
            elif key == "agent":
                if re.search(r"\s", value.value):
                    bad(kline, f'role "{role}": agent "{value.value}" holds whitespace')
                else:
                    rec["agent"] = value.value
            else:
                found, why = resolve(host, value.value)
                if why:
                    bad(kline, f'role "{role}": {why}')
                elif not SETS_MODEL_AT_START[host]:
                    bad(kline, f'{HOST_NAMES[host]} cannot set a model when it starts an agent '
                        f'(hosts/{HOST_FILES[host]}.md, "Models"): remove "model" for {role}, or '
                        "run the role with your own agent that names it")
                else:
                    rec["model"] = {"id": found.id, "name": found.name, "start": found.start}
        else:
            if value.kind != "list" or not value.value:
                bad(kline, f'role "{role}": "{key}" is a list of names: `[a, b]` or `- a` lines')
            elif any(not n.value.strip() or re.search(r"\s", n.value) for n in value.value):
                bad(kline, f'role "{role}": a name in "{key}" is empty or holds whitespace')
            else:
                rec[key] = [n.value for n in value.value]
    return rec


# ---- what is printed ----------------------------------------------------------------------------

def _model_text(model: dict) -> str:
    return f"{model['start']} ({model['id']}, {model['name']})"


def _fields(rec: dict, agent: str | None, unset_model: bool) -> str:
    parts = [f"agent={agent}"] if agent else []
    if rec.get("model"):
        parts.append(f"model={_model_text(rec['model'])}")
    elif unset_model:
        parts.append("model=(its file's)")
    return " ".join(parts + [f"{k}={','.join(rec[k])}" for k in ("skills", "tools") if rec.get(k)])


def playbook_lines(resolved: dict | None, host: str, roles: list[str], recorded: str | None = None) -> list[str]:
    """The playbook, one line per role of the plugin, then one per need."""
    if resolved is None:
        head = "playbook: no chantier.yaml, the plugin's agents and models"
    elif recorded:
        head = f"playbook: {FILE} as {recorded} opened it, host {host}"
    else:
        head = f"playbook: {FILE}, valid, host {host}"
    lines = [head]
    configured = (resolved or {}).get("roles", {})
    for role in roles:
        rec = configured.get(role, {})
        lines.append(f"{role}: " + _fields(rec, rec.get("agent") or default_agent(host, role), True))
    if resolved and resolved.get("prices"):
        lines.append(f"prices: {', '.join(resolved['prices'])} ({FILE}, above the built-in table)")
        if host == "copilot":
            lines.append("prices: not used on Copilot, whose records carry the price")
    lines += [f"needs: {role}: " + "; ".join(f"{k} {', '.join(rec[k])}" for k in ("skills", "tools")
                                              if rec.get(k))
              for role, rec in configured.items() if rec.get("skills") or rec.get("tools")]
    return lines


def escalate_line(host: str) -> str:
    """The escalation model of the host, one for every role, or that there is none."""
    entry = ESCALATION.get(host)
    found = next((m for m in MODELS[host] if m.id == entry), None) if entry else None
    return f"escalate: {_model_text({'start': found.start, 'id': found.id, 'name': found.name})}" \
        if found else "escalate: (none on this host)"


def team_lines(resolved: dict | None) -> list[str]:
    """One `team:` line per configured role, with the keys set only."""
    if not resolved:
        return []
    return [f"team: {role} " + _fields(rec, rec.get("agent"), False)
            for role, rec in resolved.get("roles", {}).items()]

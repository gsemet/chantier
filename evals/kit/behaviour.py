"""The behaviour measure: what each role read and did, from your local Claude Code transcripts.

    python -I evals/kit/behaviour.py [--since <date or ISO time>] [--prune]
                                     [--projects <dir>] [--folders <glob>] [--out <dir>]

Reads the user's Claude Code transcripts (`<projects>/<folder>/<session>.jsonl` and the subagents'
`<session>/subagents/agent-<id>.jsonl` with their `.meta.json`), one run per file, line by line,
and writes in `--out` (default `evals/results/`) a JSON and a Markdown file,
`behaviour-<date>-v<X.Y.Z>.json` and `.md`: per role, the card bytes read, the files read, the
CLI's usage errors and refusals, the `--help` and `help <topic>` reads, the host's denials, the
write guard's refusals, the waits, the tools not in the role's list and the pushes; across roles,
the Drivers' runs per CR and the wake shares of the Foreman and the Chief of Staff; then each
detector's rate (`detectors.json`, a regex on tool calls), the S-list (a usage error or refusal seen
in more than 2 % of a role's runs) and the regressions against the previous results file. It is
for your machine, never for CI: the transcripts are local. Nothing leaves it: no network, no model.

The results hold counts and message templates only: no transcript text, path, session or agent id
or project folder name. Before writing, a privacy guard refuses (exit 1, nothing written, the JSON
key paths named, the value never printed) a result that holds the home folder's path or the login
name.

- `--projects`: the transcripts' root; default `$CLAUDE_CONFIG_DIR/projects`, else `~/.claude/projects`.
- `--folders <glob>`: keep only the project folders whose name matches.
- `--since`: an ISO date (read as 00:00 UTC) or an ISO time; files and records older are skipped.
  Default: the `written` time of the latest results file in `--out`, or exit 2 when there is none.
- `--prune`: reads no transcript, writes nothing; prints the deletion candidates (a detector with no
  floor and no match, a help topic never read) from the two latest results files.

The role of a run, the first rule that applies: the `agentType` of its `.meta.json` when it is
`chantier:<role>`; the first line of its first prompt (`chantier Foreman n°`, or the kit's
`audit.PROMPT` / `audit.QA_PROMPT`); a main session's first `Skill` call of the Chief of Staff or
the Griller; else it is not a chantier role (counted once, measured no further).

Exit codes, as the kit's other tools: 0 written, 1 a privacy refusal, 2 usage, 4 external (git).
Standard library only; POSIX and Windows.
"""
from __future__ import annotations

import argparse
import datetime
import fnmatch
import getpass
import json
import os
import re
import statistics
import subprocess
import sys
import tomllib
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import audit  # noqa: E402  (the first-line forms of the roles' prompts)

OK, PRIVACY, USAGE, EXTERNAL = 0, 1, 2, 4
DETECTORS = HERE / "detectors.json"
TOPICS = ROOT / "skills" / "chantier" / "references" / "topics.json"
SHELLS = {"Bash", "PowerShell"}
WAIT_TOOLS = {"Monitor", "TaskStop", "TaskOutput", "BashOutput"}
S_LINE = 2.0  # percent of a role's runs above which a message is an S-list line
REGRESSION = 5.0  # points a detector's rate may rise before it is a regression
CHIEF_SKILLS = {"chantier:chief-of-staff": "chief-of-staff", "chief-of-staff": "chief-of-staff",
                "chantier:griller": "griller", "griller": "griller"}
GLOBAL_VALUE = {"--project", "--profile", "--skill", "--batch", "--host", "--session"}
CHANTIER_SKILLS = sorted(p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md"))

CARD = re.compile(r"skills/chantier/references(?:/([^\s\"'`<>|;&(),*?]+))?")
CARD_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)*")
TOPIC = re.compile(r"[a-z][a-z0-9-]*")
SKILL = re.compile(r"skills/(" + "|".join(map(re.escape, CHANTIER_SKILLS)) + r")/SKILL\.md")
BRIEF = re.compile(r"chantier/briefs/")
TASK_OUTPUT = re.compile(r"[/\\]tasks[/\\][^\s\"']+\.output")
SLEEP = re.compile(r"(?:^|[;&|(\s])(?:sleep|Start-Sleep)\b", re.I)
LEASE_PUSH = re.compile(r"\bgit\b[^\n;&|]*\bpush\b[^\n;&|]*--force-with-lease")
ASSIGN = re.compile(r"(?:^|[;&]\s*)(?:export\s+|local\s+|set\s+)?\$?(?:env:)?\{?([A-Za-z_]\w*)\}?\s*=\s*(.*chantier.*)$",
                    re.M)
VARIABLE = re.compile(r"^&?\$(?:\{)?(?:env:)?(\w+)\}?$")
TOKEN = re.compile(r"\"[^\"]*\"|'[^']*'|\S+")

# the host's own texts (not a published format: the fixture pins each one)
CLASSIFIER = re.compile(r"denied by the Claude Code auto mode classifier")
MODE_DENIED = re.compile(r"Permission to use \S+ has been denied")
BLOCKED_SLEEP = re.compile(r"^\s*Blocked: sleep", re.M)
BLOCKED = re.compile(r"^\s*Blocked: ", re.M)
USER_REJECTED = re.compile(r"The user doesn't want to (?:proceed|take this action)|"
                           r"Request interrupted by user for tool use|tool use was rejected")
WRITE_GUARD = re.compile(r"refused: .*outside the folders this agent may write in")
NO_SUCH_TOOL = re.compile(r"No such tool available: (\w+)")
USAGE_ERROR = re.compile(r"^[^\n:]+: error: .+$", re.M)
REFUSAL = re.compile(r"^error: (.+)$", re.M)
WAKE_COMPACTION = "This session is being continued from a previous conversation"
WAKE_KINDS = ["compaction", "agent_ended", "watcher", "heartbeat", "foreman_turn_ended", "skill", "typed"]


class Usage(Exception):
    """A bad argument or a bad detector: exit 2, with the text."""


class External(Exception):
    """A git read failed: exit 4, with the tool's own text."""


# ---- reading the arguments ----------------------------------------------------------------------

def parse_since(text: str) -> datetime.datetime:
    try:
        when = datetime.datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        raise Usage(f"--since {text!r} is not an ISO date (2026-11-17) or time (2026-11-25T03:12Z)") from None
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    return when.astimezone(datetime.timezone.utc)


def stamp(when: datetime.datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---- the detectors ------------------------------------------------------------------------------

class Detector:
    def __init__(self, raw: dict):
        self.id = raw["id"]
        self.rule = raw.get("rule", "")
        self.floor = raw.get("floor")
        self.roles = raw.get("roles", "all")
        self.except_roles = set(raw.get("except", []))
        self.tools = set(raw.get("tools", SHELLS))
        self.positive = raw.get("positive", "")
        self.negative = raw.get("negative", "")
        try:
            self.rx = re.compile(raw["pattern"], re.I | re.M)
        except (re.error, KeyError) as error:
            raise Usage(f"detector {self.id}: the pattern does not compile: {error}") from None

    def applies(self, role: str) -> bool:
        if role in self.except_roles:
            return False
        return self.roles == "all" or role in self.roles


def load_detectors(path: Path = DETECTORS) -> list[Detector]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        raws = data["detectors"]
        if data.get("schema") != 1:
            raise ValueError("schema is not 1")
        if not all(isinstance(r, dict) and "id" in r for r in raws):
            raise ValueError("a detector has no id")
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise Usage(f"{path.name}: not read: {error}") from None
    return [Detector(r) for r in raws]


# ---- message templates --------------------------------------------------------------------------

URL = re.compile(r"https?://\S+")
PATHS = [re.compile(r"[A-Za-z]:[\\/][^\s'\"`),;]*"), re.compile(r"~[\\/][^\s'\"`),;]*"),
         re.compile(r"(?<![\w/<:])/[\w.@~+-][^\s'\"`),;]*")]
RELPATH = re.compile(r"(?<![\w<>/\\.-])[\w.-]*(?:[/\\][\w.<>-]+)+")
UNRECOGNIZED = re.compile(r"(unrecognized arguments: )(.*)")
PROJECTS = re.compile(r"(projects )[\w, -]+:")
HEX = re.compile(r"\b(?=[0-9a-f]*\d)[0-9a-f]{7,40}\b")
SINGLE = re.compile(r"(?<!\w)'[^'\n]*'(?!\w)")
DOUBLE = re.compile(r"\"[^\"\n]*\"")


def scrub(text: str) -> str:
    """The login name, as a bare word, replaced: no template holds it."""
    try:
        login = getpass.getuser()
    except (KeyError, OSError, ImportError):
        return text
    return re.sub(rf"(?<!\w){re.escape(login)}(?!\w)", "<user>", text, flags=re.I) if len(login) >= 3 else text


def template(message: str) -> str:
    """A message cut to its first line, with what varies replaced; backticked names stay."""
    line = next((x for x in message.splitlines() if x.strip()), "").strip()
    line = URL.sub("<url>", line)
    for rx in PATHS:
        line = rx.sub("<path>", line)
    line = RELPATH.sub("<path>", line)
    line = UNRECOGNIZED.sub(lambda m: m[1] + " ".join(t if t.startswith("--") else "<v>" for t in m[2].split()), line)
    line = re.sub(r"(?:<v> ?){2,}", "<v>... ", line)
    line = PROJECTS.sub(r"\1<names>:", line)
    line = re.sub(r"\bCR-\d+", "CR-<n>", line)
    line = re.sub(r"\bbatch-\d+", "batch-<n>", line)
    line = scrub(line)
    line = re.sub(r"«[^»\n]*»?", "<v>", line)
    line = re.sub(r"\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b", "<id>", line)
    line = re.sub(r"\b(?:\d+-)?[a-z0-9]+(?:-[a-z0-9]+){2,}(?= is not\b)", "<slug>", line)
    line = HEX.sub("<sha>", line)
    line = re.sub(r"(could not apply <sha>\.\.\.).*", r"\1", line)
    line = SINGLE.sub("<v>", line)
    line = DOUBLE.sub("<v>", line)
    line = re.sub(r"(?<![\w<-])\d+(?![\w>])", "<n>", line)
    return line[:160]


# ---- one command --------------------------------------------------------------------------------

def unquote(token: str) -> str:
    return token[1:-1] if len(token) > 1 and token[0] == token[-1] and token[0] in "\"'" else token


def cli_calls(command: str, names: set[str]) -> list[list[str]]:
    """The arguments after `chantier`, one list per chantier call of a shell command: a segment
    whose first word is `chantier`, `uv run ... chantier`, `uvx ... chantier`, or `$NAME` that the
    run set to a value holding `chantier`. Also records the variables the command sets."""
    for m in ASSIGN.finditer(command):
        names.add(m[1])
    found = []
    for segment in re.split(r"&&|\|\||[;|\n]", command):
        tokens = TOKEN.findall(segment.strip())
        while tokens and re.match(r"^\w+=", tokens[0]):
            if tokens[0].count('"') % 2 or tokens[0].count("'") % 2:
                tokens = []  # an assignment of a quoted several words: not a call
                break
            tokens = tokens[1:]
        while tokens and unquote(tokens[0]) in ("&", "call", "env", "time", "command"):
            tokens = tokens[1:]
        if not tokens or (len(tokens) > 1 and tokens[1] == "="):
            continue
        first = unquote(tokens[0])
        base = re.split(r"[\\/]", first)[-1].removesuffix(".exe")
        if base == "chantier":
            found.append(tokens[1:])
            continue
        var = VARIABLE.match(first)
        if var and var[1] in names:
            found.append(tokens[1:])
        elif base in ("uv", "uvx"):
            plain = [unquote(t) for t in tokens]
            if "chantier" in plain:
                found.append(tokens[plain.index("chantier") + 1:])
        elif base in ("python", "python3", "py") and [unquote(t) for t in tokens[1:3]] == ["-m", "chantier"]:
            found.append(tokens[3:])
    return found


def words_of(args: list[str]) -> list[str]:
    """The command words of a chantier call, past the global options and their values."""
    words, skip = [], False
    for token in (unquote(t) for t in args):
        if skip:
            skip = False
        elif token in GLOBAL_VALUE:
            skip = True
        elif not token.startswith("-"):
            words.append(token)
    return words


def card_names(text: str) -> list[str]:
    """The cards a path or a command names, in order of appearance (`references/` when only the folder)."""
    text = text.replace("\\", "/")
    hits = []
    for rx, key in ((CARD, lambda m: (m[1] or "references/").rstrip(".,:")),
                    (SKILL, lambda m: f"SKILL.md:{m[1]}"), (BRIEF, lambda m: "brief")):
        hits += [(m.start(), key(m)) for m in rx.finditer(text)]
    return [safe_card(name) for _, name in sorted(hits)]


def safe_card(key: str) -> str:
    """A card key is a path relative to `references/` (one word per folder), `references/`, `SKILL.md:<skill>`
    or `brief`; whatever else (a path of a home folder, a glob, a prompt file) is `other-card`, never raw."""
    if key in ("references/", "brief") or (key.startswith("SKILL.md:") and key[9:] in CHANTIER_SKILLS):
        return key
    return key if CARD_KEY.fullmatch(key) else "other-card"


# ---- one run ------------------------------------------------------------------------------------

class Run:
    def __init__(self, main: bool, folder: str, meta_type: str | None):
        self.main, self.folder, self.meta_type = main, folder, meta_type
        self.first_line: str | None = None
        self.skill_role: str | None = None
        self.calls: set[str] = set()
        self.msgs: set[str] = set()
        self.pending: dict[str, dict] = {}
        self.names: set[str] = set()
        self.cards: Counter = Counter()
        self.read_paths: set[str] = set()
        self.card_keys: set[str] = set()
        self.cli = 0
        self.usage: Counter = Counter()
        self.refusals: Counter = Counter()
        self.help_commands: Counter = Counter()
        self.help_topics: Counter = Counter()
        self.denials: Counter = Counter()
        self.guard = 0
        self.waits = 0
        self.not_in_list: Counter = Counter()
        self.pushes = self.pushes_refused = self.lease = self.lease_denied = 0
        self.detected: set[str] = set()
        self.first: str | None = None
        self.last: str | None = None
        self.wake = "typed"
        self.wake_weight: Counter = Counter()
        self.msg_weight: dict[str, tuple[str, float]] = {}

    @property
    def tool_calls(self) -> int:
        return len(self.calls)

    def finish(self) -> None:
        self.model_calls = len(self.msgs)
        self.msgs, self.pending, self.msg_weight = set(), {}, {}


def weight(usage: dict) -> float:
    return (usage.get("input_tokens") or 0) + 1.25 * (usage.get("cache_creation_input_tokens") or 0) \
        + 0.1 * (usage.get("cache_read_input_tokens") or 0) + 5 * (usage.get("output_tokens") or 0)


def wake_kind(text: str) -> str:
    if WAKE_COMPACTION in text:
        return "compaction"
    if "<task-notification>" in text:
        return "watcher" if re.search(r"chantier[^<\n]*\bwatch\b", text) else "agent_ended"
    if "<<autonomous-loop" in text or text.lstrip().startswith("/loop") or "<command-name>/loop<" in text:
        return "heartbeat"
    if "finished a turn" in text:
        return "foreman_turn_ended"
    if text.lstrip().startswith("Base directory for this skill"):
        return "skill"
    return "typed"


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and isinstance(b.get("text", ""), str))


def denial_kind(text: str) -> str | None:
    if len(text) >= 2000:
        return None
    for kind, rx in (("classifier", CLASSIFIER), ("mode", MODE_DENIED), ("sleep", BLOCKED_SLEEP),
                     ("blocked_other", BLOCKED), ("user_rejected", USER_REJECTED)):
        if rx.search(text):
            return kind
    return None


def on_tool_use(run: Run, block: dict, detectors: list[Detector]) -> None:
    tid, name = block.get("id"), block.get("name")
    if tid in run.calls or not isinstance(name, str):
        return
    run.calls.add(tid)
    args = block.get("input") if isinstance(block.get("input"), dict) else {}
    info: dict = {"cards": [], "cli": False, "push": False, "lease": False}
    command = args.get("command") if name in SHELLS and isinstance(args.get("command"), str) else None
    if name == "Read" and isinstance(args.get("file_path"), str):
        run.read_paths.add(args["file_path"])
        info["cards"] = card_names(args["file_path"])
        if TASK_OUTPUT.search(args["file_path"]):
            run.waits += 1
    elif name == "Grep" and isinstance(args.get("path"), str):
        info["cards"] = card_names(args["path"])
    elif name == "Skill" and run.main and run.skill_role is None:
        run.skill_role = CHIEF_SKILLS.get(str(args.get("skill")))
    if name in WAIT_TOOLS:
        run.waits += 1
    if command is not None:
        info["cards"] = card_names(command)
        if SLEEP.search(command) or TASK_OUTPUT.search(command):
            run.waits += 1
        info["lease"] = bool(LEASE_PUSH.search(command))
        run.lease += info["lease"]
        for d in detectors:
            if name in d.tools and d.rx.search(command):
                run.detected.add(d.id)
        for call in cli_calls(command, run.names):
            run.cli += 1
            info["cli"] = True
            words = words_of(call)
            plain = [unquote(t) for t in call]
            if words and words[0] == "help":
                topic = words[1] if len(words) > 1 and TOPIC.fullmatch(words[1]) else (
                    "(none)" if len(words) < 2 else "other")
                run.help_topics[topic] += 1
                info["cards"].append(f"help:{topic}")
            elif words and words[0] == "brief":
                info["cards"].append("brief")
            elif "--help" in plain or "-h" in plain:
                run.help_commands[" ".join(w for w in words[:2] if re.fullmatch(r"[a-z][a-z-]*", w))] += 1
            if words and words[0] == "push":
                info["push"] = True
    run.pending[tid] = info
    run.pushes += info["push"]


def on_tool_result(run: Run, block: dict) -> None:
    info = run.pending.pop(block.get("tool_use_id"), None)
    text = text_of(block.get("content"))
    failed = bool(block.get("is_error"))
    kind = denial_kind(text)
    if kind:
        run.denials[kind] += 1
    if len(text) < 2000:
        if WRITE_GUARD.search(text):
            run.guard += 1
        m = NO_SUCH_TOOL.search(text)
        if m:
            run.not_in_list[m[1]] += 1
    if info is None:
        return
    if info["cards"] and not failed and not kind:
        run.cards[info["cards"][0]] += len(text.encode("utf-8"))
        run.card_keys.update(c for c in info["cards"] if not c.startswith("help:"))
    refused = bool(kind)
    if info["cli"]:
        head = text[:4000]
        if "usage: chantier" in head and (m := USAGE_ERROR.search(head)):
            run.usage[template(m[0])] += 1
            refused = True
        elif m := REFUSAL.search(head):
            run.refusals[template(m[1])] += 1
            refused = True
    if info["push"] and refused:
        run.pushes_refused += 1
    if info["lease"] and kind:
        run.lease_denied += 1


def on_record(run: Run, rec: dict, detectors: list[Detector], since: str) -> None:
    kind, msg = rec.get("type"), rec.get("message")
    if kind not in ("user", "assistant") or not isinstance(msg, dict):
        return
    when = rec.get("timestamp")
    if isinstance(when, str):
        if when[:19] < since:
            return
        run.first = when if run.first is None or when < run.first else run.first
        run.last = when if run.last is None or when > run.last else run.last
    content = msg.get("content")
    if kind == "assistant":
        mid = msg.get("id")
        if isinstance(mid, str):
            run.msgs.add(mid)
            if run.main and isinstance(msg.get("usage"), dict):
                old = run.msg_weight.get(mid)
                if old:
                    run.wake_weight[old[0]] -= old[1]
                run.msg_weight[mid] = (run.wake, weight(msg["usage"]))
                run.wake_weight[run.wake] += run.msg_weight[mid][1]
        for block in content if isinstance(content, list) else []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                on_tool_use(run, block, detectors)
        return
    blocks = content if isinstance(content, list) else []
    results = [b for b in blocks if isinstance(b, dict) and b.get("type") == "tool_result"]
    for block in results:
        on_tool_result(run, block)
    if results:
        return
    text = text_of(content)
    if run.first_line is None:
        for part in ([text] if isinstance(content, str) else [b.get("text", "") for b in blocks if isinstance(b, dict)]):
            if isinstance(part, str) and part.strip() and not part.lstrip().startswith("<"):
                run.first_line = part.strip().splitlines()[0]
                break
    if run.main:
        run.wake = wake_kind(text)


def read_run(path: Path, main: bool, folder: str, meta_type: str | None, detectors: list[Detector],
             since: str) -> Run:
    run = Run(main, folder, meta_type)
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if '"user"' not in line and '"assistant"' not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict):
                on_record(run, rec, detectors, since)
    run.finish()
    return run


def role_of(run: Run) -> str | None:
    if run.meta_type and run.meta_type.startswith("chantier:"):
        return run.meta_type[len("chantier:"):]
    line = run.first_line or ""
    if line.startswith("chantier Foreman n°"):
        return "foreman"
    m = audit.PROMPT.match(line) or audit.QA_PROMPT.match(line)
    if m:
        return m["role"]
    return run.skill_role if run.main else None


# ---- the files ----------------------------------------------------------------------------------

def projects_root(given: str | None) -> Path:
    if given:
        return Path(given)
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(config) if config else Path.home() / ".claude") / "projects"


def transcripts(root: Path, glob: str | None):
    """(path, main, folder, meta_type) of every transcript under the root."""
    if not root.is_dir():
        return
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        if glob and not fnmatch.fnmatch(folder.name, glob):
            continue
        for path in sorted(folder.glob("*.jsonl")):
            yield path, True, folder.name, None
        for path in sorted(folder.glob("*/subagents/agent-*.jsonl")):
            meta = None
            try:
                meta = json.loads(path.with_name(path.stem + ".meta.json").read_text(encoding="utf-8")).get("agentType")
            except (OSError, ValueError, AttributeError):
                pass
            yield path, False, folder.name, meta if isinstance(meta, str) else None


# ---- the figures --------------------------------------------------------------------------------

def pct(part: float, whole: float) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


def counted(counter_per_run: list[Counter]) -> dict:
    """{template: {count, runs}} over the runs' counters."""
    total, runs = Counter(), Counter()
    for c in counter_per_run:
        total.update(c)
        runs.update(c.keys())
    return {k: {"count": total[k], "runs": runs[k]} for k in sorted(total, key=lambda k: (-total[k], k))}


def role_figures(runs: list[Run]) -> dict:
    n = len(runs)
    tools = [r.tool_calls for r in runs]
    cards = Counter()
    for r in runs:
        cards.update(r.cards)
    help_commands, help_topics, denials, missing = Counter(), Counter(), Counter(), Counter()
    for r in runs:
        help_commands.update(r.help_commands)
        help_topics.update(r.help_topics)
        denials.update(r.denials)
        missing.update(r.not_in_list)
    waits = sum(r.waits for r in runs)
    pushes = sum(r.pushes for r in runs)
    refused = sum(r.pushes_refused for r in runs)
    return {
        "runs": n,
        "tool_calls": {"total": sum(tools), "per_run_mean": mean(tools), "median": statistics.median(tools)},
        "model_calls": {"total": sum(r.model_calls for r in runs),
                        "per_run_mean": mean([r.model_calls for r in runs])},
        "card_bytes": {"total": sum(cards.values()), "per_run_mean": mean([sum(r.cards.values()) for r in runs]),
                       "by_card": dict(sorted(cards.items(), key=lambda kv: (-kv[1], kv[0])))},
        "files_read": {"paths_per_run_mean": mean([len(r.read_paths) for r in runs]),
                       "cards_per_run_mean": mean([len(r.card_keys) for r in runs])},
        "cli": {"calls": sum(r.cli for r in runs), "usage_errors": counted([r.usage for r in runs]),
                "refusals": counted([r.refusals for r in runs])},
        "help": {"commands": dict(sorted(help_commands.items())), "topics": dict(sorted(help_topics.items()))},
        "host_denials": dict(sorted(denials.items())),
        "write_guard_refusals": sum(r.guard for r in runs),
        "waits": {"count": waits, "share": pct(waits, sum(tools))},
        "tool_not_in_list": dict(sorted(missing.items())),
        "pushes": {"chantier_push": pushes, "refused": refused, "rate": pct(refused, pushes),
                   "force_with_lease": sum(r.lease for r in runs),
                   "force_with_lease_denied": sum(r.lease_denied for r in runs)},
    }


def driver_figures(runs: list[Run]) -> dict:
    per_cr: Counter = Counter()
    for r in runs:
        m = audit.PROMPT.match(r.first_line or "")
        if m and m["what"].startswith("CR-"):
            per_cr[(r.folder, m["what"])] += 1
    crs = len(per_cr)
    return {"crs": crs, "runs": sum(per_cr.values()), "mean": round(sum(per_cr.values()) / crs, 1) if crs else 0.0,
            "one": pct(sum(1 for v in per_cr.values() if v == 1), crs),
            "two": pct(sum(1 for v in per_cr.values() if v == 2), crs),
            "three_or_more": pct(sum(1 for v in per_cr.values() if v >= 3), crs)}


def wake_figures(runs: list[Run]) -> dict:
    total = Counter()
    for r in runs:
        total.update(r.wake_weight)
    whole = sum(total.values())
    return {kind: pct(total[kind], whole) for kind in WAKE_KINDS}


def s_list(roles: dict) -> list[dict]:
    lines = []
    for role, fig in roles.items():
        for kind, key in (("usage_error", "usage_errors"), ("refusal", "refusals")):
            for tpl, seen in fig["cli"][key].items():
                if fig["runs"] and 100 * seen["runs"] / fig["runs"] > S_LINE:
                    lines.append({"role": role, "kind": kind, "template": tpl, "runs": seen["runs"],
                                  "rate": pct(seen["runs"], fig["runs"])})
    return sorted(lines, key=lambda x: (x["role"], x["kind"], x["template"]))


# ---- the previous file, the regressions ---------------------------------------------------------

def results_files(out: Path) -> list[tuple[str, Path, dict]]:
    """The results files of `out`, oldest first by their `written` time."""
    found = []
    for path in out.glob("behaviour-*.json") if out.is_dir() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("written"), str):
                found.append((data["written"], path, data))
        except (OSError, ValueError):
            continue
    return sorted(found, key=lambda x: (x[0], x[1].name))


def regressions(now: dict, before: dict) -> list[dict]:
    found = []
    both = set(now["roles"]) & set(before.get("roles", {}))
    for det, per_role in now["detectors"].items():
        for role, fig in per_role.items():
            prior = (before.get("detectors", {}).get(det, {}) or {}).get(role)
            if role in both and prior and fig["rate"] - prior["rate"] > REGRESSION:
                found.append({"kind": "detector", "detector": det, "role": role, "rate": fig["rate"],
                              "previous": prior["rate"]})
    held = {(x.get("role"), x.get("kind"), x.get("template")) for x in before.get("s_list", [])}
    for line in now["s_list"]:
        if line["role"] in both and (line["role"], line["kind"], line["template"]) not in held:
            found.append({"kind": "s_list", "role": line["role"], "error_kind": line["kind"],
                          "template": line["template"], "runs": line["runs"], "rate": line["rate"]})
    return found


# ---- git and version ----------------------------------------------------------------------------

def git(*args: str) -> str:
    try:
        done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
    except OSError as error:
        raise External(f"`git` did not start: {error}") from None
    if done.returncode:
        raise External(f"`git {' '.join(args)}` exited {done.returncode}: {(done.stderr or done.stdout).strip()[-300:]}")
    return done.stdout.strip()


def version() -> str:
    try:
        return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    except (OSError, KeyError, ValueError) as error:
        raise External(f"pyproject.toml: version not read: {error}") from None


# ---- the privacy guard --------------------------------------------------------------------------

def leak_checker():
    home = str(Path.home()).replace("\\", "/").rstrip("/")
    forms = {home, home.replace("/", "\\")}
    drive = re.match(r"^([A-Za-z]):(/.*)$", home)
    if drive:
        forms.add(f"/{drive[1].lower()}{drive[2]}")
    forms = {f.lower() for f in forms if len(f) > 1}
    try:
        login = getpass.getuser()
    except (KeyError, OSError, ImportError):
        login = ""
    word = re.compile(rf"(?<!\w){re.escape(login)}(?!\w)", re.I) if len(login) >= 3 else None

    def leaks(text: str) -> bool:
        low = text.lower()
        return any(f in low for f in forms) or bool(word and word.search(text))
    return leaks


def leaking_paths(value, leaks, path: str = "") -> list[str]:
    """The key paths of a JSON value holding a leak; a key that leaks is named `<key>`."""
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            shown = "<key>" if leaks(str(key)) else str(key)
            here = f"{path}.{shown}" if path else shown
            if shown == "<key>":
                found.append(here)
            found += leaking_paths(item, leaks, here)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            found += leaking_paths(item, leaks, f"{path}[{i}]")
    elif isinstance(value, str) and leaks(value):
        found.append(path)
    return found


# ---- the Markdown -------------------------------------------------------------------------------

def table(headers: list[str], rows: list[list]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    out += ["| " + " | ".join(str(c).replace("|", "\\|") for c in row) + " |" for row in rows]
    return out + [""]


def markdown(data: dict) -> str:
    lines = [f"# Behaviour measure, chantier {data['version']}", "",
             f"- Window: {data['since']} to {data['last_event'] or 'no event'} "
             f"(first event {data['first_event'] or 'none'}), written {data['written']}",
             f"- Version {data['version']}, commit {data['commit']}, cards commit {data['cards_commit']} "
             f"({data['cards_date']})",
             f"- Files read {data['files_read']}, skipped {data['files_skipped']}, "
             f"runs of no chantier role {data['not_chantier_runs']}", ""]
    for role, f in data["roles"].items():
        lines += [f"## {role}", "",
                  *table(["figure", "value"], [
                      ["runs", f["runs"]],
                      ["tool calls (total, mean per run, median)",
                       f"{f['tool_calls']['total']}, {f['tool_calls']['per_run_mean']}, {f['tool_calls']['median']}"],
                      ["model calls (total, mean per run)",
                       f"{f['model_calls']['total']}, {f['model_calls']['per_run_mean']}"],
                      ["card bytes (total, mean per run)",
                       f"{f['card_bytes']['total']}, {f['card_bytes']['per_run_mean']}"],
                      ["files read per run (paths, cards)",
                       f"{f['files_read']['paths_per_run_mean']}, {f['files_read']['cards_per_run_mean']}"],
                      ["chantier calls", f["cli"]["calls"]],
                      ["host denials", ", ".join(f"{k} {v}" for k, v in f["host_denials"].items()) or "none"],
                      ["write guard refusals", f["write_guard_refusals"]],
                      ["waits (count, share of tool calls)", f"{f['waits']['count']}, {f['waits']['share']} %"],
                      ["tool not in the role's list", ", ".join(f"{k} {v}" for k, v in f["tool_not_in_list"].items()) or "none"],
                      ["`chantier push` (calls, refused, rate)",
                       f"{f['pushes']['chantier_push']}, {f['pushes']['refused']}, {f['pushes']['rate']} %"],
                      ["`git push --force-with-lease` (calls, denied)",
                       f"{f['pushes']['force_with_lease']}, {f['pushes']['force_with_lease_denied']}"],
                      ["help reads by command", ", ".join(f"{k} {v}" for k, v in f["help"]["commands"].items()) or "none"],
                      ["help reads by topic", ", ".join(f"{k} {v}" for k, v in f["help"]["topics"].items()) or "none"]])]
        if f["card_bytes"]["by_card"]:
            lines += ["Card bytes by card:", "", *table(["card", "bytes"], [[k, v] for k, v in f["card_bytes"]["by_card"].items()])]
        for title, key in (("Usage errors", "usage_errors"), ("Refusals", "refusals")):
            if f["cli"][key]:
                lines += [f"{title}:", "", *table(["template", "count", "runs"],
                                                  [[k, v["count"], v["runs"]] for k, v in f["cli"][key].items()])]
    d = data["driver_runs_per_cr"]
    lines += ["## Driver runs per CR", "",
              f"{d['crs']} CRs, {d['runs']} runs, {d['mean']} runs per CR; with one run {d['one']} %, "
              f"two {d['two']} %, three or more {d['three_or_more']} %", "", "## Wake shares", "",
              *table(["role", *WAKE_KINDS], [[r, *[f"{s[k]} %" for k in WAKE_KINDS]] for r, s in data["wake_shares"].items()])]
    roles = list(data["roles"])
    rows = [[det, *[f"{per[r]['rate']} % ({per[r]['runs_matched']})" if r in per else "-" for r in roles]]
            for det, per in data["detectors"].items()]
    lines += ["## Detectors", "", "Rate of a role's runs with at least one matching call (runs matched).", "",
              *table(["detector", *roles], rows), "## S-list", "",
              *(table(["role", "kind", "template", "runs", "rate"],
                      [[x["role"], x["kind"], x["template"], x["runs"], f"{x['rate']} %"] for x in data["s_list"]])
                if data["s_list"] else ["none", ""]), "## Regressions", ""]
    if data["previous"] is None:
        lines += ["no earlier measure", ""]
    elif not data["regressions"]:
        lines += [f"none (against {data['previous']})", ""]
    else:
        lines += [f"Against {data['previous']}:", ""]
        lines += [f"- {json.dumps(x, ensure_ascii=False)}" for x in data["regressions"]] + [""]
    return "\n".join([*lines, "Copilot: not measured (no transcript reader)", ""])


# ---- the measure --------------------------------------------------------------------------------

def measure(args, detectors: list[Detector]) -> int:
    out = Path(args.out) if args.out else ROOT / "evals" / "results"
    if args.since:
        since = parse_since(args.since)
    else:
        files = results_files(out)
        if not files:
            raise Usage(f"no earlier measure in {out}: pass `--since <date>`")
        since = parse_since(files[-1][0])
    since_s = stamp(since)[:19]
    runs: dict[str, list[Run]] = defaultdict(list)
    read = skipped = plain = 0
    for path, main, folder, meta in transcripts(projects_root(args.projects), args.folders):
        try:
            if path.stat().st_mtime < since.timestamp():
                skipped += 1
                continue
            run = read_run(path, main, folder, meta, detectors, since_s)
        except OSError:
            skipped += 1
            continue
        read += 1
        role = role_of(run)
        if role is None:
            plain += 1
        else:
            runs[role].append(run)
    ordered = sorted(runs, key=lambda r: (-len(runs[r]), r))
    roles = {r: role_figures(runs[r]) for r in ordered}
    firsts = [x.first for rs in runs.values() for x in rs if x.first]
    lasts = [x.last for rs in runs.values() for x in rs if x.last]
    det = {d.id: {r: {"runs_matched": (m := sum(1 for x in runs[r] if d.id in x.detected)),
                      "rate": pct(m, len(runs[r]))} for r in ordered if d.applies(r)} for d in detectors}
    previous = results_files(out)[-1] if results_files(out) else None
    data = {"schema": 1, "version": version(), "commit": git("rev-parse", "--short", "HEAD"),
            "cards_commit": "", "cards_date": "", "since": stamp(since),
            "written": stamp(datetime.datetime.now(datetime.timezone.utc)),
            "first_event": min(firsts) if firsts else None, "last_event": max(lasts) if lasts else None,
            "files_read": read, "files_skipped": skipped, "not_chantier_runs": plain, "host": "claude-code",
            "roles": roles,
            "driver_runs_per_cr": driver_figures(runs.get("cr-driver", [])),
            "wake_shares": {r: wake_figures(runs[r]) for r in ("foreman", "chief-of-staff") if r in runs},
            "detectors": det, "s_list": s_list(roles), "previous": None, "regressions": []}
    cards = git("log", "-1", "--format=%h %cI", "--", "skills/chantier/references").split()
    data["cards_commit"], data["cards_date"] = (cards + ["", ""])[:2]
    if previous:
        data["previous"] = previous[1].name
        data["regressions"] = regressions(data, previous[2])
    text_json = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    text_md = markdown(data)
    leaks = leak_checker()
    bad = leaking_paths(data, leaks)
    bad += [f"markdown line {i}" for i, line in enumerate(text_md.splitlines(), 1) if leaks(line)]
    if bad:
        print("behaviour.py: refused, nothing written: the results would hold the home folder's path or "
              "the login name, at: " + ", ".join(bad), file=sys.stderr)
        return PRIVACY
    out.mkdir(parents=True, exist_ok=True)
    stem = f"behaviour-{data['written'][:10]}-v{data['version']}"
    name, n = stem, 1
    while (out / f"{name}.json").exists() or (out / f"{name}.md").exists():
        n += 1
        name = f"{stem}-run{n}"
    for suffix, text in ((".json", text_json), (".md", text_md)):
        with open(out / f"{name}{suffix}", "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    print(f"wrote {out / (name + '.json')} and {out / (name + '.md')}: {read} files read, {skipped} skipped, "
          f"{sum(len(v) for v in runs.values())} runs of {len(runs)} roles, {plain} of no chantier role, "
          f"{len(data['regressions'])} regressions")
    return OK


def topics() -> list[str] | None:
    """The help topics of `references/topics.json` (child 7); None before it exists."""
    try:
        data = json.loads(TOPICS.read_text(encoding="utf-8"))
    except OSError:
        return None
    except ValueError:
        raise Usage(f"{TOPICS.name}: not valid JSON") from None
    if isinstance(data, dict):
        data = data.get("topics", list(data))
    names = []
    for item in data if isinstance(data, (list, dict)) else []:
        name = item if isinstance(item, str) else (item.get("topic") or item.get("name") or item.get("id")
                                                   if isinstance(item, dict) else None)
        if isinstance(name, str):
            names.append(name)
    return names


def prune(args, detectors: list[Detector]) -> int:
    out = Path(args.out) if args.out else ROOT / "evals" / "results"
    files = results_files(out)[-2:]
    if len(files) < 2:
        print("needs two measures")
        return OK
    found = False
    for d in detectors:
        if d.floor is not None:
            continue
        if all(per.get("runs_matched", 0) == 0 for _, _, data in files
               for per in (data.get("detectors", {}).get(d.id) or {}).values()):
            print(f"detector {d.id}: no floor, no matching run in {files[0][1].name} and {files[1][1].name}")
            found = True
    names = topics()
    if names is None:
        print("no topics file")
    for topic in names or []:
        if all(topic not in role.get("help", {}).get("topics", {}) for _, _, data in files
               for role in data.get("roles", {}).values()):
            print(f"help topic {topic}: no read in {files[0][1].name} and {files[1][1].name}")
            found = True
    if not found:
        print("no candidate")
    return OK


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="behaviour.py", description=__doc__.splitlines()[0])
    parser.add_argument("--since", help="an ISO date or time; default: the latest results file's `written`")
    parser.add_argument("--prune", action="store_true", help="print the deletion candidates; read no transcript")
    parser.add_argument("--projects", help="the transcripts' root (default: $CLAUDE_CONFIG_DIR/projects, else ~/.claude/projects)")
    parser.add_argument("--folders", help="keep only the project folders whose name matches this glob")
    parser.add_argument("--out", help="where the results go (default: evals/results/)")
    args = parser.parse_args(argv)
    try:
        detectors = load_detectors()
        return prune(args, detectors) if args.prune else measure(args, detectors)
    except Usage as error:
        print(f"behaviour.py: {error}", file=sys.stderr)
        return USAGE
    except External as error:
        print(f"behaviour.py: {error}", file=sys.stderr)
        return EXTERNAL


if __name__ == "__main__":
    sys.exit(main())

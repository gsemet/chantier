"""The situation quiz: a role's boot text, one situation, "what do you do next", three runs, a judge.

    uv run --locked python evals/kit/quiz.py <role> [<role> ...] [--cards <git ref or folder>]
            [--case <id>] [--model <id>] [--max-usd <dollars>] [--plan]
            [--against <results.json> ...] [--save <label>]

A cheap check beside the real-run campaign. For each case of `evals/quiz/<role>/<id>.json` it gives
the role the text it boots on (its start reading, built from the cards; section "Boot text" of
CR-492), adds the case's situation, asks what it does next, and runs that three times on the role's
own model (the shipped defaults' `hosts.claude.roles.<role>.model`, never the project's
`chantier.yaml`; `--model` is needed for the three session roles, `chief-of-staff`, `foreman` and
`griller`, which have none). A separate judge model (`quiz_judge.JUDGE_MODEL`) then reads each reply
against the behaviour the case expects. Nothing is written in the repository without `--save`
(`evals/results/quiz-<date>-<label>.json` and `.md`: counts, verdicts and short reasons; no reply,
no prompt, no username, no home path). The replies stay in a temporary folder whose path is printed.

A spend cap is printed first: the plan (one line per role) and its estimate, refused (exit 2) above
`--max-usd` (default 10) before any model call; while running, no call starts once the measured cost
reaches it. The batch's `cost` does not see this spend. `--plan` stops after the plan. A case's
score is its passes out of three. `--against` reads earlier results files and applies F4: the new
cards pass when no case scores 0 of 3 that the old cards scored at least 1 of 3 on (each case from
the newest file that holds it).

Boot text: the working tree, and a folder of cards (`--cards <folder>`), ask `chantier brief <role>`:
the short prompt it prints, then the brief file it names. A git ref from before the cards were
swapped (it holds `references/startup-manifest.json`) is walked by that manifest, each byte once in
LF form, each part under a `=== <path>` header; a ref with no manifest is refused. Claude Code only:
with `CHANTIER_HOST=copilot` the quiz refuses. Hidden options for the dry run: `--cases-dir`,
`--results-dir`.

Exit codes, as the kit's other tools: 0 done (and F4 holds when `--against` is given); 1 F4
violated (each case named); 2 usage or refusal (an unknown role or case, a missing or refused
`--model`, a model with no price, the cap, `--cards` that cannot be built, Copilot); 4 external (the
host CLI is missing, a run or a judge call failed or timed out, git failed: the tool's own text).

One exception to the kit's standard-library-only line: the quiz runs in the root project's
environment (the recipe's `uv run --locked`), as the dry run's CLI calls do, and imports from the
`chantier` package, edited by none of it, `board.griller_host` (the Claude flags `CLAUDE`, the
`CLEARED_ENV` variables, `end_tree`, `result`), `costs.transcripts` (`PRICE`, `LONG_CONTEXT_TOKENS`) and
`playbook.layers` (`read_defaults`, `default_model`). Unproved until the first real run (F17): that
`--setting-sources ""` keeps the user's `~/.claude/CLAUDE.md` out, that the plugin's hook is harmless
in a headless run, that `total_cost_usd` and `num_turns` are in the JSON, that a model with every
tool refused still ends with a text `result`, that `--model claude-fable-5-2` is accepted under `-p`,
and `HOST_PROMPT_TOKENS`.
"""
from __future__ import annotations

import argparse
import datetime
import getpass
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
if __name__ == "__main__":  # the judge's `import quiz` must find this module, not a second copy
    sys.modules["quiz"] = sys.modules[__name__]
import quiz_judge  # noqa: E402

from chantier.board import griller_host  # noqa: E402
from chantier.costs.transcripts import LONG_CONTEXT_TOKENS, PRICE  # noqa: E402
from chantier.playbook import layers  # noqa: E402

OK, FAILED, USAGE, EXTERNAL = 0, 1, 2, 4
CASES_DIR = ROOT / "evals" / "quiz"
RESULTS_DIR = ROOT / "evals" / "results"
SCORECARD = ROOT / "evals" / "SCORECARD.md"
INVENTORY = ROOT / "docs" / "proofs" / "cards-inventory.md"
DEFAULTS = ROOT / "config" / "chantier.defaults.yml"
SESSION_ROLES = ("chief-of-staff", "foreman", "griller")
DRIVERS = ("cr-driver", "stack-driver", "qa-driver", "release-driver")
RUNS = 3
RUN_TIMEOUT = 300  # seconds, then the process tree is ended
HOST_PROMPT_TOKENS = 25_000  # unproved: the host's own prompt and tools; set from the first real run's cost
OUTPUT_TOKENS_ROLE = 1500
OUTPUT_TOKENS_JUDGE = 100
JUDGE_INPUT_TOKENS = 2_000
QUESTION = (
    "What do you do next? Answer in a few lines: the next action you take (the exact command, or "
    "the message and to whom), and why. Do not run anything."
)
KEYS = ("id", "role", "rules", "situation", "expected")
RULE = re.compile(r"floor-(?:[1-9]|10)|R-\d{3}")


class Stop(Exception):
    """A refusal or an external failure: the one line, and the exit code."""

    def __init__(self, text: str, code: int = USAGE):
        super().__init__(text)
        self.code = code


@dataclass
class Reply:
    """What one host CLI call gave: the text or the error, and the cost and turns when it said."""

    text: str | None = None
    error: str | None = None
    cost: float | None = None
    turns: int | None = None


@dataclass
class Boot:
    text: str
    parts: list[dict]
    bytes: int
    header_bytes: int
    label: str
    sha: str


@dataclass
class Case:
    id: str
    role: str
    rules: list[str]
    situation: str
    expected: str
    path: Path


# --- the roles, the models and the prices ---------------------------------------------------


def known_roles() -> list[str]:
    wrappers = sorted(p.stem for p in (ROOT / "agents").glob("*.md"))
    return sorted({*wrappers, *SESSION_ROLES})


def shipped_models() -> dict[str, str | None]:
    """The shipped defaults' model of each role on Claude (None for a role that has none)."""
    folders = {"claude": ROOT / "agents", "copilot": ROOT / "com.github.copilot" / "agents"}
    roles_by_host = {
        host: [
            p.name.removesuffix(".md").removesuffix(".agent").removeprefix("chantier-")
            for p in sorted(folder.glob("*.md"))
        ]
        for host, folder in folders.items()
    }
    tree, problems = layers.read_defaults(DEFAULTS, roles_by_host)
    if tree is None or problems:
        raise Stop(f"the shipped defaults do not read: {'; '.join(problems) or 'none'}", EXTERNAL)
    return {role: layers.default_model(tree, "claude", role) for role in known_roles()}


def price(model: str, tokens: int) -> tuple:
    """The $/MTok of a model (input, 5-minute write, 1-hour write, read, output), the long-context
    tier above `LONG_CONTEXT_TOKENS`: the exact id, or the id without a trailing `-YYYYMMDD`."""
    ids = [model]
    if dated := re.fullmatch(r"(.+)-\d{8}", model):
        ids.append(dated.group(1))
    for one in ids:
        if one in PRICE:
            tier = PRICE.get(f"{one}>100k")
            return tier if tier and tokens > LONG_CONTEXT_TOKENS else PRICE[one]
    raise Stop(f"no price for {model}: the quiz cannot estimate its spend")


def run_cost(model: str, boot_bytes: int, situation_bytes: int) -> float:
    """One role run, estimated high: bytes / 3 for tokens, no cache reads."""
    tokens = HOST_PROMPT_TOKENS + boot_bytes // 3 + situation_bytes // 3
    rates = price(model, tokens)
    return (tokens * rates[1] + OUTPUT_TOKENS_ROLE * rates[4]) / 1_000_000


def judge_cost() -> float:
    tokens = HOST_PROMPT_TOKENS + JUDGE_INPUT_TOKENS
    rates = price(quiz_judge.JUDGE_MODEL, tokens)
    return (tokens * rates[1] + OUTPUT_TOKENS_JUDGE * rates[4]) / 1_000_000


def estimate(model: str, boot_bytes: int, cases: list[Case]) -> float:
    """The estimate for a role: three runs and three judge calls per case."""
    return sum(
        RUNS * (run_cost(model, boot_bytes, len(c.situation.encode())) + judge_cost()) for c in cases
    )


# --- the boot text --------------------------------------------------------------------------


def lf(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def section_span(data: bytes, heading: str, where: str) -> tuple[int, int]:
    """The bytes of a section: its heading line to the next heading of its level or above."""
    lines = data.splitlines(keepends=True)
    title = heading.encode("utf-8")
    start = next((i for i, line in enumerate(lines) if line.rstrip(b"\r\n") == title), None)
    if start is None:
        raise Stop(f"{where}: missing section {heading}")
    level = len(title) - len(title.lstrip(b"#"))
    pattern = re.compile(rb"#{1," + str(level).encode() + rb"} ")
    end = next((i for i in range(start + 1, len(lines)) if pattern.match(lines[i])), len(lines))
    return sum(map(len, lines[:start])), sum(map(len, lines[:end]))


class Walk:
    """The parts of a reading in order, each byte once."""

    def __init__(self, root: Path):
        self.root = root
        self.covered: dict[Path, list[tuple[int, int]]] = {}
        self.parts: list[dict] = []
        self.chunks: list[str] = []
        self.header_bytes = 0

    def add(self, path: Path, heading: str | None, span: tuple[int, int] | None = None) -> None:
        path = path.resolve()
        data = lf(path)
        start, end = span or (0, len(data))
        gaps, cursor = [], start
        for s, e in sorted(self.covered.get(path, [])):
            if e <= cursor:
                continue
            if s >= end:
                break
            if s > cursor:
                gaps.append((cursor, s))
            cursor = max(cursor, e)
        if cursor < end:
            gaps.append((cursor, end))
        self.covered.setdefault(path, []).append((start, end))
        rel = path.relative_to(self.root.resolve()).as_posix()
        label = heading.removeprefix("## ") if heading else None
        for s, e in gaps:
            body = data[s:e].decode("utf-8")
            if not body.endswith("\n"):
                body += "\n"
            header = f"=== {rel}" + (f"#{label}" if label else "")
            self.chunks.append(f"{header}\n{body}")
            self.header_bytes += len(header.encode()) + 1 + len(body.encode()) - (e - s)
            self.parts.append(
                {"file": rel, "heading": label or "whole", "bytes": e - s, "start": s, "end": e,
                 "size": len(data)}
            )


def _expand(readings: list, actions: dict) -> list:
    out: list = []
    for reading in readings:
        if isinstance(reading, str) and reading.startswith("@"):
            if reading[1:] not in actions:
                raise Stop(f"the manifest has no action {reading[1:]}")
            out += _expand(actions[reading[1:]], actions)
        else:
            out.append(reading)
    return out


def _resolve(reading, refs: Path) -> tuple[Path, str | None]:
    if isinstance(reading, dict):
        reading = reading["claude"]
    file, _, heading = reading.partition("#")
    path = refs / file
    if not path.is_file():
        raise Stop(f"the manifest names {reading}, which is not a file here")
    return path, (f"## {heading}" if heading else None)


def build_old_boot(role: str, root: Path, label: str, sha: str) -> Boot:
    """The role's start reading under a ref from before the swap, walked by its startup manifest."""
    refs = root / "skills" / "chantier" / "references"
    manifest_path = refs / "startup-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    actions = manifest["actions"]
    walk = Walk(root)
    for path in (
        refs / manifest["common"],
        refs / manifest["role_core"],
        refs / manifest["hosts"]["claude"]["core"],
        manifest_path,
    ):
        walk.add(path, None)
    entry = {
        "chief-of-staff": root / "skills" / "chief-of-staff" / "SKILL.md",
        "griller": root / "skills" / "griller" / "SKILL.md",
        "foreman": None,
    }.get(role, root / "agents" / f"{role}.md")
    if entry is not None:
        walk.add(entry, None)
    readings = list(manifest["startup_sections"].get(role, []))
    first = {"chief-of-staff": ["session-start", "chief-of-staff"], "foreman": ["batch"],
             "griller": ["grill"]}.get(role, [role] if role in actions else [])
    for action in first:
        readings += actions[action]
    for reading in _expand(readings, actions):
        path, heading = _resolve(reading, refs)
        if heading is None:
            walk.add(path, None)
        else:
            walk.add(path, heading, section_span(lf(path), heading, f"{path.name}"))
    if role in DRIVERS:  # `driver.md`'s opening, before its first `## `: no section holds it
        card = refs / manifest["roles"][role]
        match = re.search(rb"^## ", lf(card), re.M)
        if match:
            walk.add(card, "## (opening)", (0, match.start()))
    text = "".join(walk.chunks)
    return Boot(text, walk.parts, len(text.encode()), walk.header_bytes, label, sha)


# --- the sources of the cards ---------------------------------------------------------------


def git(*args: str, binary: bool = False):
    try:
        done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    except OSError as error:
        raise Stop(f"`git` did not start: {error}", EXTERNAL) from None
    if done.returncode != 0:
        raise Stop(
            f"`git {' '.join(args)}` exited {done.returncode}: "
            f"{done.stderr.decode('utf-8', 'replace').strip()[-300:]}", EXTERNAL,
        )
    return done.stdout if binary else done.stdout.decode("utf-8", "replace").strip()


def head_state() -> tuple[str, bool]:
    dirty = git("status", "--porcelain", "--", "skills", "agents", "com.github.copilot")
    return git("rev-parse", "HEAD"), bool(dirty)


@dataclass
class Source:
    """Where the boots come from: `tree`, `ref` (unpacked in `root`), `folder` or `brief`."""

    kind: str
    ref: str | None
    sha: str
    root: Path | None = None
    folder: Path | None = None
    cleanup: list[Path] = field(default_factory=list)

    def has_manifest(self) -> bool:
        return self.root is not None and (
            self.root / "skills" / "chantier" / "references" / "startup-manifest.json"
        ).is_file()


def open_source(cards: str | None, head: str) -> Source:
    if cards is None:
        if (ROOT / "skills" / "chantier" / "references" / "startup-manifest.json").is_file():
            return Source("tree", None, head, root=ROOT)
        return Source("brief", None, head)
    if Path(cards).is_dir():
        return Source("folder", str(Path(cards).resolve()), head, folder=Path(cards).resolve())
    try:
        sha = git("rev-parse", "--verify", f"{cards}^{{commit}}")
    except Stop:
        raise Stop(f"{cards} does not resolve to a commit") from None
    data = git("archive", "--format=tar", sha, "skills", "agents", "com.github.copilot", binary=True)
    folder = Path(tempfile.mkdtemp(prefix="chantier-quiz-ref-"))
    try:
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:
            tar.extractall(folder, filter="data")
    except (tarfile.TarError, OSError) as error:
        shutil.rmtree(folder, ignore_errors=True)
        raise Stop(f"the tree of {cards} did not unpack: {error}", EXTERNAL) from None
    source = Source("ref", cards, sha, root=folder, cleanup=[folder])
    if not source.has_manifest():
        source.close()
        raise Stop(
            f"{cards} holds no startup manifest: check it out and run the quiz on that head"
        )
    return source


def _close(self: Source) -> None:
    for folder in self.cleanup:
        shutil.rmtree(folder, ignore_errors=True)


Source.close = _close  # type: ignore[attr-defined]


def brief_boot(role: str, source: Source) -> Boot:
    """`chantier brief <role> [--cards <folder>]`: the short prompt, then the brief file it names.
    A role-only brief on Claude: the caller's `CHANTIER_BATCH` is not passed on."""
    argv = [sys.executable, "-m", "chantier", "--project", str(ROOT), "brief", role]
    if source.folder is not None:
        argv += ["--cards", str(source.folder)]
    env = {k: v for k, v in os.environ.items() if k != "CHANTIER_BATCH"} | {"CHANTIER_HOST": "claude"}
    done = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    said = (done.stderr or done.stdout).strip()
    if done.returncode != 0:
        print(said, file=sys.stderr)
        if "invalid choice: 'brief'" in said:
            raise Stop("`--cards <folder>` needs `chantier brief`, which this head does not have")
        raise Stop(f"`chantier brief {role}` exited {done.returncode}")
    prompt = done.stdout.strip()
    last = prompt.splitlines()[-1] if prompt else ""
    match = re.fullmatch(r"Read (.+) whole, first\.", last)
    if not match or not Path(match.group(1)).is_file():
        raise Stop(f"`chantier brief {role}` ended with {last!r}, not `Read <file> whole, first.`")
    body = lf(Path(match.group(1))).decode("utf-8")
    text = f"{prompt}\n=== {Path(match.group(1)).name}\n{body}"
    return Boot(text, [{"file": match.group(1), "heading": "whole", "bytes": len(body.encode())}],
                len(text.encode()), len(text.encode()) - len(body.encode()),
                source.ref or "brief", source.sha)


def build_boot(role: str, source: Source) -> Boot:
    if source.kind in ("tree", "ref") and source.has_manifest():
        assert source.root is not None
        label = "working tree" if source.kind == "tree" else str(source.ref)
        return build_old_boot(role, source.root, label, source.sha)
    return brief_boot(role, source)


# --- the cases ------------------------------------------------------------------------------


def scorecard_rails() -> set[str]:
    text = SCORECARD.read_text(encoding="utf-8")
    return set(re.findall(r"^\| (J\d+) \|", text, re.M))


def inventory_rows() -> set[str]:
    """The row ids of the cards' inventory."""
    text = INVENTORY.read_text(encoding="utf-8")
    return set(re.findall(r"^\| ([A-Z]{1,2}-B?\d{3,4}) \|", text, re.M))


def load_cases(roles: list[str], case: str | None = None, cases_dir: Path = CASES_DIR,
               rails: set[str] | None = None) -> list[Case]:
    """The cases of the roles, every file validated (exit 2 on the first bad one, naming the file
    and the key); with `case`, that one only (exit 2 when no role holds it). `rails` are the ids a
    case may name beside the floor rules and `R-nnn`: the scorecard's J rows and the inventory's
    row ids."""
    rails = scorecard_rails() | inventory_rows() if rails is None else rails
    found: list[Case] = []
    for role in roles:
        for path in sorted((cases_dir / role).glob("*.json")):
            found.append(read_case(path, role, rails))
    if case is not None:
        found = [c for c in found if c.id == case]
        if not found:
            raise Stop(f"no case {case} among the roles named ({', '.join(roles)})")
    return found


def read_case(path: Path, role: str, rails: set[str]) -> Case:
    def bad(key: str, why: str) -> Stop:
        return Stop(f"{path}: key {key}: {why}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise Stop(f"{path}: not a JSON file: {error}") from None
    if not isinstance(data, dict):
        raise Stop(f"{path}: not a JSON object")
    for key in KEYS:
        if key not in data:
            raise bad(key, "missing")
    for key in data:
        if key not in KEYS:
            raise bad(key, "unknown key")
    for key in ("id", "role", "situation", "expected"):
        if not isinstance(data[key], str) or not data[key].strip():
            raise bad(key, "a non-empty string is required")
    if data["id"] != path.stem:
        raise bad("id", f"{data['id']!r} is not the file's stem {path.stem!r}")
    if data["role"] != role:
        raise bad("role", f"{data['role']!r} is not the folder's {role!r}")
    rules = data["rules"]
    if not isinstance(rules, list) or not rules or not all(isinstance(r, str) for r in rules):
        raise bad("rules", "a non-empty list of strings is required")
    for rule in rules:
        if not (RULE.fullmatch(rule) or rule in rails):
            raise bad("rules", f"{rule!r} is no floor rule, no J row of evals/SCORECARD.md, no row id "
                               "of docs/proofs/cards-inventory.md and no R-nnn id")
    return Case(data["id"], role, rules, data["situation"], data["expected"], path)


# --- the host CLI ---------------------------------------------------------------------------

_WORK: list[Path] = []


def work_dir() -> Path:
    """The run's temporary folder: each call's empty cwd, and the replies. Nothing removes it."""
    if not _WORK:
        _WORK.append(Path(tempfile.mkdtemp(prefix="chantier-quiz-")))
    return _WORK[0]


def environment() -> dict[str, str]:
    """The quiz's own environment minus the variables of a steering or nested session."""
    cleared = {name.upper() for name in griller_host.CLEARED_ENV}
    return {k: v for k, v in os.environ.items() if k.upper() not in cleared}


def claude_argv(exe: str, model: str, plugin_root: Path | None) -> list[str]:
    """The flags of `griller_host.CLAUDE`: print, model, no settings, the plugin (the judge's has
    none), no MCP, every tool refused. No agent, no session, no `--add-dir`."""
    flags = griller_host.CLAUDE
    argv = [exe, *flags["print"], flags["model"], model, *flags["no-settings"]]
    if plugin_root is not None:
        argv += [flags["plugin"], str(plugin_root)]
    return argv + [*flags["no-mcp"], *flags["refuse"]]


def call_claude(prompt: str, model: str, plugin_root: Path | None) -> Reply:
    """One headless call, the prompt on standard input, in a new empty folder."""
    exe = shutil.which("claude")
    if exe is None:
        return Reply(error="claude: not found on this machine")
    folder = Path(tempfile.mkdtemp(dir=work_dir()))
    try:
        proc = subprocess.Popen(
            claude_argv(exe, model, plugin_root), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, cwd=folder, env=environment(),
        )
    except OSError as error:
        return Reply(error=f"claude did not start: {error}")
    try:
        out, err = proc.communicate(prompt.encode("utf-8"), timeout=RUN_TIMEOUT)
    except subprocess.TimeoutExpired:
        griller_host.end_tree(proc)
        proc.communicate()
        return Reply(error=f"timed out after {RUN_TIMEOUT} s")
    text, error = griller_host.result(out, err, proc.returncode)
    cost = turns = None
    try:
        data = json.loads(out.decode("utf-8", "replace"))
        if isinstance(data, dict):
            cost = data.get("total_cost_usd")
            turns = data.get("num_turns")
    except ValueError:
        pass
    cost = float(cost) if isinstance(cost, (int, float)) and not isinstance(cost, bool) else None
    turns = turns if isinstance(turns, int) and not isinstance(turns, bool) else None
    return Reply(text=text, error=error, cost=cost, turns=turns)


def run_role(prompt: str, model: str, plugin_root: Path) -> Reply:
    """The seam: one role run (the dry run replaces this function)."""
    return call_claude(prompt, model, plugin_root)


def host_check() -> str:
    """The seam: `claude --version`, or exit 4 when the CLI is missing (the dry run replaces it)."""
    exe = shutil.which("claude")
    if exe is None:
        raise Stop("claude: not found on this machine", EXTERNAL)
    try:
        done = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise Stop(f"`claude --version` failed: {error}", EXTERNAL) from None
    if done.returncode != 0:
        raise Stop(f"`claude --version` exited {done.returncode}: {done.stderr.strip()}", EXTERNAL)
    return done.stdout.strip()


# --- redaction, scores, F4 ------------------------------------------------------------------


def redact(value):
    """Strings with the home folder as `~` and the username as `<user>`, through lists and dicts."""
    if isinstance(value, str):
        home = Path.home()
        forms = sorted({str(home), home.as_posix(), str(home).replace("\\", "\\\\")}, key=len,
                       reverse=True)
        for form in forms:
            value = re.sub(re.escape(form), "~", value, flags=re.I)
        names = {home.name, os.environ.get("USERNAME", ""), os.environ.get("USER", ""),
                 os.environ.get("LOGNAME", "")}
        try:
            names.add(getpass.getuser())
        except Exception:
            pass
        for name in sorted((n for n in names if n), key=len, reverse=True):
            edge = (r"(?<![A-Za-z0-9])", r"(?![A-Za-z0-9])") if len(name) < 4 else ("", "")
            value = re.sub(edge[0] + re.escape(name) + edge[1], "<user>", value, flags=re.I)
        return value
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    return value


def passes_of(runs: list[dict]) -> int:
    return sum(1 for r in runs if r["verdict"] == "PASS")


def ran(entry: dict) -> bool:
    return any(r["verdict"] != "not run" for r in entry["runs"])


def baseline_scores(files: list[Path]) -> dict[str, tuple[int, str]]:
    """Each case's passes and the file it comes from, from the newest file that holds it."""
    loaded = []
    for number, path in enumerate(files):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            loaded.append((str(data.get("date", "")), number, path, data))
        except (OSError, ValueError) as error:
            raise Stop(f"{path}: not a results file: {error}") from None
    scores: dict[str, tuple[int, str, str]] = {}
    for date, number, path, data in sorted(loaded, key=lambda t: (t[0], t[1])):
        for role, body in data.get("roles", {}).items():
            for entry in body.get("cases", []):
                scores[f"{role}/{entry['id']}"] = (entry["passes"], path.name, role)
    return {k: (v[0], v[1]) for k, v in scores.items()}


def f4(results: dict[str, dict], files: list[Path], roles: list[str]) -> tuple[list[str], int]:
    """The F4 lines and the number of regressions."""
    base = baseline_scores(files)
    compared = new = 0
    lines, bad = [], []
    for role, body in results.items():
        for entry in body["cases"]:
            if not ran(entry):
                continue
            if f"{role}/{entry['id']}" not in base:
                new += 1
                continue
            compared += 1
            before, name = base[f"{role}/{entry['id']}"]
            if entry["passes"] == 0 and before >= 1:
                bad.append(f"F4 FAIL {entry['id']}: 0/3 now, {before}/3 in {name}")
    lines.append(f"F4: {compared} cases compared, {new} new (no baseline)")
    lines += bad
    now = {f"{r}/{e['id']}" for r, b in results.items() for e in b["cases"] if ran(e)}
    for key in sorted(base):
        if key.split("/")[0] in roles and key not in now:
            lines.append(f"not run {key.split('/', 1)[1]} (in the baseline, not run now)")
    lines.append("F4: holds" if not bad else f"F4: violated ({len(bad)} cases)")
    return lines, len(bad)


# --- the results files ----------------------------------------------------------------------


def markdown(data: dict) -> str:
    out = [f"# Situation quiz, {data['date']}", ""]
    out.append(f"- Head {data['head'][:8]}{' (dirty)' if data['dirty'] else ''}; cards: "
               f"{data['cards']['kind']} {data['cards']['ref'] or ''} {data['cards']['sha'][:8]}")
    out.append(f"- Host {data['host']} ({data['claude_version']}); judge {data['judge_model']}; "
               f"{data['runs_per_case']} runs per case; host prompt tokens {data['host_prompt_tokens']} "
               f"(unproved); cap ${data['max_usd']}; incomplete: {str(data['incomplete']).lower()}")
    out += ["", "## Roles", "", "| role | model | source | boot bytes | cases | 3/3 | 2/3 | 1/3 | 0/3 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for role, body in data["roles"].items():
        ranked = [c for c in body["cases"] if c["passes"] is not None]
        counts = [sum(1 for c in ranked if c["passes"] == n) for n in (3, 2, 1, 0)]
        out.append(f"| {role} | {body['model']} | {body['model_source']} | {body['boot_bytes']} | "
                   f"{len(ranked)} | " + " | ".join(map(str, counts)) + " |")
    out += ["", "## Cases", "", "| role | case | rules | passes | runs |", "| --- | --- | --- | --- | --- |"]
    for role, body in data["roles"].items():
        for c in body["cases"]:
            runs = ", ".join(r["verdict"] for r in c["runs"])
            score = "not run" if c["passes"] is None else f"{c['passes']}/3"
            out.append(f"| {role} | {c['id']} | {', '.join(c['rules'])} | {score} | {runs} |")
    spend = data["spend"]
    measured = "not measured" if spend["measured"] is None else f"${spend['measured']:.2f}"
    out += ["", "## Spend", "", f"- Estimated: ${spend['estimated']:.2f}", f"- Measured: {measured}",
            f"- Calls not measured: {spend['calls_not_measured']}", ""]
    return "\n".join(out)


def save(data: dict, label: str, results_dir: Path) -> list[Path]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", label):
        raise Stop(f"--save {label!r}: a label is letters, digits, dots, dashes and underscores")
    stem = results_dir / f"quiz-{data['date']}-{label}"
    paths = [stem.with_suffix(".json"), stem.with_suffix(".md")]
    taken = [p for p in paths if p.exists()]
    if taken:
        raise Stop(f"{taken[0]} exists: nothing written")
    data = redact(data)
    results_dir.mkdir(parents=True, exist_ok=True)
    paths[0].write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    paths[1].write_text(markdown(data), encoding="utf-8", newline="\n")
    return paths


# --- the run --------------------------------------------------------------------------------


def prompt_of(boot: Boot, case: Case) -> str:
    return f"{boot.text}\n=== Situation\n{case.situation}\n\n{QUESTION}\n"


def usd(value: float) -> str:
    return f"{value:.2f}"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="quiz.py", description=__doc__.splitlines()[0])
    p.add_argument("roles", nargs="+", metavar="role")
    p.add_argument("--cards", help="a git ref or a folder of cards; default the working tree")
    p.add_argument("--case", help="that case only")
    p.add_argument("--model", help="the model of a role with no shipped model")
    p.add_argument("--max-usd", type=float, default=10.0, help="the spend cap in dollars (10)")
    p.add_argument("--plan", action="store_true", help="print the plan and the estimate, then stop")
    p.add_argument("--against", nargs="+", action="extend", default=[], metavar="results.json")
    p.add_argument("--save", metavar="label", help="write evals/results/quiz-<date>-<label>.json/.md")
    p.add_argument("--cases-dir", type=Path, default=CASES_DIR, help=argparse.SUPPRESS)  # the dry run's
    p.add_argument("--results-dir", type=Path, default=RESULTS_DIR, help=argparse.SUPPRESS)  # the dry run's
    return p


def run(argv) -> int:
    args = parser().parse_args(argv)
    if os.environ.get("CHANTIER_HOST", "").lower() == "copilot":
        raise Stop("the quiz runs on Claude Code only")
    known = known_roles()
    roles = list(dict.fromkeys(args.roles))
    unknown = [r for r in roles if r not in known]
    if unknown:
        raise Stop(f"unknown role {', '.join(unknown)}: the roles are {', '.join(known)}")
    shipped = shipped_models()
    models: dict[str, tuple[str, str]] = {}
    for role in roles:
        if shipped[role] and args.model:
            raise Stop(f"--model is refused for {role}: it has a shipped model, {shipped[role]}")
        if not shipped[role] and not args.model:
            raise Stop(f"{role} has no shipped model: pass --model <id>")
        models[role] = (shipped[role] or args.model, "shipped" if shipped[role] else "given")
        if models[role][0] == quiz_judge.JUDGE_MODEL:
            raise Stop(f"{role} would run on {quiz_judge.JUDGE_MODEL}, the judge's model: "
                       "the judge never uses the role's own model")
    cases = load_cases(roles, args.case, args.cases_dir)
    by_role = {role: [c for c in cases if c.role == role] for role in roles}
    if not cases:
        raise Stop(f"no case for {', '.join(roles)} in {args.cases_dir}")
    for model in [m for m, _ in models.values()] + [quiz_judge.JUDGE_MODEL]:
        price(model, 0)
    head, dirty = head_state()
    source = open_source(args.cards, head)
    try:
        boots = {role: build_boot(role, source) for role in roles if by_role[role]}
        return play(args, roles, models, by_role, boots, source, head, dirty)
    finally:
        source.close()  # type: ignore[attr-defined]


def play(args, roles, models, by_role, boots, source, head, dirty) -> int:
    plans, total, total_runs = {}, 0.0, 0
    for role in roles:
        if not by_role[role]:
            continue
        model = models[role][0]
        plans[role] = estimate(model, boots[role].bytes, by_role[role])
        n = len(by_role[role])
        total += plans[role]
        total_runs += n * RUNS
        print(f"plan: {role} {n} cases x {RUNS} runs on {model} + {n * RUNS} judge calls on "
              f"{quiz_judge.JUDGE_MODEL}: ~${usd(plans[role])}")
    print(f"plan total: {total_runs} runs, ~${usd(total)} (cap ${args.max_usd:g})")
    if args.plan:
        return OK
    if total > args.max_usd:
        raise Stop(f"estimate ${usd(total)} exceeds the cap ${args.max_usd:g}: pass --max-usd, "
                   "or fewer roles or --case")
    version = host_check()
    started = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    spend = {"measured": 0.0, "calls": 0, "unmeasured": 0}
    state = {"capped": False, "skipped": 0, "errors": 0, "unreadable": 0}
    results: dict[str, dict] = {}

    def call_allowed() -> bool:
        if spend["measured"] >= args.max_usd:
            state["capped"] = True
        return not state["capped"]

    def count(cost) -> None:
        spend["calls"] += 1
        if cost is None:
            spend["unmeasured"] += 1
        else:
            spend["measured"] += cost

    for role in roles:
        if not by_role[role]:
            continue
        model, source_of_model = models[role]
        boot = boots[role]
        entries = []
        for case in by_role[role]:
            runs = []
            prompt = prompt_of(boot, case)
            replies = []
            for n in range(1, RUNS + 1):
                if not call_allowed():
                    state["skipped"] += 1
                    replies.append(None)
                    continue
                reply = run_role(prompt, model, ROOT)
                count(reply.cost)
                replies.append(reply)
                if reply.text is not None:
                    folder = work_dir() / role
                    folder.mkdir(exist_ok=True)
                    (folder / f"{case.id}-{n}.txt").write_text(reply.text, encoding="utf-8")
            for reply in replies:
                if reply is None:
                    runs.append({"verdict": "not run", "reason": "cap reached", "cost_usd": None,
                                 "judge_cost_usd": None, "error": None})
                elif reply.error is not None or reply.text is None:
                    text = redact(reply.error or "no result")
                    state["errors"] += 1
                    runs.append({"verdict": "error", "reason": text, "cost_usd": reply.cost,
                                 "judge_cost_usd": None, "error": text})
                elif not call_allowed():
                    runs.append({"verdict": "not run", "reason": "cap reached before the judge",
                                 "cost_usd": reply.cost, "judge_cost_usd": None, "error": None})
                else:
                    verdict = quiz_judge.run_judge(case.situation, case.expected, reply.text)
                    count(verdict.cost)
                    if verdict.error is not None:
                        state["errors"] += 1
                    state["unreadable"] += 1 if verdict.unreadable else 0
                    reason = redact(verdict.error or verdict.reason)
                    runs.append({"verdict": "error" if verdict.error else verdict.verdict,
                                 "reason": reason, "cost_usd": reply.cost,
                                 "judge_cost_usd": verdict.cost, "error": redact(verdict.error)})
            entry = {"id": case.id, "rules": case.rules,
                     "passes": passes_of(runs) if any(r["verdict"] != "not run" for r in runs) else None,
                     "runs": runs}
            entries.append(entry)
            shown = "not run" if entry["passes"] is None else f"{entry['passes']}/3"
            print(f"case {case.id} ({role}, {', '.join(case.rules)}): {shown}")
            for n, r in enumerate(runs, 1):
                print(f"  run {n}: {r['verdict']}: {r['reason']}")
        results[role] = {"model": model, "model_source": source_of_model, "boot_bytes": boot.bytes,
                         "cases": entries}
        done = [e for e in entries if e["passes"] is not None]
        c = [sum(1 for e in done if e["passes"] == n) for n in (3, 2, 1, 0)]
        print(f"role {role} ({model}): {len(done)} cases: {c[0]} at 3/3, {c[1]} at 2/3, "
              f"{c[2]} at 1/3, {c[3]} at 0/3")
    code = OK
    if spend["calls"] == spend["unmeasured"]:
        print(f"spend: not measured over {spend['calls']} calls")
    else:
        print(f"spend: ${spend['measured']:.2f} measured over {spend['calls']} calls")
    if spend["unmeasured"]:
        print(f"{spend['unmeasured']} calls not measured")
    if state["unreadable"]:
        print(f"{state['unreadable']} verdicts unreadable (counted as FAIL)")
    if state["capped"]:
        print(f"cap reached: {state['skipped']} runs not started")
        code = USAGE
    if args.against:
        lines, regressions = f4(results, [Path(p) for p in args.against], roles)
        print("\n".join(lines))
        if regressions and code == OK:
            code = FAILED
    if args.save:
        data = {
            "schema": 1, "date": started, "head": head, "dirty": dirty,
            "cards": {"kind": source.kind, "ref": source.ref, "sha": source.sha},
            "host": "claude", "claude_version": version, "judge_model": quiz_judge.JUDGE_MODEL,
            "runs_per_case": RUNS, "host_prompt_tokens": HOST_PROMPT_TOKENS,
            "max_usd": args.max_usd, "incomplete": state["capped"], "roles": results,
            "spend": {"estimated": round(total, 4),
                      "measured": None if spend["calls"] == spend["unmeasured"] else round(spend["measured"], 4),
                      "calls_not_measured": spend["unmeasured"]},
        }
        for path in save(data, args.save, args.results_dir):
            print(f"wrote {path}")
    print(f"replies kept in {work_dir()} (nothing is removed there)")
    if state["errors"]:
        print(f"{state['errors']} calls failed", file=sys.stderr)
        return EXTERNAL
    return code


def main(argv=None) -> int:
    try:
        return run(argv)
    except Stop as stop:
        print(f"quiz.py: {stop}", file=sys.stderr)
        return stop.code


if __name__ == "__main__":
    sys.exit(main())

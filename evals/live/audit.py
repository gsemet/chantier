"""Audit a live run: which agent got which role, and did each behave as its role says.

    uv run --no-project python evals/live/audit.py <workspace> [--batch <id>] [--projects <dir>]

Reads the Foreman's Claude transcript and every subagent under it (`subagents/agent-*.jsonl` and
`.meta.json`), finds each agent's parent through the `tool_use` id that started it, and prints the
agent tree, then one PASS/FAIL line per check. It reads; it changes nothing.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

PROMPT = re.compile(r"^chantier (?P<role>[a-z][a-z0-9-]*) for (?P<what>CR-\d+|the stack)\b")
WORKERS = {"investigator", "coder", "inspector", "debugger", "verifier", "conflict-resolver"}
DRIVERS = {"cr-driver", "stack-driver", "qa-driver"}
READ_ONLY = {"inspector", "investigator", "debugger", "verifier"}  # write only their notes
EPOCH_COMMANDS = re.compile(r"chantier\.py\"?\s+(event|heartbeat|cancel|land)\b|agents set")
WINDOW = 300_000  # the plugin agents' `autoCompactWindow`: past it, the agent compacts


def records(path: Path):
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            try:
                yield json.loads(line)
            except ValueError:
                continue


def text_of(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content or [] if isinstance(b, dict))


class Agent:
    def __init__(self, path: Path, meta: dict):
        self.path, self.meta = path, meta
        self.id = path.stem.removeprefix("agent-")
        self.type = meta.get("agentType", "?")
        self.prompt, self.tools, self.spawned = "", [], {}
        self.peak = 0  # the largest context one call sent, in tokens
        for r in records(path):
            m = r.get("message") or {}
            if r.get("type") == "user" and not self.prompt:
                self.prompt = text_of(m.get("content")).strip()
            if r.get("type") == "assistant":
                u = m.get("usage") or {}
                self.peak = max(self.peak, u.get("input_tokens", 0)
                                + u.get("cache_creation_input_tokens", 0)
                                + u.get("cache_read_input_tokens", 0))
                for b in m.get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        self.tools.append((b.get("name"), b.get("input") or {}))
                        self.spawned[b.get("id")] = b.get("input") or {}
        match = PROMPT.match(self.prompt)
        self.role = match["role"] if match else None
        self.what = match["what"] if match else None
        self.parent = None

    def bash(self) -> list[str]:
        return [i.get("command", "") for n, i in self.tools if n in ("Bash", "PowerShell")]

    def writes(self) -> list[str]:
        return [i.get("file_path", "") for n, i in self.tools if n in ("Write", "Edit")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace", type=Path)
    ap.add_argument("--batch")
    ap.add_argument("--projects", type=Path, default=Path.home() / ".claude" / "projects")
    args = ap.parse_args()
    ws = args.workspace.resolve()
    batches = ws / ".agents" / "changes" / "batches"
    batch = args.batch or sorted(p.name for p in batches.iterdir())[-1]
    data = json.loads((batches / batch / "batch.json").read_text(encoding="utf-8"))
    uuid = data.get("foreman_transcript")
    main_path = next(args.projects.glob(f"*/{uuid}.jsonl"), None) if uuid else None
    results: list[tuple[bool, str]] = []

    def check(ok: bool, label: str):
        results.append((bool(ok), label))

    check(main_path is not None, f"the Foreman's transcript {uuid} is found")
    if not main_path:
        return report(results)
    foreman = Agent(main_path, {"agentType": "foreman"})
    agents = []
    for f in sorted(main_path.with_suffix("").rglob("agent-*.jsonl")):
        meta_path = f.with_suffix("").with_suffix(".meta.json")
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        agents.append(Agent(f, meta))
    by_tool = {tid: a for a in [foreman, *agents] for tid in a.spawned}
    for a in agents:
        a.parent = by_tool.get(a.meta.get("toolUseId"))

    print(f"# Batch {batch}: {len(agents)} subagents under the Foreman\n")
    print("| agent | type | role in prompt | for | parent | depth | peak context |")
    print("| --- | --- | --- | --- | --- | --- | ---: |")
    for a in agents:
        parent = "foreman" if a.parent is foreman else (a.parent.role or a.parent.type) \
            if a.parent else "?"
        print(f"| {a.id[:10]} | {a.type} | {a.role or '-'} | {a.what or '-'} | {parent} | "
              f"{a.meta.get('spawnDepth', '?')} | {a.peak:,} |")
    print(f"\nThe Foreman's peak context: {foreman.peak:,} tokens (your own settings set its window).\n")

    reviews = data["settings"].get("reviews", {})
    custom = data["settings"].get("agents", {})
    for a in agents:
        expected = (reviews[a.role]["agent"] if a.role in reviews else custom.get(a.role)
                    or f"chantier:{a.role}")
        check(a.role is not None, f"{a.id[:10]} ({a.type}) starts with a `chantier <role>` prompt")
        if a.role:
            check(a.type == expected, f"{a.id[:10]} runs {expected} for its role {a.role}")
            card = "driver.md" if a.role in DRIVERS else "worker.md"
            check(f"references/{card}" in a.prompt, f"{a.id[:10]} is told to read {card}")
            parent_ok = (a.parent is foreman) if a.role in DRIVERS else \
                (a.parent is not None and a.parent.role in DRIVERS)
            check(parent_ok, f"{a.id[:10]} ({a.role}) was started by "
                             f"{'the Foreman' if a.role in DRIVERS else 'a Driver'}")
        if a.role in WORKERS | set(reviews):
            commits = [c for c in a.bash() if re.search(r"git\s+(commit|push|merge)\b(?!-)", c)]
            check(not commits or a.role == "conflict-resolver",
                  f"{a.id[:10]} ({a.role}) never commits, pushes or merges")
        if a.role in READ_ONLY | set(reviews):
            outside = [w for w in a.writes() if "/work/" not in w.replace("\\", "/")]
            check(not outside, f"{a.id[:10]} ({a.role}) edits nothing but its notes"
                               + (f": {outside[:2]}" if outside else ""))
        if a.type.startswith("chantier:"):
            check(a.peak <= WINDOW, f"{a.id[:10]} ({a.type}) stays within its {WINDOW:,}-token "
                                    f"window (peak {a.peak:,})")
        if a.role in DRIVERS:
            code = [w for w in a.writes() if "/work/" not in w.replace("\\", "/")]
            check(not code, f"{a.id[:10]} ({a.role}) writes no code itself"
                            + (f": {code[:2]}" if code else ""))
    for who in [foreman, *agents]:
        hand = [w for w in who.writes() if w.endswith(("batch.json", "events.jsonl"))]
        check(not hand, f"{who.id[:10]} never edits batch.json or events.jsonl by hand")
    no_epoch = [c for c in foreman.bash() if EPOCH_COMMANDS.search(c) and "--epoch" not in c]
    check(not no_epoch, "every Foreman event, heartbeat, agents set, cancel and land carries its "
                        f"epoch{': ' + no_epoch[0][:80] if no_epoch else ''}")

    roles = Counter(a.role for a in agents)
    check(roles["cr-driver"] >= len(data["crs"]), f"a CR Driver per CR ({roles['cr-driver']} for "
                                                  f"{len(data['crs'])} CRs)")
    for c in data["crs"]:
        check(c["status"] in {"merged", "cancelled"}, f"{c['id']} ended {c['status']}")
    calls = ws.with_name(ws.name + ".forge") / "state.calls"
    refused = [json.loads(line)["args"] for line in calls.read_text(encoding="utf-8").splitlines()
               if json.loads(line)["args"][:2] not in (["pr", "create"], ["pr", "edit"],
                                                       ["pr", "checks"], ["pr", "view"],
                                                       ["run", "list"], ["run", "view"])] \
        if calls.exists() else []
    check(not refused, f"no agent tried to merge or close on the forge{': ' + str(refused[:2]) if refused else ''}")
    dirty = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=ws, capture_output=True,
                           text=True).stdout.splitlines()
    check(all(line[3:].startswith(".agents/changes/") for line in dirty),
          "nothing written in the main checkout outside .agents/changes")
    return report(results)


def report(results) -> int:
    for ok, label in results:
        print(f"{'PASS' if ok else 'FAIL'} {label}")
    failed = sum(not ok for ok, _ in results)
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

# Chantier

The construction site for your Software Factory.

Modern coding agents like Claude Code or Copilot provide "nested session" features.
Chantier uses them to give you a single "ticket office" to talk to,
while one "Foreman" coordinates the work underneath.

![How chantier works](docs/how-chantier-works.svg)

## How it works

You only ever talk to the **Chief of Staff**, in your own session.
It keeps the backlog, asks you the questions a change needs, and starts work only on your go.

1. **It learns your project.** It reads your `AGENTS.md` (or `CLAUDE.md`) for the gates, the
   default branch, your conventions and your team, and asks you what it does not say. There is
   nothing else to configure.
2. **You file work.** Each item becomes a **Change Request**: a folder that keeps the raw request
   (`intake/`), its analysis (`01-intent.md`), every answer you give (`02-answers.md`) and the
   self-contained **Change Specification** (`03-change-spec.md`).
3. **You start a batch** ("run the P1s", "build a PR stack"). After a preflight and your go, the
   Chief of Staff starts one **Foreman** in a nested session.
4. **The Foreman runs the batch.** It owns one background **Driver** per CR slot, plus a stack
   driver and a QA driver when needed, and keeps itself warm with a heartbeat.
5. **Each Driver runs short foreground workers** in the CR's own git worktree: Investigator,
   Coder, Inspector, Debugger, Verifier, Conflict resolver, and any review step you added. It
   ships a PR and waits for CI.
6. **The Foreman reports back.** You steer through the Chief of Staff (add, drop, reorder a CR;
   "I merged #42"); it forwards one `order` line to the Foreman. You merge; chantier does not,
   unless you allow it for a release's fixes.
7. **A Release driver releases, when you ask.** It follows your project's own procedure, and
   stops for your approval before each irreversible action.

Agents never decide mechanics on their own. Every mechanical step goes through the `chantier`
Python CLI (`uv run`), which owns the batch state: slots, rounds, budget, events, gates, waits,
ship and cost. Everything it writes goes to `.agents/changes/`, as plain JSON and Markdown.

## Install

chantier is a [Claude Code plugin](https://code.claude.com/docs/en/plugins), a GitHub Copilot
plugin and an [Agent Plugin](https://agent-plugins.org/): one skill and one agent per role and
host. Claude Code and Copilot get different agents: their tools and model fields differ.

On Claude Code:

```bash
claude plugin marketplace add gsemet/chantier
```

```bash
claude plugin install chantier@chantier
```

On GitHub Copilot:

```bash
copilot plugin marketplace add https://github.com/gsemet/chantier.git
```

```bash
copilot plugin install chantier@chantier
```

New to chantier? Follow the [step-by-step tutorial for Claude Code](docs/tutorial-claude-code.md),
then browse the [use cases](docs/use-cases.md).

Then restart the session and type `/chantier` (on Claude Code, `/chantier:chantier`). Besides
the plugin, the only thing to install is [`uv`](https://docs.astral.sh/uv/); working on a
repository also needs `git` and the forge's CLI, logged in: `gh` for GitHub, `glab` for GitLab.

## Use

Talk to the Chief of Staff in plain language:

| You say | What happens |
| --- | --- |
| "file this idea" | a CR folder in the inbox; it can be refined at any stage |
| "make it a P2" | it moves into the prioritized backlog |
| "run the P1s", "build a stack of these" | preflight, questions, the plan, then a Foreman starts on your go |
| "status?" | one line per CR with its PR; a blocked CR comes back as a question |
| "drop CR-103", "I merged #42" | an order for the Foreman, never a direct action on a Driver |
| "release v1.4.0" | a release CR, run by your project's procedure; you approve each irreversible action |
| "what did it cost?" | measured cost, by role or by CR |
| "use my `rust-coder` agent as the coder" | that role runs your agent from the next batch |
| "add a security review with `sec-reviewer`" | a new review step the Driver runs after the Inspector |
| "which agents and models?" | the team: each role, its agent, its model |

### Your own agents

Any role can run one of your agents. Tell the Chief of Staff, and it writes it in a `chantier`
section of your `AGENTS.md`, shared with your team:

```markdown
## chantier

- coder: `rust-coder`
- security-review: `sec-reviewer`, after the Inspector: OWASP top 10 on the diff
```

The role's contract travels in the spawn prompt, so your agent only needs the tools the role
uses. A name that is not a built-in role becomes an extra review step: it runs after the
Inspector approves and answers with the same verdict. A running batch keeps the team it started
with.

### Models

| Role | Claude | Copilot |
| --- | --- | --- |
| Chief of Staff | your session (Opus 5.5 recommended) | your session |
| Foreman | Sonnet 5.5, effort low | Claude Sonnet 5.5 |
| Drivers (CR, stack, QA, release) | Sonnet 5.5 | Claude Sonnet 5.5 |
| Coder, Investigator, Debugger, Conflict resolver | Sonnet 5.5 | GPT-5.6 Luna |
| Inspector, Verifier | Sonnet 5.5 | GPT-6.1 Sol |

**Fail, never improvise:** if a host refuses a model, a tool or an agent, chantier stops and
says so; it never picks a look-alike or a workaround.

### Change Request lifecycle

Everything lives in `.agents/changes/`:

```text
.agents/changes/
├── backlog/
│   ├── 1-inbox/<slug>/             filed, not prioritized
│   ├── 2-backlog/P1…P4/<slug>/     prioritized by you
│   ├── 3-requests/<number>-<slug>/ in a batch: branch chantier/<batch>/…, worktree next to the repo
│   ├── 4-archives/<number>-<slug>/ merged
│   └── 5-trash/<slug>/             abandoned on your word
└── batches/<batch>/                batch.json, events.jsonl, brief.md, report.md
```

The folder moves, it is never copied; a dropped CR returns where it came from, and collisions
are errors rather than overwrites. While a CR runs, the team writes its notes, gate logs and PR
body in the CR's own `work/` folder.

## Supported hosts

| Host | Nested session | Foreman heartbeat |
| --- | --- | --- |
| Claude Desktop | `start_session` + `detach_session` | 55 minutes |
| Copilot SDK host | `create_session` + `send_message` | 4 minutes (`/every`) |

Preflight refuses everything else (a VS Code tab, the terminal, an unattended run, a linked
worktree) and offers no fallback.

| Forge | CLI | Where |
| --- | --- | --- |
| GitHub | `gh` | github.com, or GitHub Enterprise when `gh` is logged in to its host |
| GitLab | `glab` | gitlab.com, or a self-managed server when `glab` is logged in to its host |

The forge and the project come from the batch's git remote (`origin`, or `--remote`); the login
is the CLI's own (`glab auth login --hostname <host>`). Nothing is configured in chantier.

On Windows, the CLI runs natively (no WSL). Gates run in `cmd.exe`, so write them for it.
`chantier cancel` ends a CR's processes at once, with no grace period, and finds stray ones by
their command line only, since Windows does not expose another process's current directory.

## Costs and budgets

`chantier cost` reports what the Foreman's session and its subagents cost, in total, by role or
by CR. On Claude, chantier prices the transcripts with its own rates for Opus, Sonnet and Haiku
5.5; on Copilot, it reads per-call costs from
[copilot-session-usage](https://github.com/gsemet/copilot-session-usage), which uv fetches from
PyPI, and flags calls that were estimated rather than billed. A missing transcript, an unknown
model or an unpriced call is an error, never a guess. The Foreman records the spend at each
heartbeat; past the batch budget it spawns nothing new.

## Repository layout

```text
plugin.json                 ← Agent Plugins manifest
.claude-plugin/             ← Claude Code plugin manifest and marketplace
.github/plugin/             ← GitHub Copilot marketplace
agents/                     ← Claude Code agents, one per role
com.github.copilot/agents/  ← Copilot agents, one per role (chantier-<role>)
skills/chantier/
├── SKILL.md                ← the Chief of Staff's entry point
├── references/             ← one file per running context: concepts, chief-of-staff,
│                             foreman, driver, worker, message formats
└── scripts/cli/            ← the `chantier` CLI and its tests
scenario/                   ← one whole batch, scripted, no model
evals/                      ← eval campaigns with real agents, and their reports
scripts/                    ← version tooling, run by `just`
docs/                       ← diagrams
```

## Develop

See [CONTRIBUTING.md](CONTRIBUTING.md) for how the project is built and how a release is made.

```bash
just check                  # structure tests (a few seconds)
just scenario               # one whole batch, end to end, no model
```

See [`evals/README.md`](evals/README.md) for the eval campaigns with real agents (claude-smoke,
claude-full, copilot), how to run one, and their last results.

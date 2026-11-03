# Chantier

The construction site for your Software Factory.

Modern coding agents like Claude Code or Copilot CLI provide "nested session" features.
Chantier uses them to give you a single "ticket office" to talk to,
while one "Foreman" coordinates the work underneath.

![How chantier works](docs/how-chantier-works.svg)

## How it works

You only ever talk to the **Chief of Staff**, in your own session.
It keeps the backlog, asks you the questions a change needs, and starts work only on your go.

1. **You file work.** Each item becomes a **Change Request**: a local folder in the project's
   inbox that keeps the raw request (`intake/`), its analysis (`01-intent.md`), every answer you
   give (`02-answers.md`) and the self-contained **Change Specification** (`03-change-spec.md`).
2. **You start a batch** ("run the P1s", "build a PR stack").
   The Chief of Staff reads the project's `AGENTS.md` and linked guidance, prepares and grills the
   selected CRs, then runs a preflight and starts one **Foreman** in a nested session.
3. **The Foreman runs the batch.** It owns one background **Driver** per CR slot,
   plus a stack driver and a QA driver when needed, and keeps itself warm with a heartbeat.
4. **Each Driver runs short foreground workers** in the CR's own git worktree:
   Investigator, Coder, Inspector, Debugger, Verifier and Conflict resolver.
   It ships a PR and waits for CI.
5. **The Foreman reports back** with `ready`, `ask` and `final` messages.
   You steer through the Chief of Staff (add, drop, reorder a CR; "I merged #42").
   It forwards one `order` line to the Foreman. Confirmed merges move CRs to the archive.

Agents never decide mechanics on their own.
Every mechanical step goes through the `chantier` Python CLI (`uv run`),
which owns the batch state: slots, rounds, budget, events, gates, waits, ship and cost.

## Design choices

- **Fail, never improvise.** If a tool, a host feature or a configured model is not available
  exactly as written, chantier stops and reports it.
  It never picks a look-alike model, another tool or a workaround.
- **Static agents per host.** The shipped Claude Code and Copilot agents explicitly declare their
  model, effort and tools. To change one, copy the host's agent to your project and edit your copy;
  no agent generation or model preference files are involved.
- **Cheap by construction.** Short-lived workers, one model per role, a heartbeat tuned to each
  host's prompt-cache lifetime, and a budget stop.
  `chantier cost` reports spend by role and by CR, flagging estimated Copilot calls.

## Supported hosts

| Host | Nested session | Foreman heartbeat |
| --- | --- | --- |
| Claude Desktop | `start_session` + `detach_session` | 55 minutes |
| Copilot SDK host | `create_session` + `send_message` | 4 minutes (`/every`) |

Preflight refuses everything else (a VS Code tab, an unattended run, a linked worktree)
and offers no fallback.
Forge: GitHub (`gh`).

## Install

chantier is a [Claude Code plugin](https://code.claude.com/docs/en/plugins), a GitHub Copilot
plugin and an [Agent Plugin](https://agent-plugins.org/): the skill plus one agent per role and
host, each pinned to its model, effort and tools. Claude Code and Copilot get different agents:
their tools and model fields differ.

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
copilot plugin install chantier@chantier
```

Then restart the session. There is no project configuration file and no agent generation.
The Chief of Staff reads `AGENTS.md` and any linked project guidance to infer the lifecycle paths,
Git conventions and fast and long gates. If a necessary gate or default branch is unclear, it asks
you instead of assuming success. It records the decisions for each batch in `batch.json`.
Old `.agents/chantier.json` and model YAML files are ignored, not migrated or deleted.

To customize a role, copy the appropriate shipped agent into `.claude/agents/` or
`.github/agents/` and edit its model, effort or tool list. A copy with the role's original
filename takes precedence automatically. For a differently named agent, name it in the project's
`AGENTS.md` and restart the session:

```markdown
- chantier copilot coder agent: .github/agents/my-coder.agent.md
- chantier claude coder agent: .claude/agents/rust-coder.md
```

Each copy keeps its host's frontmatter and decides its own model, effort and tools.
Copilot's `create_session` cannot select a Foreman agent file or set its effort: the Chief of
Staff supplies its model and prompt, and the session's effort and tools apply.

Besides the plugin, the only thing to install is [`uv`](https://docs.astral.sh/uv/).
The CLI is plain Python scripts with PEP 723 inline metadata: there is no package to install.
For costs on Copilot, uv fetches
[copilot-session-usage](https://github.com/gsemet/copilot-session-usage) from PyPI when needed.
Working on a repository also needs `git` and an authenticated `gh`, which you already have there.

On Windows, the CLI runs natively (no WSL). Gates run in `cmd.exe`, so write them for it.
`chantier cancel` ends a CR's processes at once, with no grace period, and finds stray ones by
their command line only, since Windows does not expose another process's current directory.

## Use

Talk to the Chief of Staff in plain language:

| You say | What happens |
| --- | --- |
| "file this idea" | a CR folder is created in the inbox; it can be grilled at any stage |
| "make it a P2" | `triage` moves it into the prioritized backlog |
| "run the P1s", "build a stack of these" | preflight, questions, then a Foreman starts the batch |
| "status?" | `chantier status`, with PR links; a blocked CR comes back as a question |
| "drop CR-103", "I merged #42" | an `order` for the Foreman, never a direct action on a Driver |
| "what did it cost?" | `chantier cost`, by role and by CR |
| "which models?" | `chantier models`: the resolved id of every role and where it comes from |

### Change Request lifecycle

Unless the project guidance specifies another layout, each CR moves through:

```text
.agents/changes/
├── backlog/
│   ├── 1-inbox/<slug>/
│   ├── 2-backlog/P1…P4/<slug>/
│   ├── 3-requests/<number>-<slug>/
│   ├── 4-archives/<number>-<slug>/
│   └── 5-trash/<slug>/
└── batches/<batch>/             # runtime state and batch brief
```

The inbox holds ideas; the backlog holds what you have prioritized into P1 to P4. The Chief of
Staff can grill a CR at any stage to sharpen its specification.

`file` creates an inbox folder; `triage` moves it to the priority you choose. Opening or adding to a batch
requires an existing prepared folder, or an explicitly named specification within it; the whole
folder moves to requests. A dropped CR returns to its original inbox or priority folder. Only an
explicitly abandoned, unclaimed CR goes to trash. A confirmed merge moves the folder to archives.
Existing files are preserved, and collisions are errors rather than overwrites.

The Chief of Staff passes project-specific stage paths and gates as CLI options, and propagates
the changes root to the Foreman and workers. They put `--changes-dir <absolute-path>` before the
subcommand in every invocation, so separate shell calls cannot lose it. `chantier path <cr>
--batch <batch>` returns the folder's current absolute path; `--spec` returns the recorded
specification, even when its filename differs.

## Costs and budgets

Ask the Chief of Staff what a batch cost. `chantier cost` reports the total and can group it
by role or by CR. It covers the Foreman's session and its subagents, not the Chief of Staff's
own session.

On Claude, chantier prices the transcripts using its built-in rates. On Copilot, it reads
per-call costs from `copilot-session-usage`; calls estimated rather than billed are flagged in
the total. If the transcript, the dependency or a call price is unavailable, the command fails
instead of inventing a cost.

The Foreman updates the recorded spend at each heartbeat. Once that amount reaches the batch
budget, it stops spawning new work; the budget check can therefore lag by one heartbeat.

## Repository layout

```text
plugin.json               ← Agent Plugins manifest (the skill under `extensions`)
.claude-plugin/           ← Claude Code plugin manifest and marketplace
.github/plugin/           ← GitHub Copilot marketplace
agents/                   ← static Claude Code agents
com.github.copilot/agents/ ← static GitHub Copilot agents
skills/chantier/
├── SKILL.md              ← entry point and routing
├── references/           ← definitions, role cards, capabilities, message formats
├── scripts/cli/          ← the `chantier` CLI and its tests
└── evals/                ← deterministic scenario and model behavior cases
scripts/                  ← version and release tooling, run by `just`
docs/                     ← diagrams
```

## Develop

See [CONTRIBUTING.md](CONTRIBUTING.md) for how the project is built and how a release is made.
Recipes need [`just`](https://just.systems/) and `uv`:

```bash
just check                  # static-agent and structure tests (a few seconds)
just scenario               # optional: one whole batch, end to end, no model
just version 1.2.3          # set the version in every file that carries it
just bump-version           # patch; or `just bump-version minor`, `just bump-version major`
```

See [`evals/README.md`](skills/chantier/evals/README.md) for the model behavior cases.

# Chantier

The construction site for your Software Factory.

Modern coding agents like Claude Code or Copilot CLI provide "nested session" features.
Chantier uses them to give you a single "ticket office" to talk to,
while one "Foreman" coordinates the work underneath.

![How chantier works](docs/how-chantier-works.svg)

## How it works

You only ever talk to the **Chief of Staff**, in your own session.
It keeps the backlog, asks you the questions a change needs, and starts work only on your go.

1. **You file work.** Each item becomes a **Change Request**: a local folder that keeps the raw
   request (`intake/`), its analysis (`01-intent.md`), every answer you give (`02-answers.md`)
   and the self-contained **Change Specification** (`03-change-spec.md`).
2. **You start a batch** ("run the P1s", "build a PR stack").
   The Chief of Staff runs a preflight, then starts one **Foreman** in a nested session
   and detaches it.
3. **The Foreman runs the batch.** It owns one background **Driver** per CR slot,
   plus a stack driver and a QA driver when needed, and keeps itself warm with a heartbeat.
4. **Each Driver runs short foreground workers** in the CR's own git worktree:
   Investigator, Coder, Inspector, Debugger, Verifier and Conflict resolver.
   It ships a PR and waits for CI.
5. **The Foreman reports back** with `ready`, `ask` and `final` messages.
   You steer through the Chief of Staff (add, drop, reorder a CR; "I merged #42"),
   and it forwards one `order` line to the Foreman.

Agents never decide mechanics on their own.
Every mechanical step goes through the `chantier` Python CLI (`uv run`),
which owns the batch state: slots, rounds, budget, events, gates, waits, ship, cost
and the exact model of every role.

## Design choices

- **Fail, never improvise.** If a tool, a host feature or a configured model is not available
  exactly as written, chantier stops and reports it.
  It never picks a look-alike model, another tool or a workaround.
- **Exact models, configurable without editing the skill.**
  Base lists per host live in
  [`references/models/`](skills/chantier/references/models/) (`claude.yml`, `copilot.yml`).
  You override them in `~/.config/chantier/models.yml`, then `.agents/chantier.models.yml`,
  then the batch brief.
  Each role can also set its reasoning effort; unset, your own setting applies.
- **Cheap by construction.** Short-lived workers, one model per role, a heartbeat tuned to each
  host's prompt-cache lifetime, and a budget stop.
  `chantier cost` reports measured spend by role and by CR.

## Supported hosts

| Host | Nested session | Foreman heartbeat |
| --- | --- | --- |
| Claude Desktop | `start_session` + `detach_session` | 55 minutes |
| Copilot SDK host | `create_session` + `send_message` | 4 minutes (`/every`) |

Preflight refuses everything else (a VS Code tab, an unattended run, a linked worktree)
and offers no fallback.
Forge: GitHub (`gh`).

## Install

chantier is a [Claude Code plugin](https://code.claude.com/docs/en/plugins) and an
[Agent Plugin](https://agent-plugins.org/): the skill plus one agent per role
(`chantier:foreman`, `chantier:cr-driver`, `chantier:coder`, …), each pinned to its model, effort
and tools.

```bash
claude plugin marketplace add gsemet/chantier
```

```bash
claude plugin install chantier@chantier
```

Then restart the session. That is all: in any repository, ask the Chief of Staff for a batch.
Nothing is written in the repository until you start one: no configuration file (defaults
apply) and no agent file (the plugin ships them).

`.agents/chantier.json` is optional and holds only what differs from the defaults, for example
the project's gates:

```json
{"gates": {"fast": ["uv run pytest -q"], "long": []}}
```

A model override (`~/.config/chantier/models.yml` or `.agents/chantier.models.yml`) needs that
role's own agent file: ask **"set up chantier"** (it runs `chantier setup`, which writes only the
overridden roles), then restart the session. On Copilot, `chantier setup` writes every role's agent
in `.github/agents/`.

Besides the plugin, the only thing to install is [`uv`](https://docs.astral.sh/uv/).
The CLI is plain Python scripts with PEP 723 inline metadata: there is no package to install,
and uv fetches any dependency from pypi.org when the CLI runs
(for example [copilot-session-usage](https://github.com/gsemet/copilot-session-usage),
used by `chantier cost` on Copilot).
Working on a repository also needs `git` and an authenticated `gh`, which you already have there.

On Windows, the CLI runs natively (no WSL). Gates run in `cmd.exe`, so write them for it.
`chantier cancel` ends a CR's processes at once, with no grace period, and finds stray ones by
their command line only, since Windows does not expose another process's current directory.

## Use

Talk to the Chief of Staff in plain language:

| You say | What happens |
| --- | --- |
| "file this issue" | the item is added to the backlog and triaged |
| "run the P1s", "build a stack of these" | preflight, questions, then a Foreman starts the batch |
| "status?" | `chantier status`, with PR links; a blocked CR comes back as a question |
| "drop CR-103", "I merged #42" | an `order` for the Foreman, never a direct action on a Driver |
| "what did it cost?" | `chantier cost`, by role and by CR |
| "which models?" | `chantier models`: the resolved id of every role and where it comes from |

## Repository layout

```text
plugin.json               ← Agent Plugins manifest (agents and skills under `extensions`)
.claude-plugin/           ← Claude Code plugin manifest and marketplace
agents/                   ← the plugin's agents, generated from the templates (`just agents`)
skills/chantier/
├── SKILL.md              ← entry point and routing
├── references/           ← definitions, role cards, capabilities, models, message formats
├── assets/agents/        ← agent templates
├── scripts/cli/          ← the `chantier` CLI and its tests
└── evals/                ← deterministic scenario and model behavior cases
scripts/                  ← version and agent generation, run by `just`
docs/                     ← diagrams
```

## Develop

Recipes need [`just`](https://just.systems/) and `uv`:

```bash
just check                  # agents up to date, CLI unit tests, whole batch scenario
just agents                 # regenerate agents/ after editing a template or the base models
just version 1.2.3          # set the version in every file that carries it
just bump-version           # patch; or `just bump-version minor`, `just bump-version major`
```

See [`evals/README.md`](skills/chantier/evals/README.md) for the model behavior cases.

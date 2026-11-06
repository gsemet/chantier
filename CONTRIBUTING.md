# Contributing to chantier

This guide is for the people who work on chantier itself. To use it, read the
[README](README.md).

## How the project is built

chantier is four things in one repository:

1. **A skill** ([`skills/chantier/`](skills/chantier/)). `SKILL.md` is the Chief of Staff's entry
   point. [`references/`](skills/chantier/references/) holds one file per running context:
   `concepts.md` (read by everyone), `chief-of-staff.md`, `foreman.md`, `driver.md`, `worker.md`
   and `routing.md`; `hosts/claude-code.md` and `hosts/copilot.md` hold what is proper to a host
   (tools, heartbeat, sessions), each behaviour marked proved, documented or unproved, and the
   cards only point to them. They are written for agents: short, exact, one meaning per word. A card
   says what a role judges and how; the project's own rules (`chantier rules`) rank above it.
2. **A CLI** ([`skills/chantier/scripts/cli/`](skills/chantier/scripts/cli/)): plain Python with
   no dependency, run by `uv run --script`, on Linux, macOS and Windows. Its scope is the frame
   the agents work in: the CR lifecycle (`file`, `triage`, `abandon`, `open`, the stages,
   `cancel`, `land`, `close`), the batch's limits and record (`take`, `round`, `handback`,
   `ship`, `release go`; `rails.py` says what is refused), the means to synchronise (`order`,
   `asks`, `note`, `gate` and its lock) and a few tools (`rules`, `cost`). It runs no git
   command that changes anything (it reads the head, the remote and the status to say what is
   off) and no forge command: the agents have `git`, `gh` and `glab` and do the work. It writes
   only in the target repository's
   `.agents/changes/`, as plain JSON and Markdown: the CR folders in `1-inbox/`, `2-backlog/`,
   `3-requests/`, `4-archives/` and `5-trash/` (each with a `work/` folder while it runs), and
   the batch folders `3-requests/batch-<n>/` (`batch.json`, `events.jsonl`, the brief,
   `STATUS.md`). There is no configuration file: every agent reads the project's `AGENTS.md`.
   The CLI knows no role: the cards hold each role's contract, and the Foreman and the Drivers
   write the prompts. A new CLI tool comes only from measured token-costly behaviour of the
   agents, never from speculation about what they might need.
3. **A plugin**: [`.github/plugin/`](.github/plugin/) (GitHub Copilot: `plugin.json` and the marketplace) and
   [`.claude-plugin/`](.claude-plugin/) (Claude Code) ship the skill
   and one agent per role and host: [`agents/`](agents/) for Claude Code (`chantier:<role>`),
   [`com.github.copilot/agents/`](com.github.copilot/agents/) for Copilot (`chantier-<role>`, a
   prefix a project agent named after the role cannot shadow). An agent file holds only its
   host's frontmatter (model, tools) and a short body; both hosts' bodies are identical, which the
   tests check. The Foreman is a session, not an agent: its model is in
   [`chief-of-staff.md`](skills/chantier/references/chief-of-staff.md), where it is started.

4. **A mod** ([`hooks/`](hooks/), Claude Code only): the CR board, a read-only pane over
   `.agents/changes/3-requests/STATUS.json`. `hooks/hooks.json` names `register.tsx`, which
   hooks `skill.prompt`, the `/chantier-board` command and the `cr-board` pane; `types/index.d.ts`
   (named in `plugin.json`) is its contract. It writes nothing and runs no process but
   `git rev-parse`. Copilot has no such thing: its manifest names no hooks. The mod reads
   `STATUS.json` (`schema` 2) as `status.py` writes it: change both together.

The design rule that shapes everything: **no fallback.** When a tool, a host feature, a model
or an agent is not exactly available, chantier stops and says so; it never picks a look-alike.
Within what they have, the Foreman and the stack and release Drivers (Opus 5.5), the CR and QA Drivers (Sonnet 5.5) judge freely: the cards state
goals and boundaries, not procedures. Keep both true in any change.

## Set up

Install [`uv`](https://docs.astral.sh/uv/), [`just`](https://just.systems/) and `git`.
Nothing else: `uv` fetches Python and the test dependencies.

To run your working copy in Claude Code, install the plugin from your checkout, once:

```bash
claude plugin marketplace add ./
```

```bash
claude plugin install chantier@chantier
```

The plugin is then read live from that checkout, and [`.claude/settings.json`](.claude/settings.json)
keeps it on in every session of this repository: a session here runs chantier itself, which is
how you debug it. An edit loads at the next session or with `/reload-plugins`, with no reinstall.
The main checkout is what runs: a branch switched there changes the plugin, and a worktree's work
counts once merged.

## Daily work

```bash
just                # list the recipes
just check          # structure tests: run before any PR
just test -k agent  # structure tests, with pytest arguments
just scenario       # one whole batch, end to end, through the real CLI and a fake gh, then glab
```

The mod is checked apart from `just check` and CI, which have no `claude` binary. With Claude Code
installed (on Claude Desktop `claude` is not on the `PATH`: use the session's own binary, the
process `CLAUDE_PID` names, `(Get-Process -Id $env:CLAUDE_PID).Path` on Windows):

```bash
claude plugin validate .        # the manifest, hooks.json and what register.tsx hooks and calls
claude plugin test .            # hooks/register.test.tsx, against the engine, no session
tsc -p <folder>                 # the type-check, see below
```

`tsc` is not one of the project's tools: fetch it where you need it (`typescript` from npm).
Keep outside the mod folder a `<folder>/tsconfig.json`, with the options from the header of the
engine's `claude-code/index.d.ts`, and that d.ts under `<folder>/types/claude-code/`; its
`include` names those and the absolute paths of `hooks/` and `types/`.

`validate` warns about the marketplace description and the missing icon; those are known. The
tests stand in for the file system, the process and the session's folder with the engine's own
`on` hooks; they do not draw a real pane, so open the board in a session once after a change.

- Repository text is in English.
- Write code and docs in the style of the surrounding files: short sentences, exact terms.
- Tests check the structure (versions, manifests, agents, references, and a smoke run in a fresh
  repository) in a few seconds. They do not evaluate the batch workflow: run `just scenario`
  ([scenario/](scenario/README.md)) when you change it; CI runs it too, on Linux.
- With real agents, the [eval campaigns](evals/README.md): `real` before a release,
  `claude-smoke` after a change to a role or the flow, `claude-full` after a change to how a
  batch handles failures, `copilot` for a change to Copilot's mechanics. Each run commits its
  report.
- `main` is protected: every change goes through a pull request, merged by rebase once CI
  (`just check` on Linux, macOS and Windows, and `just scenario` on Linux) is green.

## Versions

One version, `MAJOR.MINOR.PATCH`, is carried by the CLI, `pyproject.toml`, `uv.lock`,
`SKILL.md`, the plugin manifests and marketplaces, and the agents. Never edit it by hand:

```bash
just version-show
just version 1.2.3            # an exact version
just bump-version             # patch; or `just bump-version minor`, `just bump-version major`
```

The script writes nothing if one file disagrees with the current version. Preflight refuses to
run when the skill, the CLI and the agents disagree, so every file must move together.

## Release

1. From an up-to-date `main` with green CI, on a new branch, prepare the release. This bumps
   the version, runs `just check` and commits `release: vX.Y.Z`; it pushes nothing:

   ```bash
   just release          # patch; or `just release minor`, `just release major`
   ```

2. Push the branch, open a pull request and merge it by rebase once CI is green.
3. Tag the merged commit on `main` and push the tag:

   ```bash
   just tag
   ```

4. Publish the GitHub release with its notes:

   ```bash
   gh release create vX.Y.Z --generate-notes
   ```

Users get the new version by updating the plugin from its marketplace, then restarting their
session.

# Contributing to chantier

This guide is for the people who work on chantier itself. To use it, read the
[README](README.md).

## How the project is built

chantier is four things in one repository:

1. **Four skills.** [`skills/chantier/`](skills/chantier/) holds the router (`SKILL.md` asks
   which role the session takes), the cards, the CLI and the assets; the entries
   [`skills/chief-of-staff/`](skills/chief-of-staff/), [`skills/griller/`](skills/griller/) and
   [`skills/status/`](skills/status/) are thin and load the same cards. [`references/`](skills/chantier/references/) holds one file per
   running context: `concepts.md` (read by everyone), `session-start.md` (the start checks, the
   seat, the session titles), `chief-of-staff.md`, `griller.md`, `status-layout.md`, `foreman.md`, `driver.md`, `worker.md`
   and `routing.md`; `pr-template.md` is the default PR description a CR Driver writes and the
   Inspector audits; `release-template.md` is the default release notes and announcement thread the
   release Driver writes when the project has none of its own; `hosts/claude-code.md` and
   `hosts/copilot.md` hold what is proper to a host (tools, heartbeat, sessions), each behaviour
   marked proved, documented or unproved, and the cards only point to them. They are written for agents: short, exact, one meaning per word. A card
   says what a role judges and how; the project's own rules (`chantier rules`) rank above it.
2. **A CLI** ([`skills/chantier/scripts/cli/`](skills/chantier/scripts/cli/)): plain Python with
   no dependency, run by `uv run --script`, on Linux, macOS and Windows. Its scope is the frame
   the agents work in: the CR lifecycle (`file`, `triage`, `abandon`, `open`, the stages,
   `cancel`, `pause`, `close`), the batch's limits and record (`take`, `round`, `handback`,
   `ship`, `release go`; `rails.py` says what is refused), the means to synchronise (`order`,
   `asks`, `note`, `gate` and its lock) and a few tools (`rules`, `cost`). It runs no git
   command that changes anything (it reads the head, the remote and the status to say what is
   off) and no forge command: the agents have `git`, `gh` and `glab` and do the work. It writes
   only in the planning folder (the target repository's `.agents/changes/`, or the project's
   folder of an external planning surface, plus its own `.gitignore`), as plain JSON and
   Markdown: the CR folders in `1-inbox/`, `2-backlog/`,
   `3-ready/`, `4-batch/` (`1-pending/`, `2-actives/`, `3-done/`), `5-archives/` and `6-trash/`
   (each with a `work/` folder while it runs), and the batch's own files at the root of
   `4-batch/` (`batch.json`, `events.jsonl`, the brief, `STATUS.md`). There is no configuration file: every agent reads the project's `AGENTS.md`.
   The CLI knows no role: the cards hold each role's contract, and the Foreman and the Drivers
   write the prompts. One named exception among the tools: `board`, a read-only web view of this
   record for the user in remote (it writes no file, uses the standard library only and knows no
   role; more is another CR). A new CLI tool comes only from measured token-costly behaviour of the
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
   `.agents/changes/STATUS.json`. `hooks/hooks.json` names `register.tsx`, which
   hooks `skill.prompt`, `session.compact` (the automatic reload), the `/chantier-board` command
   and the `cr-board` pane, and guards a worker's writes (`agent.spawn` and `tool.call`: it starts an
   agent whose prompt holds a `writes:` line in its first folder and refuses its Write, Edit or
   NotebookEdit outside the folders named; a shell write is not guarded); `types/index.d.ts`
   (named in `plugin.json`) is its contract. It writes nothing and runs no process but
   `git rev-parse`. Copilot has no such thing: its manifest names no hooks. The mod reads
   `STATUS.json` (`schema` 3) as `status.py` writes it: change both together. The CR board pane
   and `chantier board` show the same view (`schema` 3) and change with `status.py`.

The design rule that shapes everything: **no fallback.** When a tool, a host feature, a model
or an agent is not exactly available, chantier stops and says so; it never picks a look-alike.
Within what they have, the Foreman and the Drivers judge freely: the cards state
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
just mod            # the mod: claude plugin validate, then claude plugin test (needs a claude binary)
```

The mod is checked apart from `just check` and CI, which have no `claude` binary. `just mod` is
the way to run `validate` and `test`: it finds `claude` on the `PATH`, else the executable of the
process `CLAUDE_PID` names (on Claude Desktop `claude` is not on the `PATH`), and stops with one
line when it finds none. It runs, from the repository's root:

```bash
claude plugin validate .        # the manifest, hooks.json and what register.tsx hooks and calls
claude plugin test .            # hooks/register.test.tsx, against the engine, no session
```

The type-check is by hand:

```bash
tsc -p <folder>                 # see below
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
- With real agents, the [eval campaigns](evals/README.md): one quick campaign (`real-foreman`
  or `real-direct`, five frozen CRs on the sandbox) after a change to a role or the flow, in the
  mode it touched; `full` and both quick campaigns before a release; `claude-planted` after a
  change to how a batch handles
  failures; `copilot` for a change to Copilot's mechanics. Each run commits its report, with the
  [scorecard](evals/SCORECARD.md) for the Claude campaigns.
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

1. From an up-to-date `main` with green CI, agree on the version. Then, on a new branch, write the
   release folder `docs/release-notes/<today>-vX.Y.Z/` as
   [docs/release-process.md](docs/release-process.md) says.
2. Prepare the release. This bumps the version and runs `just check`, which refuses missing or
   invalid notes. It then stages `docs/release-notes/` and commits `release: vX.Y.Z`; it pushes
   nothing:

   ```bash
   just release          # patch; or `just release minor`, `just release major`
   ```

3. Push the branch and open the pull request. The user reviews the release folder in the PR's body and its files. Merge it
   by rebase once CI is green.
4. Tag the merged commit on `main` and push the tag:

   ```bash
   just tag
   ```

   It refuses unless origin/main's head is the `release: vX.Y.Z` commit of the local version, so
   a commit pushed after the merge never gets the tag.

5. Publish the reviewed notes as they are, with the images attached:

   ```bash
   uv run --script scripts/release_notes.py --prepare vX.Y.Z --output <tmp>/release-notes.md --assets <tmp>/assets
   gh release create vX.Y.Z --title vX.Y.Z --verify-tag --notes-file <tmp>/release-notes.md <each file that --prepare listed>
   ```

   `--verify-tag` makes `gh` refuse when the tag `just tag` pushed is not on the forge, instead
   of creating one.

   A typo found after publication is fixed by editing the release on GitHub. The published text
   may then differ from the file, and that is accepted.
6. The user posts the thread from `tweet.md`.

Users get the new version by updating the plugin from its marketplace, then restarting their
session.
